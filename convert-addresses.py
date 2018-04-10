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
parser.add_argument('-buildings', action='store_true', dest='buildings',
                    help='Specify if building addresses/locations should be included or not.')
parser.add_argument('-sort', default=None, dest='sort',
                    help='Specify if and by which field the output should be sorted (possible values: gemeinde, plz, strasse, nummer, hausname, x, y, gkz).')
args = parser.parse_args()

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

class ProgressBar():
    def __init__(self):
        self.percentage = 0
    
    def update(self, new_percentage):
        if new_percentage != self.percentage:
            sys.stdout.write("\r{} %   ".format(str(new_percentage).ljust(6)))
            sys.stdout.write('[{}]'.format(('#' * int(new_percentage / 2)).ljust(50)))
            sys.stdout.flush()
        self.percentage = new_percentage

def downloadData():
    """This function downloads the address data from BEV and displays its terms
    of usage"""

    if not requestsModule:
        print("source data missing and download is deactivated")
        quit()
    addressdataUrl = "http://www.bev.gv.at/pls/portal/docs/PAGE/BEV_PORTAL_CONTENT_ALLGEMEIN/0200_PRODUKTE/UNENTGELTLICHE_PRODUKTE_DES_BEV/Adresse_Relationale_Tabellen-Stichtagsdaten.zip"
    response = requests.get(addressdataUrl, stream=True)
    print("downloading address data from BEV")
    
    with open(addressdataUrl.split('/')[-1], 'wb') as handle:
        pb = ProgressBar()
        for i, data in enumerate(response.iter_content(chunk_size=1000000)):
            handle.write(data)
            current_percentage = i * 1.3
            pb.update(current_percentage)
    pb.update(100)


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
        

def buildHausNumber(hausnrzahl1, hausnrbuchstabe1, hausnrverbindung1, hausnrzahl2, hausnrbuchstabe2, hausnrbereich):
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
    if hausnrbereich != "keine Angabe": compiledHausNr += ", {}".format(hausnrbereich)
    return compiledHausNr


def preparations():
    """check for necessary files and issue downloads when necessary"""
    csv_files = ["STRASSE.csv", "GEMEINDE.csv", "ADRESSE.csv", "GEBAEUDE.csv", "ORTSCHAFT.csv"]
    if not all(os.path.isfile(csv) for csv in csv_files):
        # ckeck if the packed version exists
        if not os.path.isfile('Adresse_Relationale_Tabellen-Stichtagsdaten.zip'):
            # if not, download it
            downloadData()
        with zipfile.ZipFile('Adresse_Relationale_Tabellen-Stichtagsdaten.zip', 'r') as myzip:
            for csv in csv_files:
                print("extracting %s" % csv)
                myzip.extract(csv)
    return True

