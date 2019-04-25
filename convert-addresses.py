#!/usr/bin/env python3
# -*- coding: utf-8 -*-

info = """The idea for this script originates from
https://github.com/BergWerkGIS/convert-bev-address-data/blob/master/README.md

The input are the various csv files from the publicly available dataset of 
addresses of Austria, available for download at
http://www.bev.gv.at/portal/page?_pageid=713,1604469&_dad=portal&_schema=PORTAL

This script will attempt to download the data necessary automatically.
The output will be named "bev_addressesEPSGxxxx.csv".
"""

requestsModule = False
osgeoModule = False
pyprojModule = False
arcpyModule = False

from collections import defaultdict
import time
print( time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) )
import sys
import csv
import argparse
try:
    import requests
    requestsModule = True
except ImportError:
    print("- no module named requests, automatic download of data is deactivated\n")
import os.path
import xml.etree.cElementTree as ET
import operator
import zipfile
try:
    from osgeo import osr
    from osgeo import ogr
    osgeoModule = True
except ImportError:
    print("- no osgeo module for coordinate transformation found, trying to load pyproj module instead ...")
    try:
        import pyproj
        arcpyModule = True
    except ImportError:
        print("- no pyproj module for coordinate transformation found, trying to load ArcPy module instead ...")
        try:
            import arcpy
            arcpyModule = True
        except ImportError:
            print("- No arcpy module is present. Coordinate transformation requires either the free OsGeo module or ArcGis >= 10 to be installed.")
            print("quitting.")
            quit()

# command line arguments are evaluated
parser = argparse.ArgumentParser(prog='python3 convert-addresses.py')
parser.add_argument('-epsg', type=int, default=3035, dest='epsg',
                    help='Specify the EPSG code of the coordinate  system used for the results. If none is given, this value defaults to EPSG:3035')
parser.add_argument('-sort', default=None, dest='sort',
                    help='Specify if and by which fields the output should be sorted (possible values: gemeinde, plz, strasse, nummer, hausname, x, y, gkz).')
parser.add_argument('-compatibility_mode', action='store_true', dest='compatibility_mode',
                    help='''Compatiblity mode for bev-reverse-geocoder with only one entry per address. In case of addresses with exactly one building, 
                        the building position is taken, otherwise the address position (more precisely the building position replaces the column, 
                        where bev-reverse-geocoder expected the former single position and in case of no/multiple buildings it's set equal to the address location).''')
parser.add_argument('-output_format', default='csv', dest='output_format',
                    help='''Specify the output format. Either csv (default) or osm. If osm is chosen, the arguments above (epsg, sort, compatibility_mode) are ignored.''')
parser.add_argument('-here_be_dragons', action='store_true', dest='here_be_dragons',
                    help='''Include entries that would otherwise be filtered because they are most likely unimportant or even downright false.''')
parser.add_argument('-only_notes', action='store_true', dest='only_notes',
                    help='''Only output entries that have either a "Hofname" or a "Gebäudebezeichnung"''')
parser.add_argument('-debug', action='store_true', dest='debug',
                    help='''Return ALL coordinates to an address with annotations coded directly into the housenumber''')
args = parser.parse_args()

if args.output_format == 'osm':
    args.epsg = 4326
    args.sort = 'gkz,okz,plz,strasse,adrcd'
    args.compatibility_mode = False

# the target EPSG is set according to the argument
if not arcpyModule:
    # for OsGeo
    targetRef = osr.SpatialReference()
    targetRef.ImportFromEPSG(args.epsg)

    westRef = osr.SpatialReference()
    westRef.ImportFromEPSG(31254)
    centerRef = osr.SpatialReference()
    centerRef.ImportFromEPSG(31255)
    eastRef = osr.SpatialReference()
    eastRef.ImportFromEPSG(31256)

    westTransform = osr.CoordinateTransformation(westRef, targetRef)
    centralTransform = osr.CoordinateTransformation(centerRef, targetRef)
    eastTransfrom = osr.CoordinateTransformation(eastRef, targetRef)

else:
    # for ArcPy
    arcTargetRef = arcpy.SpatialReference(args.epsg)

    arcWestRef = arcpy.SpatialReference(31254)
    arcCenterRef = arcpy.SpatialReference(31255)
    arcEastRef = arcpy.SpatialReference(31256)

