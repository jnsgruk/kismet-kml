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

    self.rows = []

    self.clients = []
    self.aps = []
    self.bridged = []

    self.getData()
    self.createKML()

  def getData(self):
    conn = sqlite3.connect(self.inputFile)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM devices")
    self.rows = c.fetchall()
    c.close()

  # ['first_time', 'last_time', 'phyname', 'devmac', 'strongest_signal', 'min_lat', 'min_lon', 'max_lat', 'max_lon', 'avg_lat', 'avg_lon', 'bytes_data', 'type', 'device']
  def createKML(self):
    try:
      document = KML.kml(KML.Document())

      # Create an icon style for each Placemark to use
      document.Document.append(
          KML.Style(KML.IconStyle(KML.scale(1.0), KML.color('50B41E14'), KML.Icon(
                      KML.href("http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png"),), id="blue_icon"), id="blue_circle"))
      document.Document.append(
          KML.Style(KML.IconStyle(KML.scale(1.0), KML.color('ff00C2ff'), KML.Icon(
                      KML.href("http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png"),), id="amber_icon"), id="amber_circle"))
      document.Document.append(
          KML.Style(KML.IconStyle(KML.scale(1.0), KML.color('ff00ff00'), KML.Icon(
                      KML.href("http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png"),), id="green_icon"), id="green_circle"))

      for row in self.rows:

        device_json = json.loads(row["device"])
        common_name = device_json["kismet.device.base.commonname"]
        channel = device_json["kismet.device.base.channel"]

        # IF TYPE = Wi-Fi AP
        #  SSID: device_json["dot11.device"][""dot11.device.last_beaconed_ssid""]

        style = "#blue_circle" if row["type"] == "Wi-Fi Client" else "#green_circle"

        if row["type"] == "Wi-Fi Client": self.clients.append(device_json)
        if row["type"] == "Wi-Fi AP": self.aps.append(device_json)
        if row["type"] == "Wi-Fi Bridged": self.bridged.append(device_json)

        pm = KML.Placemark(
          KML.name(common_name),
          KML.styleUrl(style),
          KML.Point(KML.coordinates(row["avg_lon"]/100000,",",row["avg_lat"]/100000)),
          KML.ExtendedData(
            KML.Data(KML.value(row["devmac"], name="Device MAC")),
            KML.Data(KML.value(channel, name="Channel")),
            KML.Data(KML.value(datetime.fromtimestamp(row["first_time"]), name="First Seen")),
            KML.Data(KML.value(datetime.fromtimestamp(row["last_time"]), name="Last Seen")),
            KML.Data(KML.value(row["type"], name="Type"))
          )
        )
        document.Document.append(pm)

      output = open(self.outputFile, "w")
      output.write(etree.tostring(document, pretty_print=True).decode())
      output.close()

      output_aps = open("output/aps.json", "w")
      output_aps.write(json.dumps(self.aps, sort_keys=True, indent=4))
      output_aps.close()

      output_clients = open("output/clients.json", "w")
      output_clients.write(json.dumps(self.clients, sort_keys=True, indent=4))
      output_clients.close()

      output_bridged = open("output/bridged.json", "w")
      output_bridged.write(json.dumps(self.bridged, sort_keys=True, indent=4))
      output_bridged.close()

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


