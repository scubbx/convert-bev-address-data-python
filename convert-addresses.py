# -*- coding: utf-8 -*-

info = """The idea for this script originates from
https://github.com/BergWerkGIS/convert-bev-address-data/blob/master/README.md

The input are the files STRASSE.csv, GEMEINDE.csv and ADRESSE.csv from the
publicly available dataset of addresses of Austria, available for download at
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
parser.add_argument('-gkz', action='store_true', dest='gkz',
                    help='Specify if GKZ should be included or not.')
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
        for i, data in enumerate(response.iter_content(chunk_size=1000000)):
            handle.write(data)
            # we draw a nice progess bar
            current_percentage = i * 1.3
            sys.stdout.write("\r{} %   ".format(str(current_percentage).ljust(6)))
            sys.stdout.write('[{}]'.format(('#' * int(current_percentage / 2)).ljust(50)))
            sys.stdout.flush()
            #print("{} %".format(i))
    current_percentage = 100
    sys.stdout.write("\r{} %   ".format(str(current_percentage).ljust(6)))
    sys.stdout.write('[{}]'.format(('#' * (int(current_percentage) / 2)).ljust(50)))
    sys.stdout.flush()


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
        

def buildHausNumber(hausnrtext, hausnrzahl1, hausnrbuchstabe1, hausnrverbindung1, hausnrzahl2, hausnrbuchstabe2, hausnrbereich):
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
    if hausnrtext != "": compiledHausNr += " ,{}".format(hausnrtext)
    if hausnrbereich != "keine Angabe": compiledHausNr += " ,{}".format(hausnrbereich)
    return compiledHausNr


def preparations():
    """check for necessary files and issue downloads when necessary"""

    if not (os.path.isfile('STRASSE.csv') and os.path.isfile('GEMEINDE.csv') and os.path.isfile('ADRESSE.csv')):
        # ckeck if the packed version exists
        if not os.path.isfile('Adresse_Relationale_Tabellen-Stichtagsdaten.zip'):
            # if not, download it
            downloadData()
        with zipfile.ZipFile('Adresse_Relationale_Tabellen-Stichtagsdaten.zip', 'r') as myzip:
            print("extracting STRASSE.csv")
            myzip.extract('STRASSE.csv');
            print("extracting GEMEINDE.csv")
            myzip.extract('GEMEINDE.csv');
            print("extracting ADRESSE.csv")
            myzip.extract('ADRESSE.csv');
    return True

if __name__ == '__main__':
    print('#' * 40)
    print(info)
    print('#' * 40 + '\n')
    
    if not preparations() == True:
        print("There was an error")
        quit()
    
    print("buffering streets ...")
    try:
        streetReader = csv.reader(open('STRASSE.csv', 'r'), delimiter=';', quotechar='"')
    except IOError:
        print("\n##### ERROR ##### \nThe file 'STRASSE.csv' was not found. Please download and unpack the BEV Address data from http://www.bev.gv.at/portal/page?_pageid=713,1604469&_dad=portal&_schema=PORTAL")
        quit()

    streets = {}
    headerstreets = next(streetReader, None)
    for streetrow in streetReader:
        streets[streetrow[0]] = streetrow[1] + " " + streetrow[2]

    print("buffering districts ...")
    try:
        districtReader = csv.reader(open('GEMEINDE.csv', 'r'), delimiter=';', quotechar='"')
    except IOError:
        print("\n##### ERROR ##### \nThe file 'GEMEINDE.csv' was not found. Please download and unpack the BEV Address data from http://www.bev.gv.at/portal/page?_pageid=713,1604469&_dad=portal&_schema=PORTAL")
        quit()

    districts = {}
    headerdistricts = next(districtReader, None)
    for districtrow in districtReader:
        districts[districtrow[0]] = districtrow[1]

    print("processing addresses ...")
    try:
        addressReader = csv.reader(open('ADRESSE.csv', 'r'), delimiter=';', quotechar='"')
    except IOError:
        print("\n##### ERROR ##### \nThe file 'ADRESSE.csv' was not found. Please download and unpack the BEV Address data from http://www.bev.gv.at/portal/page?_pageid=713,1604469&_dad=portal&_schema=PORTAL")
        quit()

    headeraddresses = next(addressReader, None)

    outputFilename = "bev_addressesEPSG{}.csv".format(args.epsg)
    addressWriter = csv.writer(open(outputFilename, 'w'), delimiter=";", quotechar='"')
    row = ['Gemeinde', 'plz', 'strasse', 'nummer', 'hausname', 'x', 'y']
    if args.gkz:
        row.append('gkz')
    addressWriter.writerow(row)

    # get the total file size for status output
    total_addresses = sum(1 for row in csv.reader(open('ADRESSE.csv', 'r'), delimiter=';', quotechar='"'))
    previous_percentage = 0
    # the main loop is this: each line in the ADRESSE.csv is parsed one by one
    for i, addressrow in enumerate(addressReader):
        current_percentage = round(float(i) / total_addresses * 100, 2)
        if current_percentage != previous_percentage:
            # we draw a nice progess bar
            sys.stdout.write("\r{} %   ".format(str(current_percentage).ljust(6)))
            sys.stdout.write('[{}]'.format(('#' * int(current_percentage / 2) ).ljust(50)))
            sys.stdout.flush()
            previous_percentage = current_percentage
        streetname = streets[addressrow[4]]
        streetname = streetname.strip()  # remove the trailing whitespace after each street name
        districtname = districts[addressrow[1]]
        gkz = addressrow[1]
        plzname = addressrow[3]
        hausnr = buildHausNumber(addressrow[6], addressrow[7], addressrow[8], addressrow[9], addressrow[10], addressrow[11], addressrow[12])
        hausname = addressrow[14]
        x = addressrow[15]
        y = addressrow[16]
        # some entries don't have coordinates: ignore these entries
        if x == '' or y == '':
            continue
        usedprojection = addressrow[17]
        coords = reproject(usedprojection, [x, y])
        # if the reprojection returned [0,0], this indicates an error: ignore these entries
        if coords[0] == '0' or coords[1] == '0':
            continue
        row = [districtname, plzname, streetname, hausnr, hausname, coords[0], coords[1]]
        if args.gkz:
            row.append(gkz)
        addressWriter.writerow(row)
    print("\nfinished")
    print( time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) )