BUNDESLAND = {
    "1": "Burgenland",
    "2": "Kärnten",
    "3": "Niederösterreich",
    "4": "Oberösterreich",
    "5": "Salzburg",
    "6": "Steiermark",
    "7": "Tirol",
    "8": "Vorarlberg",
    "9": "Wien"
}

BEZIRK = {
    "101": "Eisenstadt-Stadt",
    "102": "Rust-Stadt",
    "103": "Eisenstadt-Umgebung",
    "104": "Güssing",
    "105": "Jennersdorf",
    "106": "Mattersburg",
    "107": "Neusiedl_am_See",
    "108": "Oberpullendorf",
    "109": "Oberwart",
    "201": "Klagenfurt-Stadt",
    "202": "Villach-Stadt",
    "203": "Hermagor",
    "204": "Klagenfurt-Land",
    "205": "St.Veit_Glan",
    "206": "Spittal_Drau",
    "207": "Villach-Land",
    "208": "Völkermarkt",
    "209": "Wolfsberg",
    "210": "Feldkirchen",
    "301": "Krems-Stadt",
    "302": "St.Pölten-Stadt",
    "303": "Waidhofen_Ybbs-Stadt",
    "304": "Wr.Neustadt-Stadt",
    "305": "Amstetten",
    "306": "Baden",
    "307": "Bruck_Leitha",
    "308": "Gänserndorf",
    "309": "Gmünd",
    "310": "Hollabrunn",
    "311": "Horn",
    "312": "Korneuburg",
    "313": "Krems-Land",
    "314": "Lilienfeld",
    "315": "Melk",
    "316": "Mistelbach",
    "317": "Mödling",
    "318": "Neunkirchen",
    "319": "St.Pölten-Land",
    "320": "Scheibbs",
    "321": "Tulln",
    "322": "Waidhofen_Thaya",
    "323": "Wr.Neustadt-Land",
    "325": "Zwettl",
    "401": "Linz-Stadt",
    "402": "Stayr-Stadt",
    "403": "Wels-Stadt",
    "404": "Braunau_Inn",
    "405": "Eferding",
    "406": "Freistadt",
    "407": "Gmunden",
    "408": "Grieskirchen",
    "409": "Kirchdorf_Krems",
    "410": "Linz-Land",
    "411": "Perg",
    "412": "Ried_Innkreis",
    "413": "Rohrbach",
    "414": "Schärding",
    "415": "Steyr-Land",
    "416": "Urfahr-Umgebung",
    "417": "Vöcklabruck",
    "418": "Wels-Land",
    "501": "Salzburg-Stadt",
    "502": "Hallein",
    "503": "Salzburg-Umgebung",
    "504": "St.Johann_Pongau",
    "505": "Tamsweg",
    "506": "Zell_am_See",
    "601": "Graz-Stadt",
    "603": "Deutschlandsberg",
    "606": "Graz-Umgebung",
    "610": "Leibnitz",
    "611": "Leoben",
    "612": "Liezen",
    "614": "Murau",
    "616": "Voitsberg",
    "617": "Weiz",
    "620": "Murtal",
    "621": "Bruck-Mürzzuschlag",
    "622": "Hartberg-Fürstenfeld",
    "623": "Südoststeiermark",
    "701": "Innsbruck-Stadt",
    "702": "Imst",
    "703": "Innsbruck-Land",
    "704": "Kitzbühel",
    "705": "Kufstein",
    "706": "Landeck",
    "707": "Lienz",
    "708": "Reutte",
    "709": "Schwaz",
    "801": "Bludenz",
    "802": "Bregenz",
    "803": "Dornbirn",
    "804": "Feldkirch",
    "900": "Wien-Stadt",
    "901": "01-Innere_Stadt",
    "902": "02-Leopoldstadt",
    "903": "03-Landstraße",
    "904": "04-Wieden",
    "905": "05-Margareten",
    "906": "06-Mariahilf",
    "907": "07-Neubau",
    "908": "08-Josefstadt",
    "909": "09-Alsergrund",
    "910": "10-Favoriten",
    "911": "11-Simmering",
    "912": "12-Meidling",
    "913": "13-Hietzing",
    "914": "14-Penzing",
    "915": "15-Rudolfsheim-Fünfhaus",
    "916": "16-Ottakring",
    "917": "17-Hernals",
    "918": "18-Währing",
    "919": "19-Döbling",
    "920": "20-Brigittenau",
    "921": "21-Floridsdorf",
    "922": "22-Donaustadt",
    "923": "23-Liesing"
}

