import sqlite3
import argparse
from datetime import datetime
from lxml import etree
from pykml.factory import KML_ElementMaker as KML
import json 

class KMLGen():

  def __init__(self, inputFile, outputFile):
    self.inputFile = inputFile
    self.outputFile = outputFile

    self.debug = True 
    
    self.rows = []

    self.clients = []
    self.aps = []
    self.bridged = []
    self.other = []

    self.getData()
    self.parseData()
    

    # self.createKML()

  def getData(self):
    conn = sqlite3.connect(self.inputFile)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM devices")
    self.rows = c.fetchall()
    c.close()

  # ['first_time', 'last_time', 'phyname', 'devmac', 'strongest_signal', 'min_lat', 'min_lon', 'max_lat', 'max_lon', 'avg_lat', 'avg_lon', 'bytes_data', 'type', 'device']

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

    fields["Clients"] = []
    row_clients = device_json["dot11.device"]["dot11.device.associated_client_map"]
    for client in row_clients:
      fetched = list(filter(lambda x: x["Key"] == row_clients[client], self.clients))
      fields["Clients"] = fetched

    # 
    # 
    # CHECK THE CLIENTS SECTION ABOVE WORKS
    # 
    # 
      
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

  # 
  # 
  #  CHECK THIS WORKS
  # 
  # 
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
  # 
  # 
  #  CHECK THIS WORKS
  # 
  # 
  def parseData(self):
    clients = list(filter(lambda x: x["type"] == "Wi-Fi Client", self.rows))
    aps = list(filter(lambda x: x["type"] == "Wi-Fi AP", self.rows))
    bridged = list(filter(lambda x: x["type"] == "Wi-Fi Bridged", self.rows))
    other = list(filter(lambda x: x["type"] not in ["Wi-Fi Client","Wi-Fi AP""Wi-Fi Bridged"], self.rows))

    self.clients = list(map(lambda x: self.parseClient(x), clients))
    self.aps = list(map(lambda x: self.parseAP(x), aps))
    self.bridged = list(map(lambda x: self.parseOther(x), bridged))
    self.other = list(map(lambda x: self.parseOther(x), other))
    # print(json.dumps(self.clients))
    # print()
    # print(json.dumps(self.aps))
    # print()
    # print(json.dumps(self.bridged))
    # print()
    # print(json.dumps(self.other))

  def createKML(self):
    try:
      document = KML.kml(KML.Document())

      # Create an icon style for each Placemark to use
      document.Document.append(KML.Style(KML.IconStyle(KML.scale(1.0), KML.color('50B41E14'), KML.Icon(KML.href("http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png"),), id="blue_icon"), id="blue_circle"))
      document.Document.append(KML.Style(KML.IconStyle(KML.scale(1.0), KML.color('ff00C2ff'), KML.Icon(KML.href("http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png"),), id="amber_icon"), id="amber_circle"))
      document.Document.append(KML.Style(KML.IconStyle(KML.scale(1.0), KML.color('ff00ff00'), KML.Icon(KML.href("http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png"),), id="green_icon"), id="green_circle"))

      for row in self.rows:
        fields = {}
        device_json = json.loads(row["device"])
        
        fields["Common Name"] = device_json["kismet.device.base.commonname"]
        fields["Channel"] = device_json["kismet.device.base.channel"]

        # IF TYPE = Wi-Fi AP
        #  SSID: device_json["dot11.device"][""dot11.device.last_beaconed_ssid""]

        style = "#blue_circle" if row["type"] == "Wi-Fi Client" else "#green_circle"

        pm = KML.Placemark(
          KML.name(common_name),
          KML.styleUrl(style),
          KML.Point(KML.coordinates(row["avg_lon"]/100000,",",row["avg_lat"]/100000)),
          KML.ExtendedData(
            KML.Data(KML.value(row["devmac"], name="Device MAC"))
            # 
            # 
            # LOOP OVER ATTRIBUTES HERE
            # 
            # 
          )
        )
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
parser.add_argument('--output-file', '-o', required=True, type=str, help="Path to desired KML output file")
args = parser.parse_args()

# Create a new instance of the Wigle class
kmlGen = KMLGen(args.input_file, args.output_file)


