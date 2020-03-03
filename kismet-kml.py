import sqlite3
import argparse
from datetime import datetime
import json
import simplekml
from xml.sax.saxutils import escape


class KMLGen():

    def __init__(self, filename, printjson, inplace):
        self.inputFile = filename
        basename = filename.split(
            ".")[-2] if inplace else filename.split(".")[-2].split("/")[-1]
        self.outputFile = basename + ".kml"
        self.jsonFile = basename + ".json"
        # Initialize variables
        self.rows = []
        self.clients = []
        self.aps = []
        self.bridged = []
        self.other = []
        self.probes = set([])

        #  Load data from the database file passed in
        self.getData()
        #  Parse the data, sorting into aps, bridged, clients, other
        self.parseData()
        #  Take the parsed data and generate a KML
        self.createKML()

        jsonData = json.dumps({
            "clients": self.clients,
            "aps": self.aps,
            "bridged": self.bridged,
            "other": self.other,
            "probes": list(self.probes)
        }, indent=2)
        # Write the sorted data into a nicely formatted JSON file
        output = open(self.jsonFile, "w")
        output.write(jsonData)
        output.close()

        if printjson:
            print(jsonData)

    # Connects to the Kismet database file and pulls the rows from the devices table
    def getData(self):
        conn = sqlite3.connect(self.inputFile)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM devices")
        self.rows = c.fetchall()
        c.close()

    # Process the collected data
    def parseData(self):
        #  Filter the data into lists based on type
        clients = list(
            filter(lambda x: x["type"] == "Wi-Fi Client", self.rows))
        aps = list(filter(lambda x: x["type"] == "Wi-Fi AP", self.rows))
        bridged = list(
            filter(lambda x: x["type"] == "Wi-Fi Bridged", self.rows))
        other = list(filter(lambda x: x["type"] not in [
                     "Wi-Fi Client", "Wi-Fi AP", "Wi-Fi Bridged"], self.rows))

        #  Parse every item, placing the result into an approriate list
        self.clients = list(map(lambda x: self.parseClient(x), clients))
        self.aps = list(map(lambda x: self.parseAP(x), aps))
        self.bridged = list(map(lambda x: self.parseOther(x), bridged))
        self.other = list(map(lambda x: self.parseOther(x), other))

    #  Fetches every location a device was seen, and works out Lat/Lon based on position when
    #  signal strength was highest
    def getLocationData(self, device_json):
        fields = {}
        fields["Locations"] = []
        if "kismet.device.base.location_cloud" in device_json:
            locations = device_json["kismet.device.base.location_cloud"]
        else:
            locations = None

        if type(locations) is dict:
            maxdBm = -1000
            for loc in locations["kis.gps.rrd.samples_100"]:
                outputLoc = {
                    "Latitude": loc["kismet.historic.location.lat"],
                    "Longitude": loc["kismet.historic.location.lon"],
                    "dBm": loc["kismet.historic.location.signal"],
                    "Time": str(datetime.fromtimestamp(loc["kismet.historic.location.time_sec"]))
                }
                fields["Locations"].append(outputLoc)
                if outputLoc["dBm"] > maxdBm:
                    fields["Latitude"] = outputLoc["Latitude"]
                    fields["Longitude"] = outputLoc["Longitude"]
                    maxdBm = outputLoc["dBm"]
        else:
            fields["Latitude"] = 0
            fields["Longitude"] = 0
        return fields

    # Returns all the fields common to every device type
    def getCommonFields(self, row, device_json):
        fields = {}
        fields["Type"] = row["type"]
        fields["First Seen"] = str(datetime.fromtimestamp(row["first_time"]))
        fields["Last Seen"] = str(datetime.fromtimestamp(row["last_time"]))
        fields["Device MAC"] = row["devmac"]
        fields["Common Name"] = device_json["kismet.device.base.commonname"]
        fields["Channel"] = device_json["kismet.device.base.channel"]
        fields["Key"] = device_json["kismet.device.base.key"]
        return fields

    # For a given client, find any APs it's associateprint(file.split(".")[-1])d with
    def getClientAPs(self, device_json):
        fields = {}
        clientMap = device_json["dot11.device"]["dot11.device.client_map"]
        fields["APs"] = []
        if clientMap:
            for ap in clientMap:
                fields["APs"].append({
                    "Key": clientMap[ap]["dot11.client.bssid_key"],
                    "BSSID": clientMap[ap]["dot11.client.bssid"]
                })
        return fields

    #  For a given device, find any probes it may have sent out
    def getProbes(self, device_json):
        fields = {}
        fields["Probes"] = []
        row_probes = device_json["dot11.device"]["dot11.device.probed_ssid_map"]
        for probe in row_probes:
            if row_probes[probe]["dot11.probedssid.ssid"]:
                ssid = row_probes[probe]["dot11.probedssid.ssid"]
                fields["Probes"].append({"SSID": ssid})
                self.probes.add(ssid)
        return fields

    #  Parse an AP object, creating necesarry common keys, and populate with client macs/uuids
    def parseAP(self, row):
        fields = {}
        device_json = json.loads(row["device"].decode("utf-8"))
        # Get common fields and location data
        fields.update(self.getCommonFields(row, device_json))
        fields.update(self.getLocationData(device_json))

        # Populate the SSID field
        try:
            fields["SSID"] = device_json["dot11.device"]["dot11.device.last_beaconed_ssid"]
        except:
            fields["SSID"] = ""

        # Populate an array of client objects
        row_clients = device_json["dot11.device"]["dot11.device.associated_client_map"]
        fields["Clients"] = [{k: v} for k, v in row_clients.items()]

        # Iterate over the clients, adding their MACs and UUIDs
        for i, client in enumerate(fields["Clients"]):
            key = list(client.values())[0]
            # Filter the client list to get all clients matching the Key
            matched = list(filter(lambda c: key == c["Key"], self.clients))
            if len(matched) > 0:
                # fields["Clients"][i] = matched[0]
                matchedClient = matched[0]
                fields["Clients"][i] = {
                    "Key": key, "Device MAC": matchedClient["Device MAC"]}
            else:
                fields["Clients"][i] = {"Key": key,
                                        "Device MAC": list(client.keys())[0]}
        return fields

    def parseClient(self, row):
        fields = {}
        device_json = json.loads(row["device"].decode("utf-8"))
        fields.update(self.getCommonFields(row, device_json))
        fields.update(self.getLocationData(device_json))
        fields.update(self.getClientAPs(device_json))
        fields.update(self.getProbes(device_json))
        return fields

    def parseOther(self, row):
        fields = {}
        device_json = json.loads(row["device"].decode("utf-8"))
        fields.update(self.getCommonFields(row, device_json))
        fields.update(self.getLocationData(device_json))
        fields.update(self.getClientAPs(device_json))
        fields.update(self.getProbes(device_json))
        return fields

    def getCommonExtendedData(self, object, point):
        ed = point.extendeddata
        ed.newdata(name="Device MAC", value=escape(object["Device MAC"]))
        ed.newdata(name="Type", value=escape(object["Type"]))
        ed.newdata(name="First Seen", value=escape(object["First Seen"]))
        ed.newdata(name="Last Seen", value=escape(object["Last Seen"]))
        ed.newdata(name="Channel", value=escape(object["Channel"]))
        return point

    def getPlacemark(self, folder, object, style):
        point = folder.newpoint(name=escape(object["Common Name"]), coords=[
                                (object["Longitude"], object["Latitude"])])
        point.style = style
        return point

    def createKML(self):
        kml = simplekml.Kml()

        kmlClients = kml.newfolder(name="Clients")
        kmlAPs = kml.newfolder(name="APs")
        kmlBridged = kml.newfolder(name="Bridged")
        kmlOther = kml.newfolder(name="Other")

        circleUrl = "http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png"

        blueCircle = simplekml.Style()
        blueCircle.iconstyle.icon.href = circleUrl
        blueCircle.iconstyle.color = simplekml.Color.blue

        amberCircle = simplekml.Style()
        amberCircle.iconstyle.icon.href = circleUrl
        amberCircle.iconstyle.color = simplekml.Color.orange

        greenCircle = simplekml.Style()
        greenCircle.iconstyle.icon.href = circleUrl
        greenCircle.iconstyle.color = simplekml.Color.green

        redCircle = simplekml.Style()
        redCircle.iconstyle.icon.href = circleUrl
        redCircle.iconstyle.color = simplekml.Color.red

        for client in self.clients:
            if client["Locations"]:
                pm = self.getPlacemark(kmlClients, client, blueCircle)
                pm = self.getCommonExtendedData(client, pm)
                ed = pm.extendeddata

                for probe in client["Probes"]:
                    ed.newdata(name="Probed SSID",
                               value=escape(probe["SSID"]))

                for i, ap in enumerate(client["APs"]):
                    clist = list(
                        filter(lambda x: x["Key"] == ap["Key"], self.aps))
                    if len(clist) > 0:
                        ssid = clist[0]["SSID"]
                        name = "AP " + str(i) + " SSID"
                        ed.newdata(name=name, value=escape(ssid))
                        name = "AP " + str(i) + " BSSID"
                        ed.newdata(name=name, value=escape(ap["BSSID"]))

        for ap in self.aps:
            if ap["Locations"]:
                pm = self.getPlacemark(kmlAPs, ap, greenCircle)
                pm = self.getCommonExtendedData(ap, pm)
                ed = pm.extendeddata

                ed.newdata(name="SSID", value=escape(ap["SSID"]))

                for c in ap["Clients"]:
                    ed.newdata(name="Client Device MAC",
                               value=escape(c["Device MAC"]))

        for other in self.other:
            if other["Locations"]:
                folder = kmlClients if other["APs"] else kmlOther
                style = blueCircle if other["APs"] else redCircle

                pm = self.getPlacemark(folder, other, style)
                pm = self.getCommonExtendedData(other, pm)
                ed = pm.extendeddata

                for probe in other["Probes"]:
                    ed.newdata(name="Probed SSID", value=escape(probe["SSID"]))

                for i, ap in enumerate(other["APs"]):
                    olist = list(
                        filter(lambda x: x["Key"] == ap["Key"], self.aps))
                    if len(olist) > 0:
                        ssid = olist[0]["SSID"]
                        name = "AP " + str(i) + " SSID"
                        ed.newdata(name=name, value=escape(ssid))

                    name = "AP " + str(i) + " BSSID"
                    ed.newdata(name=name, value=escape(ap["BSSID"]))

        for bridged in self.bridged:
            if bridged["Locations"]:
                folder = kmlClients if bridged["APs"] else kmlBridged
                style = blueCircle if bridged["APs"] else amberCircle

                pm = self.getPlacemark(folder, bridged, style)
                pm = self.getCommonExtendedData(bridged, pm)
                ed = pm.extendeddata

                for probe in bridged["Probes"]:
                    ed.newdata(name="Probed SSID", value=escape(probe["SSID"]))

                for i, ap in enumerate(bridged["APs"]):
                    blist = list(
                        filter(lambda x: x["Key"] == ap["Key"], self.aps))
                    if len(blist) > 0:
                        ssid = blist[0]["SSID"]
                        name = "AP " + str(i) + " SSID"
                        ed.newdata(name=name, value=escape(ssid))

                    name = "AP " + str(i) + " BSSID"
                    ed.newdata(name=name, value=escape(ap["BSSID"]))

        kml.save(self.outputFile)


# Set up command line arguments
parser = argparse.ArgumentParser(
    description="Generates a KML file and a JSON file from the output file of Kismet (2018 Development Version).")

parser.add_argument('filename', metavar='Kismet File', type=str,
                    help="Path to Kismet file (*.kismet).")
parser.add_argument('--print', '-p', required=False,
                    action='store_true', help='Print resulting JSON to stdout.')
parser.add_argument('--inplace', '-i', required=False,
                    action='store_true', help='Save output files in same directory as input file. Default is to output to current working directory')

args = parser.parse_args()


kmlGen = KMLGen(args.filename, args.print, args.inplace)