class CsvWriter():
    def __init__(self, output_filename, header_row):
        if args.compatibility_mode:
            directory = "./"
        else:
            directory = "results/"
            if not os.path.isdir(directory):
                os.makedirs(directory)
        self.address_writer = csv.DictWriter(open(os.path.join(directory, output_filename), 'w'), header_row, delimiter=";", quotechar='"')
        self.address_writer.writeheader()

    def add_address(self, address):
        self.address_writer.writerow(address)

    def close(self):
        self.address_writer = None

class OsmWriter():
    def __init__(self):
        self._current_id = 0
        self._current_postcode = None
        self._current_gkz = None
        self._current_locality = None
        self._current_district = None
        self._current_street = None
        self.root = None
        self._bev_date = self._get_addr_date()
        self._min_lat = None
        self._max_lat = None
        self._min_lon = None
        self._max_lon = None

    def _get_addr_date(self):
        z = zipfile.ZipFile('Adresse_Relationale_Tabellen-Stichtagsdaten.zip', 'r')
        for f in z.infolist():
            if f.filename == 'ADRESSE.csv':
                return "%d-%02d-%02d" % f.date_time[:3]

    def add_address(self, address):
        #if self._current_locality != address["ortschaft"].lower() or self._current_postcode != address["plz"]:
        if self._current_street != address["strasse"].lower():
            if self.root != None:
                self.close()
            self._current_gkz = address["gkz"]
            self._current_postcode = address["plz"]
            self._current_locality = address["ortschaft"].lower()
            self._current_district = address["gemeinde"].lower()
            self._current_street = address["strasse"].lower()
            self.root = ET.Element("osm", version="0.6", generator="convert-addresses.py", upload="never", locked="true")
        if "haus_x" in address and str(address["haus_x"]).strip() != "":
            lat = float(address["haus_y"])
            lon = float(address["haus_x"])
        else:
            lat = float(address["adress_y"])
            lon = float(address["adress_x"])
        if self._min_lat is None:
            self._min_lat = lat
            self._max_lat = lat
            self._min_lon = lon
            self._max_lon = lon
        else:
            if lat < self._min_lat:
                self._min_lat = lat
            elif lat > self._max_lat:
                self._max_lat = lat
            if lon < self._min_lon:
                self._min_lon = lon
            elif lon > self._max_lon:
                self._max_lon = lon
        node = ET.SubElement(self.root, "node", id=self._get_id(address), lat=str(lat), lon=str(lon))
        ET.SubElement(node, "tag", k="addr:country", v="AT")
        ET.SubElement(node, "tag", k="at_bev:addr_date", v=self._bev_date)
        
        ET.SubElement(node, "tag", k="addr:postcode", v=address["plz"])
        streetname = address["strasse"]
        if streetname.lower().endswith("str."):
            streetname = streetname[:-1] + "aße"
        ortschaft = address["ortschaft"]
        if address["strasse"] == ortschaft:
            ET.SubElement(node, "tag", k="addr:place", v=streetname)
        else:
            ET.SubElement(node, "tag", k="addr:street", v=streetname)
        index_comma = ortschaft.find(",")
        if index_comma > -1:
            if ortschaft.startswith("Wien"):
                ET.SubElement(node, "tag", k="addr:suburb", v=ortschaft[index_comma+1:])
            elif ortschaft.startswith("Graz") or ortschaft.startswith("Klagenfurt"):
                ET.SubElement(node, "tag", k="addr:suburb", v=ortschaft[index_comma+9:])
            ortschaft = ortschaft[:index_comma]
        if address["strassenname_mehrdeutig"]:
            ET.SubElement(node, "tag", k="addr:suburb", v=ortschaft)
        ET.SubElement(node, "tag", k="addr:city", v=address["gemeinde"])
        ET.SubElement(node, "tag", k="addr:housenumber", v=address["hausnummer"])
        if "subadresse" in address and address["subadresse"].strip() != "":
            ET.SubElement(node, "tag", k="addr:unit", v=address["subadresse"])
        if args.here_be_dragons or args.only_notes:
            notes = []
            if "haus_bez" in address and address["haus_bez"].strip() != "":
                notes.append(address["haus_bez"])
            if "hausname" in address and address["hausname"].strip() != "":
                notes.append(address["hausname"])
            if len(notes) > 0:
                ET.SubElement(node, "tag", k="note", v=";".join(notes))

    def close(self):
        ET.SubElement(self.root, "bounds", minlat=str(self._min_lat), minlon=str(self._min_lon), maxlat=str(self._max_lat), maxlon=str(self._max_lon))
        self._min_lat = None
        self._max_lat = None
        self._min_lon = None
        self._max_lon = None
        self._format()
        tree = ET.ElementTree(self.root)
        district = "".join(c for c in self._current_district if c.isalnum())
        locality = "".join(c for c in self._current_locality if c.isalnum())
        federal_state = BUNDESLAND[self._current_gkz[0]]
        if federal_state == "Wien":
            directory = "results/{datum}/{bundesland}/{ortschaft}".format(
                datum = self._bev_date,
                bundesland = federal_state,
                ortschaft = locality)
        else:
            directory = "results/{datum}/{bundesland}/Bezirk_{bezirk}/gemeinde_{gemeinde}/{ortschaft}".format(
                datum = self._bev_date,
                bundesland = federal_state,
                bezirk = BEZIRK[self._current_gkz[:3]],
                gemeinde = district,
                ortschaft = locality)
        if not os.path.isdir(directory):
            os.makedirs(directory)
        if args.here_be_dragons:
            prefix = "DRAGONS_"
        elif args.only_notes:
            prefix = "NOTES_"
        else:
            prefix = ""
        self.output_filename = "%s%s_%s_%s_(%s).osm" % (
            prefix,
            "".join(c for c in self._current_street if c.isalnum()),
            self._current_postcode, 
            locality,
            district
        )
        tree.write(os.path.join(directory, self.output_filename), encoding="utf-8", xml_declaration=True)

    def _format(self):
        self.root.text = "\n"
        for node in self.root.getchildren():
            node.tail = "\n"

    def _get_id(self, address):
        return "-%s%s" % (address["adrcd"], address["subcd"])

