import sqlite3
import argparse
from datetime import datetime
from lxml import etree
from pykml.factory import KML_ElementMaker as KML
import json 

class KMLGen():

  def __init__(self, inputFile, outputFile, jsonFile):
    self.inputFile = inputFile
    self.outputFile = outputFile
    self.jsonFile = jsonFile

    self.rows = []

    self.clients = []
    self.aps = []
    self.bridged = []
    self.other = []

    self.getData()
    self.parseData()
    self.createKML()

    jsonOut = {
      "clients": self.clients,
      "aps": self.aps,
      "bridged": self.bridged,
      "other": self.other
    }

    output = open(self.jsonFile, "w")
    output.write(json.dumps(jsonOut, indent=2))
    output.close()
    
  def getData(self):
    conn = sqlite3.connect(self.inputFile)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM devices")
    self.rows = c.fetchall()
    c.close()
 
  def parseData(self):
    clients = list(filter(lambda x: x["type"] == "Wi-Fi Client", self.rows))
    aps = list(filter(lambda x: x["type"] == "Wi-Fi AP", self.rows))
    bridged = list(filter(lambda x: x["type"] == "Wi-Fi Bridged", self.rows))
    other = list(filter(lambda x: x["type"] not in ["Wi-Fi Client","Wi-Fi AP","Wi-Fi Bridged"], self.rows))

    self.clients = list(map(lambda x: self.parseClient(x), clients))
    self.aps = list(map(lambda x: self.parseAP(x), aps))
    self.bridged = list(map(lambda x: self.parseOther(x), bridged))
    self.other = list(map(lambda x: self.parseOther(x), other))

  def getLocationData(self, device_json):
    fields = {}
    fields["Locations"] = []
    locations = device_json["kismet.device.base.location_cloud"]
    if type(locations) is dict:
      maxdBm = -1000
      for loc in locations["kis.gps.rrd.samples_100"]:
          outputLoc = {
              "Latitude": loc["kismet.historic.location.lat"],
              "Longitude": loc["kismet.historic.location.lon"],
              "dBm": loc["kismet.historic.location.signal"]
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

  def getClientAPs(self,device_json):
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

  def getProbes(self, device_json):
    fields = {}
    fields["Probes"] = []
    row_probes = device_json["dot11.device"]["dot11.device.probed_ssid_map"]
    for probe in row_probes:
      if row_probes[probe]["dot11.probedssid.ssid"]:
        fields["Probes"].append({"SSID": row_probes[probe]["dot11.probedssid.ssid"]})
    return fields

  def parseAP(self, row):
    fields = {}
    device_json = json.loads(row["device"])
    print(json.dumps(device_json, indent=2))
    fields.update(self.getCommonFields(row, device_json))
    fields.update(self.getLocationData(device_json))
    
    fields["SSID"] = device_json["dot11.device"]["dot11.device.last_beaconed_ssid"]

    # Populate an array of client objects
    row_clients = device_json["dot11.device"]["dot11.device.associated_client_map"]
    fields["Clients"] = [{k:v} for k,v in row_clients.items()]

    for i, client in enumerate(fields["Clients"]):
      key = list(client.values())[0]
      matched = list(filter(lambda c: key == c["Key"] ,self.clients))
      if len(matched) > 0:
        # fields["Clients"][i] = matched[0]
        matchedClient = matched[0]
        fields["Clients"][i] = { "Key": key, "Device MAC": matchedClient["Device MAC"]}
      else:
        fields["Clients"][i] = { "Key": key, "Device MAC": list(client.keys())[0]}
    return fields

  def parseClient(self, row):
    fields = {}
    device_json = json.loads(row["device"])
    fields.update(self.getCommonFields(row, device_json))
    fields.update(self.getLocationData(device_json))
    fields.update(self.getClientAPs(device_json))
    fields.update(self.getProbes(device_json))
    return fields

  def parseOther(self, row):
    fields = {}
    device_json = json.loads(row["device"])
    fields.update(self.getCommonFields(row, device_json))
    fields.update(self.getLocationData(device_json))
    fields.update(self.getClientAPs(device_json))
    fields.update(self.getProbes(device_json))
    return fields

  def getCommonExtendedData(self, object):
    return KML.ExtendedData(
          KML.Data(KML.value(object["Device MAC"]), name="Device MAC"),
          KML.Data(KML.value(object["Type"]), name="Type"),
          KML.Data(KML.value(object["First Seen"]), name="First Seen"),
          KML.Data(KML.value(object["Last Seen"]), name="Last Seen"),
          KML.Data(KML.value(object["Channel"]), name="Channel")
    )

  def getPlacemark(self, object, style):
    return KML.Placemark(
          KML.name(object["Common Name"]),
          KML.styleUrl(style),
          KML.Point(KML.coordinates(object["Longitude"],",",object["Latitude"])),
        )

  def createKML(self):
    try:
      document = KML.kml(KML.Document())

      # Create an icon style for each Placemark to use
      document.Document.append(KML.Style(KML.IconStyle(KML.scale(1.0), KML.color('50B41E14'), KML.Icon(KML.href("http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png"),), id="blue_circle"), id="blue_circle"))
      document.Document.append(KML.Style(KML.IconStyle(KML.scale(1.0), KML.color('ff00C2ff'), KML.Icon(KML.href("http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png"),), id="amber_circle"), id="amber_circle"))
      document.Document.append(KML.Style(KML.IconStyle(KML.scale(1.0), KML.color('ff00ff00'), KML.Icon(KML.href("http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png"),), id="green_circle"), id="green_circle"))
      document.Document.append(KML.Style(KML.IconStyle(KML.scale(1.0), KML.color('501400FF'), KML.Icon(KML.href("http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png"),), id="red_circle"), id="red_circle"))

      for client in self.clients:
        if client["Locations"]:
          pm = self.getPlacemark(client, "#blue_circle")
          extData = self.getCommonExtendedData(client)
            
          for probe in client["Probes"]:
            extData.append(KML.Data(KML.value(probe["SSID"]), name="Probed SSID"))

          for i, ap in enumerate(client["APs"]):
            ssid = list(filter(lambda x: x["Key"] == ap["Key"], self.aps))[0]["SSID"]
            extData.append(KML.Data(KML.value(ssid), name="AP " + str(i) + " SSID"))
            extData.append(KML.Data(KML.value(ap["BSSID"]), name="AP " + str(i) + " BSSID"))

          pm.append(extData)
          document.Document.append(pm)

      for ap in self.aps:
        if ap["Locations"]:
          pm = self.getPlacemark(ap, "#green_circle")
          extData = self.getCommonExtendedData(ap)
          extData.append(KML.Data(KML.value(ap["SSID"]), name="SSID"))
            
          for client in ap["Clients"]:
            extData.append(KML.Data(KML.value(client["Device MAC"]), name="Client Device MAC"))

          pm.append(extData)
          document.Document.append(pm)
      
      for other in self.other:
        if other["Locations"]:
          pm = self.getPlacemark(other, "#red_circle")
          extData = self.getCommonExtendedData(other)

          for probe in other["Probes"]:
            extData.append(KML.Data(KML.value(probe["SSID"]), name="Probed SSID"))

          for i, ap in enumerate(other["APs"]):
            ssid = list(filter(lambda x: x["Key"] == ap["Key"], self.aps))[0]["SSID"]
            extData.append(KML.Data(KML.value(ssid), name="AP " + str(i) + " SSID"))
            extData.append(KML.Data(KML.value(ap["BSSID"]), name="AP " + str(i) + " BSSID"))

          pm.append(extData)
          document.Document.append(pm)

      for bridged in self.bridged:
        if bridged["Locations"]:
          pm = self.getPlacemark(bridged, "#amber_circle")
          extData = self.getCommonExtendedData(bridged)

          for probe in bridged["Probes"]:
            extData.append(KML.Data(KML.value(probe["SSID"]), name="Probed SSID"))

          for i, ap in enumerate(bridged["APs"]):
            ssid = list(filter(lambda x: x["Key"] == ap["Key"], self.aps))[0]["SSID"]
            extData.append(KML.Data(KML.value(ssid), name="AP " + str(i) + " SSID"))
            extData.append(KML.Data(KML.value(ap["BSSID"]), name="AP " + str(i) + " BSSID"))

          pm.append(extData)
          document.Document.append(pm)

      output = open(self.outputFile, "w")
      output.write(etree.tostring(document, pretty_print=True).decode())
      output.close()

    except TypeError as e:
      print(e)
      print("createKML: No data to export!")


# Set up command line arguments
parser = argparse.ArgumentParser(description="Generates a KML file from the output file of Kismet (2017 Development Version")

parser.add_argument('--input-file', '-i', required=True, type=str, help="Path to Kismet file. Usually a *.kismet file.")
parser.add_argument('--output-kml-file', '-k', required=True, type=str, help="Path to desired KML output file")
parser.add_argument('--output-json-file', '-j', required=True, type=str, help="Path to desired JSON output file")
args = parser.parse_args()

# Create a new instance of the Wigle class
kmlGen = KMLGen(args.input_file, args.output_kml_file, args.output_json_file)


