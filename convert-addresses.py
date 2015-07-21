# -*- coding: utf-8 -*-

"""The idea for this script originates from
https://github.com/BergWerkGIS/convert-bev-address-data/blob/master/README.md

The input are the files STRASSE.csv, GEMEINDE.csv and ADRESSE.csv from the 
publicly available dataset of addresses of Austria, available for download at
http://www.bev.gv.at/portal/page?_pageid=713,1604469&_dad=portal&_schema=PORTAL
"""

import csv
import argparse
from osgeo import osr
from osgeo import ogr

'''
targetRefLambert = osr.SpatialReference()
targetRefLambert.ImportFromEPSG(31287)
targetRefWgs = osr.SpatialReference()
targetRefWgs.ImportFromEPSG(4326)
'''

# command line arguments are evaluated
parser = argparse.ArgumentParser(prog='python3 convert-addresses.py')
parser.add_argument('-epsg', help='Specify the EPSG code of the coordinate system used for the results. If none is given, this value defaults to the WGS84 system.'
                    ,type=int, default=4326, dest='epsg')
args = parser.parse_args()
# the target EPSG is set according to the argument
targetRef = osr.SpatialReference()
targetRef.ImportFromEPSG(args.epsg)

westRef = osr.SpatialReference()
westRef.ImportFromEPSG(31254)
centerRef = osr.SpatialReference()
centerRef.ImportFromEPSG(31255)
eastRef = osr.SpatialReference()
eastRef.ImportFromEPSG(31256)

westTransform = osr.CoordinateTransformation(westRef,targetRef)
centralTransform = osr.CoordinateTransformation(centerRef,targetRef)
eastTransfrom = osr.CoordinateTransformation(eastRef,targetRef)

def reproject(sourceCRS, points):
    """This function reprojects an array of coordinates (a point) to EPSG:31287
    depending on their original CRS given by the parameter sourceCRS"""
    
    point = ogr.CreateGeometryFromWkt("POINT (" + str(points[0]) + " " + str(points[1]) + ")")
    if sourceCRS == '31254':
        point.Transform(westTransform)
    elif sourceCRS == '31255':
        point.Transform(centralTransform)
    elif sourceCRS == '31256':
        point.Transform(eastTransfrom)
    else:
        print("unkown CRS: {}".format(sourceCRS))
        return([0,0])
    wktPoint = point.ExportToWkt()
    transformedPoint = wktPoint.split("(")[1][:-1].split(" ")
    del(point)
    return [round(float(p),6) for p in transformedPoint]

def buildHausNumber(hausnrtext,hausnrzahl1,hausnrbuchstabe1,hausnrverbindung1,hausnrzahl2,hausnrbuchstabe2,hausnrbereich):
    """This function takes all the different single parts of the input file that belong
    to the house number and combines them into one single string"""
    
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
    

if __name__ == '__main__':
    print("buffering streets ...")
    streetReader = csv.reader(open('STRASSE.csv', 'r'), delimiter=';', quotechar='"')
    streets = {}
    headerstreets = next(streetReader, None)
    for streetrow in streetReader:
        streets[streetrow[0]] = streetrow[1] + " " + streetrow[2]
    
    print("buffering districts ...")
    districtReader = csv.reader(open('GEMEINDE.csv', 'r'), delimiter=';', quotechar='"')
    districts = {}
    headerdistricts = next(districtReader, None)
    for districtrow in districtReader:
        districts[districtrow[0]] = districtrow[1]
    
    print("processing addresses ...")
    addressReader = csv.reader(open('ADRESSE.csv', 'r'), delimiter=';', quotechar='"')
    headeraddresses = next(addressReader, None)
    
    addressWriter = csv.writer(open('bev_addresses.csv', 'w'), delimiter=";", quotechar='"')
    addressWriter.writerow(['Gemeinde', 'plz', 'strasse', 'nummer','hausname','x', 'y'])
    
    # get the total file size for status output
    total_addresses = sum(1 for row in csv.reader(open('ADRESSE.csv', 'r'), delimiter=';', quotechar='"'))
    previous_percentage = 0
    # the main loop is this: each line in the ADRESSE.csv is parsed one by one
    for i,addressrow in enumerate(addressReader):
        current_percentage = round(float(i)/total_addresses * 100)
        if current_percentage != previous_percentage:
            print("{} %".format(current_percentage))
            previous_percentage = current_percentage
        streetname = streets[addressrow[4]]
        districtname = districts[addressrow[1]]
        plzname = addressrow[3]
        hausnr = buildHausNumber(addressrow[6],addressrow[7],addressrow[8],addressrow[9],addressrow[10],addressrow[11],addressrow[12])
        hausname = addressrow[14]
        x = addressrow[15]
        y = addressrow[16]
        # some entries don't have coordinates: ignore these entries
        if x == '' or y == '': continue
        usedprojection = addressrow[17]
        coords = reproject(usedprojection,[x,y])
        # if the reprojection returned [0,0], this indicates an error: ignore these entries
        if coords[0] == '0' or coords[1] == '0': continue
        addressWriter.writerow([districtname, plzname, streetname, hausnr, hausname, coords[0], coords[1]])
    print("finished")