class ProgressBar():
    def __init__(self, message=None):
        self.percentage = 0
        if message:
            print(message)
    
    def update(self, new_percentage):
        new_percentage = round(new_percentage, 2)
        if new_percentage != self.percentage:
            sys.stdout.write("\r{} %   ".format(str(new_percentage).ljust(6)))
            sys.stdout.write('[{}]'.format(('#' * int(new_percentage / 2)).ljust(50)))
            sys.stdout.flush()
        self.percentage = new_percentage

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.update(100)
        sys.stdout.write("\n")

def download_data():
    """This function downloads the address data from BEV and displays its terms
    of usage"""

    if not requestsModule:
        print("source data missing and download is deactivated")
        quit()
    addressdataUrl = "http://www.bev.gv.at/pls/portal/docs/PAGE/BEV_PORTAL_CONTENT_ALLGEMEIN/0200_PRODUKTE/UNENTGELTLICHE_PRODUKTE_DES_BEV/Adresse_Relationale_Tabellen-Stichtagsdaten.zip"
    response = requests.get(addressdataUrl, stream=True)
    with open(addressdataUrl.split('/')[-1], 'wb') as handle, ProgressBar("downloading address data from BEV") as pb:
        for i, data in enumerate(response.iter_content(chunk_size=1000000)):
            handle.write(data)
            current_percentage = i * 1.3
            pb.update(current_percentage)


