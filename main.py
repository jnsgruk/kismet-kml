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

    self.debug = True 
    
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
    output.write(json.dumps(jsonOut))
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
    other = list(filter(lambda x: x["type"] not in ["Wi-Fi Client","Wi-Fi AP""Wi-Fi Bridged"], self.rows))

    self.clients = list(map(lambda x: self.parseClient(x), clients))
    self.aps = list(map(lambda x: self.parseAP(x), aps))
    self.bridged = list(map(lambda x: self.parseOther(x), bridged))
    self.other = list(map(lambda x: self.parseOther(x), other))

  def parseAP(self, row):
    fields = {}
    device_json = json.loads(row["device"])
    fields["Type"] = row["type"]
    fields["Average Longitude"] = row["avg_lon"]/100000
    fields["Average Latitude"] = row["avg_lat"]/100000
    fields["First Seen"] = str(datetime.fromtimestamp(row["first_time"]))
    fields["Last Seen"] = str(datetime.fromtimestamp(row["last_time"]))
    fields["Device MAC"] = row["devmac"]
    fields["Common Name"] = device_json["kismet.device.base.commonname"]
    fields["Channel"] = device_json["kismet.device.base.channel"]
    fields["Key"] = device_json["kismet.device.base.key"]
    fields["SSID"] = device_json["dot11.device"]["dot11.device.last_beaconed_ssid"]

    # Populate an array of client objects
    row_clients = device_json["dot11.device"]["dot11.device.associated_client_map"]
    fields["Clients"] = [{k:v} for k,v in row_clients.items()]

    for i, client in enumerate(fields["Clients"]):
      key = list(client.values())[0]
      matched = list(filter(lambda c: key == c["Key"] ,self.clients))
      if len(matched) > 0:
        fields["Clients"][i] = matched[0]
      else:
        fields["Clients"][i] = { "Key": key, "Device MAC": list(client.keys())[0]}
    
    #  Add fields["Locations"] and capture all location instances
    return fields

  def parseClient(self, row):
    fields = {}
    device_json = json.loads(row["device"])
    fields["Type"] = row["type"]
    fields["Average Longitude"] = row["avg_lon"]/100000
    fields["Average Latitude"] = row["avg_lat"]/100000
    fields["First Seen"] = str(datetime.fromtimestamp(row["first_time"]))
    fields["Last Seen"] = str(datetime.fromtimestamp(row["last_time"]))
    fields["Device MAC"] = row["devmac"]
    fields["Common Name"] = device_json["kismet.device.base.commonname"]
    fields["Channel"] = device_json["kismet.device.base.channel"]
    fields["Key"] = device_json["kismet.device.base.key"]

    fields["Probes"] = []
    row_probes = device_json["dot11.device"]["dot11.device.probed_ssid_map"]
    for probe in row_probes:
      if row_probes[probe]["dot11.probedssid.ssid"]:
        fields["Probes"].append({"SSID": row_probes[probe]["dot11.probedssid.ssid"]})
    #  Add fields["Locations"] and capture all location instances
    return fields


  def parseOther(self, row):
    fields = {}
    device_json = json.loads(row["device"])
    fields["Type"] = row["type"]
    fields["Average Longitude"] = row["avg_lon"]/100000
    fields["Average Latitude"] = row["avg_lat"]/100000
    fields["First Seen"] = str(datetime.fromtimestamp(row["first_time"]))
    fields["Last Seen"] = str(datetime.fromtimestamp(row["last_time"]))
    fields["Device MAC"] = row["devmac"]
    fields["Common Name"] = device_json["kismet.device.base.commonname"]
    fields["Channel"] = device_json["kismet.device.base.channel"]
    fields["Key"] = device_json["kismet.device.base.key"]

    #  Add fields["Locations"] and capture all location instances
    return fields

  def createKML(self):
    try:
      document = KML.kml(KML.Document())

      # Create an icon style for each Placemark to use
      document.Document.append(KML.Style(KML.IconStyle(KML.scale(1.0), KML.color('50B41E14'), KML.Icon(KML.href("http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png"),), id="blue_circle"), id="blue_circle"))
      document.Document.append(KML.Style(KML.IconStyle(KML.scale(1.0), KML.color('ff00C2ff'), KML.Icon(KML.href("http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png"),), id="amber_circle"), id="amber_circle"))
      document.Document.append(KML.Style(KML.IconStyle(KML.scale(1.0), KML.color('ff00ff00'), KML.Icon(KML.href("http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png"),), id="green_circle"), id="green_circle"))

      for client in self.clients:
        style = "#blue_circle"
        pm = KML.Placemark(
          KML.name(client["Common Name"]),
          KML.styleUrl(style),
          KML.Point(KML.coordinates(client["Average Longitude"],",",client["Average Latitude"])),
        )
        
        extData = KML.ExtendedData(
          KML.Data(KML.value(client["Device MAC"], name="Device MAC")),
          KML.Data(KML.value(client["First Seen"], name="First Seen")),
          KML.Data(KML.value(client["Last Seen"], name="Last Seen")),
          KML.Data(KML.value(client["Channel"], name="Channel"))
        )
          
        for probe in client["Probes"]:
          extData.append(KML.Data(KML.value(probe["SSID"], name="Probed SSID")))

        pm.append(extData)
        document.Document.append(pm)

      for ap in self.aps:
        style = "#green_circle"
        pm = KML.Placemark(
          KML.name(ap["Common Name"]),
          KML.styleUrl(style),
          KML.Point(KML.coordinates(ap["Average Longitude"],",",ap["Average Latitude"])),
        )
        
        extData = KML.ExtendedData(
          KML.Data(KML.value(ap["Device MAC"], name="Device MAC")),
          KML.Data(KML.value(ap["First Seen"], name="First Seen")),
          KML.Data(KML.value(ap["Last Seen"], name="Last Seen")),
          KML.Data(KML.value(ap["Channel"], name="Channel")),
          KML.Data(KML.value(ap["SSID"], name="SSID"))
        )
          
        for client in ap["Clients"]:
          extData.append(KML.Data(KML.value(client["Device MAC"], name="Client Device MAC")))

        pm.append(extData)
        document.Document.append(pm)

      for other in self.other:
        style = "#amber_circle"
        pm = KML.Placemark(
          KML.name(other["Common Name"]),
          KML.styleUrl(style),
          KML.Point(KML.coordinates(other["Average Longitude"],",",other["Average Latitude"])),
        )
        
        extData = KML.ExtendedData(
          KML.Data(KML.value(other["Device MAC"], name="Device MAC")),
          KML.Data(KML.value(other["First Seen"], name="First Seen")),
          KML.Data(KML.value(other["Last Seen"], name="Last Seen")),
          KML.Data(KML.value(other["Channel"], name="Channel"))
        )

        pm.append(extData)
        document.Document.append(pm)

      for bridged in self.bridged:
        style = "#amber_circle"
        pm = KML.Placemark(
          KML.name(bridged["Common Name"]),
          KML.styleUrl(style),
          KML.Point(KML.coordinates(bridged["Average Longitude"],",",bridged["Average Latitude"])),
        )
        
        extData = KML.ExtendedData(
          KML.Data(KML.value(bridged["Device MAC"], name="Device MAC")),
          KML.Data(KML.value(bridged["First Seen"], name="First Seen")),
          KML.Data(KML.value(bridged["Last Seen"], name="Last Seen")),
          KML.Data(KML.value(bridged["Channel"], name="Channel"))
        )

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


