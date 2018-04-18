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

def downloadData():
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

def buildSubHouseNumber(hausnrzahl3, hausnrbuchstabe3, hausnrverbindung2, hausnrzahl4, hausnrbuchstabe4, hausnrverbindung3):
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


    output_header_row = ['gemeinde', 'ortschaft', 'plz', 'strasse', 'strassenzusatz', 'hausnrtext', 'hausnummer', 'hausname', 'adress_x', 'adress_y', 'subadresse', 'haus_x', 'haus_y', 'haus_bez', 'adrcd', 'gkz']
    if args.sort != None:
        if args.sort not in output_header_row:
            print("\n##### ERROR ##### \nSort parameter is not allowed. Use one of %s" % output_header_row)
            quit()
        args.sort = output_header_row.index(args.sort)

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
        streets[streetrow['SKZ']] = [streetrow['STRASSENNAME'].strip(), streetrow['STRASSENNAMENZUSATZ']]

    print("buffering districts ...")
    try:
        districtReader = csv.DictReader(open('GEMEINDE.csv', 'r', encoding='UTF-8-sig'), delimiter=';', quotechar='"')
    except IOError:
        print("\n##### ERROR ##### \nThe file 'GEMEINDE.csv' was not found. Please download and unpack the BEV Address data from http://www.bev.gv.at/portal/page?_pageid=713,1604469&_dad=portal&_schema=PORTAL")
        quit()
    districts = {}
    for districtrow in districtReader:
        districts[districtrow['GKZ']] = districtrow['GEMEINDENAME']

    try:
        addressReader = csv.DictReader(open('ADRESSE.csv', 'r', encoding='UTF-8-sig'), delimiter=';', quotechar='"')
    except IOError:
        print("\n##### ERROR ##### \nThe file 'ADRESSE.csv' was not found. Please download and unpack the BEV Address data from http://www.bev.gv.at/portal/page?_pageid=713,1604469&_dad=portal&_schema=PORTAL")
        quit()
    outputFilename = "bev_addressesEPSG{}.csv".format(args.epsg)

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
            address = {
                "gemeinde": districts[reader_row["GKZ"]],
                "ortschaft": localities[reader_row["OKZ"]],
                "plz": reader_row["PLZ"],
                "strasse": streets[reader_row["SKZ"]][0],
                "strassenzusatz": streets[reader_row["SKZ"]][1],
                "hausnrtext": reader_row["HAUSNRTEXT"],
                "hausnummer": buildHausNumber(
                    reader_row["HAUSNRZAHL1"], 
                    reader_row["HAUSNRBUCHSTABE1"],
                    reader_row["HAUSNRVERBINDUNG1"],
                    reader_row["HAUSNRZAHL2"],
                    reader_row["HAUSNRBUCHSTABE2"],
                    reader_row["HAUSNRBEREICH"]),
                "hausname": reader_row["HOFNAME"],
                "gkz": reader_row["GKZ"],
                "adress_x": coords[0],
                "adress_y": coords[1],
                "adrcd": address_id,
            }
            addresses[address_id] = address
            buildings[address_id] = []

    try:
        buildingReader = csv.DictReader(open('GEBAEUDE.csv', 'r', encoding='UTF-8-sig'), delimiter=';', quotechar='"')
    except IOError:
        print("\n##### ERROR ##### \nThe file 'GEBAEUDE.csv' was not found. Please download and unpack the BEV Address data from http://www.bev.gv.at/portal/page?_pageid=713,1604469&_dad=portal&_schema=PORTAL")
        quit()
    # get the total file size for status output
    total_buildings = sum(1 for row in open('GEBAEUDE.csv', 'r'))
    with ProgressBar("processing buildings ...") as pb:
        for i, buildingrow in enumerate(buildingReader):
            current_percentage = float(i) / total_addresses * 100
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
                subaddress = buildSubHouseNumber(
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
                buildings[address_id].append(building_info)

    if args.sort != None:
        print("\nsorting output ...")
        output = sorted(addresses.values(), key=lambda var: var[args.sort])
    else:
        output = addresses.values()
    #addressWriter = csv.DictWriter(open(outputFilename, 'w'), output_header_row, extrasaction="ignore", delimiter=";", quotechar='"')
    addressWriter = csv.DictWriter(open(outputFilename, 'w'), output_header_row, delimiter=";", quotechar='"')
    addressWriter.writeheader()
    num_addresses_without_buildings = 0
    num_addresses_with_one_building = 0
    num_addresses_with_more_buildings = 0
    num_building_without_subadress = 0
    num_building_with_subadress = 0
    num_single_building_without_subadress = 0
    num_single_building_with_subadress = 0
    with ProgressBar("writing output ...") as pb:
        for i, row in enumerate(output):
            current_percentage = float(i) / len(output) * 100
            pb.update(current_percentage)
            address_buildings = buildings[row["adrcd"]]
            if len(address_buildings) == 0:
                num_addresses_without_buildings += 1
                addressWriter.writerow(row)
                continue
            elif len(address_buildings) == 1:
                num_addresses_with_one_building += 1
                single_building = True
            else:
                num_addresses_with_more_buildings += 1
                single_building = False
            for building_info in address_buildings:
                row["haus_x"] = building_info[0]
                row["haus_y"] = building_info[1]
                row["subadresse"] = building_info[2]
                row["haus_bez"] = building_info[3]
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
                addressWriter.writerow(row)

    print("\nfinished")
    print( time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) )

    print("{:,} addresses without buildings".format(num_addresses_without_buildings))
    print("{:,} addresses with exactly one building".format(num_addresses_with_one_building))
    print("from which {:,} buildings have a subaddress and {:,} buildings don't".format(num_single_building_with_subadress, num_single_building_without_subadress))
    print("{:,} addresses with more than one building".format(num_addresses_with_more_buildings))
    print("from which {:,} buildings have a subaddress and {:,} buildings don't".format(num_building_with_subadress, num_building_without_subadress))