def reproject(sourceCRS, point):
    """This function reprojects an array of coordinates (a point) to the desired CRS
    depending on their original CRS given by the parameter sourceCRS"""

    if not arcpyModule:
        # if using OsGeo
        #point = ogr.CreateGeometryFromWkt("POINT (" + str(point[0]) + " " + str(point[1]) + ")")
        point = ogr.CreateGeometryFromWkt("POINT ({} {})".format(point[0], point[1]))
        if sourceCRS == '31254':
            point.Transform(westTransform)
        elif sourceCRS == '31255':
            point.Transform(centralTransform)
        elif sourceCRS == '31256':
            point.Transform(eastTransfrom)
        else:
            print("unkown CRS: {}".format(sourceCRS))
            return([0, 0])
        wktPoint = point.ExportToWkt()
        transformedPoint = wktPoint.split("(")[1][:-1].split(" ")
        del(point)
    
    elif pyprojModule:
        # use pyproj
        print("coordinate transformation with pyproj is not yet implemented")
        quit()
        
    else:
        # if using ArcPy
        point = [float(x) for x in point]
        arcPoint = arcpy.Point(point[0],point[1])
        if sourceCRS == '31254':
            arcPointSourceCRS = arcpy.SpatialReference(31254)
        elif sourceCRS == '31255':
            arcPointSourceCRS = arcpy.SpatialReference(31255)
        elif sourceCRS == '31256':
            arcPointSourceCRS = arcpy.SpatialReference(31256)
        else:
            print("unkown CRS: {}".format(sourceCRS))
            return([0, 0])
        arcPointGeo = arcpy.PointGeometry(arcPoint, arcPointSourceCRS)
        arcPointTargetGeo = arcPointGeo.projectAs(arcTargetRef)
        arcTargetPoint = arcPointTargetGeo.lastPoint
        transformedPoint = [arcTargetPoint.X, arcTargetPoint.Y]
        del(arcPointGeo)
        del(arcPointTargetGeo)
        del(arcTargetPoint)
        del(arcPoint)

    return [round(float(p), 6) for p in transformedPoint]
        

def build_housenumber(hausnrzahl1, hausnrbuchstabe1, hausnrverbindung1, hausnrzahl2, hausnrbuchstabe2, hausnrbereich):
    """This function takes all the different single parts of the input file
    that belong to the house number and combines them into one single string"""

    hausnr1 = hausnrzahl1
    hausnr2 = hausnrzahl2
    compiledHausNr = ""
    if hausnrbuchstabe1 != "": hausnr1 += hausnrbuchstabe1
    if hausnrbuchstabe2 != "": hausnr2 += hausnrbuchstabe2
    if hausnrverbindung1 != "":
        compiledHausNr = hausnr1 + hausnrverbindung1 + hausnr2
    elif hausnr2 != "":
        compiledHausNr = hausnr1 + " " + hausnr2
    else:
        compiledHausNr = hausnr1
    #if hausnrbereich != "keine Angabe": compiledHausNr += ", {}".format(hausnrbereich)
    return compiledHausNr

def build_sub_housenumber(hausnrzahl3, hausnrbuchstabe3, hausnrverbindung2, hausnrzahl4, hausnrbuchstabe4, hausnrverbindung3):
    """This function takes all the different single parts of the input file
    that belong to the sub address and combines them into one single string"""

    hausnr3 = hausnrzahl3
    hausnr4 = hausnrzahl4
    compiledHausNr = ""
    if hausnrbuchstabe3 != "": hausnr3 += hausnrbuchstabe3
    if hausnrbuchstabe4 != "": hausnr4 += hausnrbuchstabe4
    # ignore hausnrverbindung2
    if hausnrverbindung3 in ["", "-", "/"]:
        compiledHausNr = hausnr3 + hausnrverbindung3 + hausnr4
    else:
        compiledHausNr = hausnr3 +" "+ hausnrverbindung3 +" "+ hausnr4
    return compiledHausNr


def preparations():
    """check for necessary files and issue downloads when necessary"""
    csv_files = ["STRASSE.csv", "GEMEINDE.csv", "ADRESSE.csv", "GEBAEUDE.csv", "ORTSCHAFT.csv"]
    if not all(os.path.isfile(csv) for csv in csv_files):
        # ckeck if the packed version exists
        if not os.path.isfile('Adresse_Relationale_Tabellen-Stichtagsdaten.zip'):
            # if not, download it
            download_data()
        with zipfile.ZipFile('Adresse_Relationale_Tabellen-Stichtagsdaten.zip', 'r') as myzip:
            for csv in csv_files:
                print("extracting %s" % csv)
                myzip.extract(csv)
    return True

''' strips whitespace/dash, ß->ss, ignore case '''
def normalize_streetname(street):
    s = street.replace("ß", "ss").replace(" ", "").replace("-", "").lower()
    if s.endswith("str.") or s.endswith("g."):
        s = s[:-1] + "asse"
    return s