if __name__ == '__main__':
    print('#' * 40)
    print(info)
    print('#' * 40 + '\n')
    
    if not preparations() == True:
        print("There was an error")
        quit()

    if args.sort != None:
        possibleValues = ['gemeinde', 'plz', 'strasse', 'nummer', 'hausname', 'x', 'y', 'gkz']
        if args.sort not in possibleValues:
            print("\n##### ERROR ##### \nSort parameter is not allowed. Use one of gemeinde, plz, strasse, nummer, hausname, x, y, gkz")
            quit()
        args.sort = possibleValues.index(args.sort)

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

    print("buffering streets ...")
    try:
        streetReader = csv.DictReader(open('STRASSE.csv', 'r', encoding='UTF-8-sig'), delimiter=';', quotechar='"')
    except IOError:
        print("\n##### ERROR ##### \nThe file 'STRASSE.csv' was not found. Please download and unpack the BEV Address data from http://www.bev.gv.at/portal/page?_pageid=713,1604469&_dad=portal&_schema=PORTAL")
        quit()
    streets = {}
    for streetrow in streetReader:
        streets[streetrow['SKZ']] = [streetrow['STRASSENNAME'], streetrow['STRASSENNAMENZUSATZ']]

    print("buffering districts ...")
    try:
        districtReader = csv.DictReader(open('GEMEINDE.csv', 'r', encoding='UTF-8-sig'), delimiter=';', quotechar='"')
    except IOError:
        print("\n##### ERROR ##### \nThe file 'GEMEINDE.csv' was not found. Please download and unpack the BEV Address data from http://www.bev.gv.at/portal/page?_pageid=713,1604469&_dad=portal&_schema=PORTAL")
        quit()
    districts = {}
    for districtrow in districtReader:
        districts[districtrow['GKZ']] = districtrow['GEMEINDENAME']

    print("processing addresses ...")
    try:
        addressReader = csv.DictReader(open('ADRESSE.csv', 'r', encoding='UTF-8-sig'), delimiter=';', quotechar='"')
    except IOError:
        print("\n##### ERROR ##### \nThe file 'ADRESSE.csv' was not found. Please download and unpack the BEV Address data from http://www.bev.gv.at/portal/page?_pageid=713,1604469&_dad=portal&_schema=PORTAL")
        quit()
    outputFilename = "bev_addressesEPSG{}.csv".format(args.epsg)
    addressWriter = csv.writer(open(outputFilename, 'w'), delimiter=";", quotechar='"')
    row = ['gemeinde', 'ortschaft', 'plz', 'strasse', 'strassenzusatz', 'hausnrtext', 'hausnummer', 'hausname', 'gkz', 'x', 'y']
    if args.buildings:
        row.append('typ')
    addressWriter.writerow(row)

    # get the total file size for status output
    total_addresses = sum(1 for row in open('ADRESSE.csv', 'r'))
    pb = ProgressBar()
    addresses = {}
    # the main loop is this: each line in the ADRESSE.csv is parsed one by one
    for i, addressrow in enumerate(addressReader):
        current_percentage = round(float(i) / total_addresses * 100, 2)
        pb.update(current_percentage)
        
        streetname = streets[addressrow["SKZ"]][0]
        streetsupplement = streets[addressrow["SKZ"]][1]
        streetname = streetname.strip()  # remove the trailing whitespace after each street name
        districtname = districts[addressrow["GKZ"]]
        localityname = localities[addressrow["OKZ"]]
        plzname = addressrow["PLZ"]
        hausnrtext = addressrow["HAUSNRTEXT"]
        hausnr = buildHausNumber(
            addressrow["HAUSNRZAHL1"], 
            addressrow["HAUSNRBUCHSTABE1"],
            addressrow["HAUSNRVERBINDUNG1"],
            addressrow["HAUSNRZAHL2"],
            addressrow["HAUSNRBUCHSTABE2"],
            addressrow["HAUSNRBEREICH"])
        hausname = addressrow["HOFNAME"]
        x = addressrow["RW"]
        y = addressrow["HW"]
        # some entries don't have coordinates: ignore these entries
        if x == '' or y == '':
            continue
        usedprojection = addressrow["EPSG"]
        coords = reproject(usedprojection, [x, y])
        # if the reprojection returned [0,0], this indicates an error: ignore these entries
        if coords[0] == '0' or coords[1] == '0':
            continue
        # note: coordinates are expected as the last two list values in case of args.buildings, so please don't add anything behind it
        row = [districtname, localityname, plzname, streetname, streetsupplement, hausnrtext, hausnr, hausname, coords[0], coords[1]]
        if args.buildings:
            row.append('Adresskoordinate')
        addresses[addressrow["ADRCD"]] = row
        if not args.sort:
            addressWriter.writerow(row)

    if args.buildings:
        print("processing buildings ...")
        try:
            buildingReader = csv.DictReader(open('GEBAEUDE.csv', 'r', encoding='UTF-8-sig'), delimiter=';', quotechar='"')
        except IOError:
            print("\n##### ERROR ##### \nThe file 'GEBAEUDE.csv' was not found. Please download and unpack the BEV Address data from http://www.bev.gv.at/portal/page?_pageid=713,1604469&_dad=portal&_schema=PORTAL")
            quit()
        # get the total file size for status output
        total_buildings = sum(1 for row in open('ADRESSE.csv', 'r'))
        pb = ProgressBar()
        buildings = {}
        # the main loop is this: each line in the GEBAEUDE.csv is parsed one by one
        for i, buildingrow in enumerate(buildingReader):
            current_percentage = round(float(i) / total_addresses * 100, 2)
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
                building_address = addresses[address_id][:-3] + coords[:] + ["Hauskoordinate"]
                addresses[address_id + buildingrow["SUBCD"]] = building_address
                if not args.sort:
                    addressWriter.writerow(building_address)

    if args.sort != None:
        print("\nsorting output ...")
        pb = ProgressBar()
        sortedAddresses = sorted(addresses.values(), key=lambda var: var[args.sort])
        print("writing output ...")
        for i, row in enumerate(sortedAddresses):
            current_percentage = round(float(i) / len(sortedAddresses) * 100, 2)
            pb.update(current_percentage)
            addressWriter.writerow(row)

    print("\nfinished")
    print( time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) )