if __name__ == '__main__':
    print('#' * 40)
    print(info)
    print('#' * 40 + '\n')
    
    if not preparations() == True:
        print("There was an error")
        quit()

    output_header_row = ['gemeinde', 'ortschaft', 'plz', 'strasse', 'strassenzusatz', 'hausnrtext', 'hausnummer', 'hausname', 'haus_x', 'haus_y', 'gkz', 'adress_x', 'adress_y', 'subadresse', 'haus_bez', 'adrcd', 'subcd', 'okz', 'strassenname_mehrdeutig']
    if args.sort != None:
        for s in args.sort.split(","):
            if s not in output_header_row:
                print("\n##### ERROR ##### \nSort parameter is not allowed. Use one (or mulitple separated by ',') of %s" % output_header_row)
                quit()

    print("buffering localities ...")
    try:
        localityReader = csv.DictReader(open('ORTSCHAFT.csv', 'r', encoding='UTF-8-sig'), delimiter=';', quotechar='"')
    except IOError:
        print(
            "\n##### ERROR ##### \nThe file 'ORTSCHAFT.csv' was not found. Please download and unpack the BEV Address data from http://www.bev.gv.at/portal/page?_pageid=713,1604469&_dad=portal&_schema=PORTAL")
        quit()
    localities = {}
    for localityrow in localityReader:
        localities[localityrow['OKZ']] = localityrow['ORTSNAME']

    print("buffering districts ...")
    try:
        districtReader = csv.DictReader(open('GEMEINDE.csv', 'r', encoding='UTF-8-sig'), delimiter=';', quotechar='"')
    except IOError:
        print("\n##### ERROR ##### \nThe file 'GEMEINDE.csv' was not found. Please download and unpack the BEV Address data from http://www.bev.gv.at/portal/page?_pageid=713,1604469&_dad=portal&_schema=PORTAL")
        quit()
    districts = {}
    for districtrow in districtReader:
        districts[districtrow['GKZ']] = districtrow['GEMEINDENAME']
    print("GKZ overall: ", len(districts))

    print("buffering streets ...")
    try:
        streetReader = csv.DictReader(open('STRASSE.csv', 'r', encoding='UTF-8-sig'), delimiter=';', quotechar='"')
    except IOError:
        print("\n##### ERROR ##### \nThe file 'STRASSE.csv' was not found. Please download and unpack the BEV Address data from http://www.bev.gv.at/portal/page?_pageid=713,1604469&_dad=portal&_schema=PORTAL")
        quit()
    streets = {}
    gkz_streets = defaultdict(list)
    gkz_has_ambiguous_streetnames = defaultdict(bool)
    ambiguous_streetnames = defaultdict(list)
    okz_has_ambiguous_streetnames = defaultdict(bool)
    for streetrow in streetReader:
        streetname = streetrow['STRASSENNAME'].strip()
        streets[streetrow['SKZ']] = [streetname, streetrow['STRASSENNAMENZUSATZ']]
        gkz = streetrow['GKZ']
        if normalize_streetname(streetname) in gkz_streets[gkz]:
            gkz_has_ambiguous_streetnames[gkz] = True
            ambiguous_streetnames[gkz].append(normalize_streetname(streetname))
        else:
            gkz_streets[gkz].append(normalize_streetname(streetname))
    print("GKZ with ambiguous streetnames: ", len(gkz_has_ambiguous_streetnames))

    try:
        addressReader = csv.DictReader(open('ADRESSE.csv', 'r', encoding='UTF-8-sig'), delimiter=';', quotechar='"')
    except IOError:
        print("\n##### ERROR ##### \nThe file 'ADRESSE.csv' was not found. Please download and unpack the BEV Address data from http://www.bev.gv.at/portal/page?_pageid=713,1604469&_dad=portal&_schema=PORTAL")
        quit()
    outputFilename = "bev_addressesEPSG{}.{}".format(args.epsg, args.output_format)

    # get the total file size for status output
    total_addresses = sum(1 for row in open('ADRESSE.csv', 'r'))
    with ProgressBar("processing addresses ...") as pb:
        addresses = {}
        buildings = {}
        for i, reader_row in enumerate(addressReader):
            current_percentage = float(i) / total_addresses * 100
            pb.update(current_percentage)

            x = reader_row["RW"]
            y = reader_row["HW"]
            # some entries don't have coordinates: ignore these entries
            if x == '' or y == '':
                continue
            usedprojection = reader_row["EPSG"]
            coords = reproject(usedprojection, [x, y])
            # if the reprojection returned [0,0], this indicates an error: ignore these entries
            if coords[0] == '0' or coords[1] == '0':
                continue
            
            address_id = reader_row["ADRCD"]
            housenumber = build_housenumber(reader_row["HAUSNRZAHL1"], 
                        reader_row["HAUSNRBUCHSTABE1"],
                        reader_row["HAUSNRVERBINDUNG1"],
                        reader_row["HAUSNRZAHL2"],
                        reader_row["HAUSNRBUCHSTABE2"],
                        reader_row["HAUSNRBEREICH"])
            # some entries don't have a housenumber: ignore these entries
            if housenumber == '':
                continue
            elif not any(char.isdigit() for char in housenumber) and not args.here_be_dragons:
                continue
            try:
                gkz = reader_row["GKZ"]
                okz = reader_row["OKZ"]
                street = streets[reader_row["SKZ"]][0]
                streetname_is_ambiguous = False
                if gkz_has_ambiguous_streetnames[gkz]:
                    if normalize_streetname(street) in ambiguous_streetnames[gkz]:
                        okz_has_ambiguous_streetnames[okz] = True
                        streetname_is_ambiguous = True
                address = {
                    "gemeinde": districts[reader_row["GKZ"]],
                    "ortschaft": localities[reader_row["OKZ"]],
                    "plz": str(reader_row["PLZ"]),
                    "strasse": street,
                    "strassenzusatz": streets[reader_row["SKZ"]][1],
                    "hausnrtext": reader_row["HAUSNRTEXT"],
                    "hausnummer": housenumber,
                    "hausname": reader_row["HOFNAME"],
                    "gkz": reader_row["GKZ"],
                    "adress_x": coords[0],
                    "adress_y": coords[1],
                    "adrcd": address_id,
                    "okz": okz,
                    "strassenname_mehrdeutig": streetname_is_ambiguous
                }
                addresses[address_id] = address
                buildings[address_id] = []
            except KeyError:
                # ignore incomplete input files
                pass
    print("OKZ with ambiguous streetnames: ", len([okz for okz in okz_has_ambiguous_streetnames if okz_has_ambiguous_streetnames[okz] == True]))

    try:
        buildingReader = csv.DictReader(open('GEBAEUDE.csv', 'r', encoding='UTF-8-sig'), delimiter=';', quotechar='"')
    except IOError:
        print("\n##### ERROR ##### \nThe file 'GEBAEUDE.csv' was not found. Please download and unpack the BEV Address data from http://www.bev.gv.at/portal/page?_pageid=713,1604469&_dad=portal&_schema=PORTAL")
        quit()
    # get the total file size for status output
    total_buildings = sum(1 for row in open('GEBAEUDE.csv', 'r'))
    with ProgressBar("processing buildings ...") as pb:
        for i, buildingrow in enumerate(buildingReader):
            current_percentage = float(i) / total_buildings * 100
            pb.update(current_percentage)
            if buildingrow["HAUPTADRESSE"] != "1":
                continue
            address_id = buildingrow["ADRCD"]
            if address_id in addresses:
                x = buildingrow["RW"]
                y = buildingrow["HW"]
                if x == "" or y == "":
                    continue
                coords = reproject(buildingrow["EPSG"], [x, y])
                if coords[0] == '0' or coords[1] == '0':
                    continue
                subaddress = build_sub_housenumber(
                    buildingrow["HAUSNRZAHL3"],
                    buildingrow["HAUSNRBUCHSTABE3"],
                    buildingrow["HAUSNRVERBINDUNG2"],
                    buildingrow["HAUSNRZAHL4"],
                    buildingrow["HAUSNRBUCHSTABE4"],
                    buildingrow["HAUSNRVERBINDUNG3"]
                )
                building_info = coords
                building_info.append(subaddress)
                building_info.append(buildingrow["HAUSNRGEBAEUDEBEZ"])
                building_info.append(buildingrow["SUBCD"])
                buildings[address_id].append(building_info)

    if args.sort != None:
        print("\nsorting output ...")
        output = sorted(addresses.values(), key= operator.itemgetter(*args.sort.split(",")))
    else:
        output = addresses.values()
    if args.output_format == "osm":
        output_writer = OsmWriter()
    else:
        output_writer = CsvWriter(outputFilename, output_header_row)
    num_addresses_without_buildings = 0
    num_addresses_with_one_building = 0
    num_addresses_with_more_buildings = 0
    num_building_without_subadress = 0
    num_building_with_subadress = 0
    num_single_building_without_subadress = 0
    num_single_building_with_subadress = 0
    num_addresses_with_mixed_subaddresses = 0
    num_addresses_with_only_subaddresses = 0
    num_addresses_with_buildings_without_subaddresses = 0
    with ProgressBar("writing output ...") as pb:
        for i, row in enumerate(output):
            current_percentage = float(i) / len(output) * 100
            pb.update(current_percentage)
            address_buildings = buildings[row["adrcd"]]
            row["subcd"] = "000"
            if args.debug:
                tmp = row["hausnummer"]
                row["hausnummer"] += " (Z)"
                output_writer.add_address(row)
                row["hausnummer"] = tmp
            else:
                if len(address_buildings) == 0:
                    num_addresses_without_buildings += 1
                    if args.compatibility_mode:
                        row["haus_x"] = row["adress_x"]
                        row["haus_y"] = row["adress_y"]
                    if args.only_notes == False or row["hausname"] != "":
                        output_writer.add_address(row)
                    continue
                elif len(address_buildings) == 1:
                    num_addresses_with_one_building += 1
                    single_building = True
                    if building_info[3] == "Wohnhaus":
                        building_info[3] = ""
                else:
                    num_addresses_with_more_buildings += 1
                    single_building = False
                    has_building_without_subaddress = False
                    has_building_with_subaddress = False
                    for building_info in address_buildings:
                        if building_info[2] == "":
                            has_building_without_subaddress = True
                        else:
                            has_building_with_subaddress = True
                    if has_building_with_subaddress:
                        if has_building_without_subaddress:
                            num_addresses_with_mixed_subaddresses += 1
                        else:
                            num_addresses_with_only_subaddresses += 1
                    else:
                        num_addresses_with_buildings_without_subaddresses += 1
                    if args.compatibility_mode or (
                        has_building_without_subaddress and 
                        not has_building_with_subaddress and
                        not args.here_be_dragons):

                        row["haus_x"] = row["adress_x"]
                        row["haus_y"] = row["adress_y"]
                        if args.only_notes == False or row["hausname"] != "":
                            output_writer.add_address(row)
                        continue

            for building_info in address_buildings:
                row["haus_x"] = building_info[0]
                row["haus_y"] = building_info[1]
                row["subadresse"] = building_info[2]
                row["haus_bez"] = building_info[3]
                row["subcd"] = building_info[4]
                if args.debug:
                    tmp = row["hausnummer"]
                    row["hausnummer"] += " (G%d)" % int(row["subcd"])
                    row["adress_x"] = row["haus_x"]
                    row["adress_y"] = row["haus_y"]
                    output_writer.add_address(row)
                    row["hausnummer"] = tmp
                    continue
                if row["subadresse"] == "":
                    if single_building:
                        num_single_building_without_subadress += 1
                    else:
                        num_building_without_subadress += 1
                else:
                    if single_building:
                        num_single_building_with_subadress += 1
                    else:
                        num_building_with_subadress += 1
                if args.only_notes == False or row["haus_bez"] != "" or row["hausname"] != "":
                    output_writer.add_address(row)

    output_writer.close()
    print("\nfinished")
    print( time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) )

    # print("{:,} addresses without buildings".format(num_addresses_without_buildings))
    # print("{:,} addresses with exactly one building".format(num_addresses_with_one_building))
    # print("from which {:,} buildings have a subaddress and {:,} buildings don't".format(num_single_building_with_subadress, num_single_building_without_subadress))
    # print("{:,} addresses with more than one building".format(num_addresses_with_more_buildings))
    # print("from which {:,} buildings have a subaddress and {:,} buildings don't".format(num_building_with_subadress, num_building_without_subadress))
    # print("{:,} addresses where all buildings have subaddresses".format(num_addresses_with_only_subaddresses))
    # print("{:,} addresses where no buildings have subaddresses".format(num_addresses_with_buildings_without_subaddresses))
    # print("{:,} addresses that have both, buildings with and without subaddresses".format(num_addresses_with_mixed_subaddresses))