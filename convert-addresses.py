# -*- coding: utf-8 -*-

"""The idea for this script originates from
https://github.com/BergWerkGIS/convert-bev-address-data/blob/master/README.md

The input are the files STRASSE.csv, GEMEINDE.csv and ADRESSE.csv from the 
publicly available dataset of addresses of Austria, available for download at
http://www.bev.gv.at/portal/page?_pageid=713,1604469&_dad=portal&_schema=PORTAL
"""

import csv
from osgeo import osr
from osgeo import ogr

targetRef = osr.SpatialReference()
targetRef.ImportFromEPSG(31287)
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
    return([round(float(p),2) for p in transformedPoint])

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
    addressWriter.writerow(['Gemeinde', 'plz', 'strasse', 'nummer','x', 'y'])
    
    # the main loop is this: each line in the ADRESSE.csv is parsed one by one
    for addressrow in addressReader:
        streetname = streets[addressrow[4]]
        districtname = districts[addressrow[1]]
        plzname = addressrow[3]
        hausnrzahl = addressrow[7]
        x = addressrow[15]
        y = addressrow[16]
        # some entries don't have coordinates: ignore these entries
        if x == '' or y == '': continue
        usedprojection = addressrow[17]
        coords = reproject(usedprojection,[x,y])
        # if the reprojection returned [0,0], this indicates an error: ignore these entries
        if coords[0] == '0' or coords[1] == '0': continue
        addressWriter.writerow([districtname, plzname, streetname, hausnrzahl, coords[0], coords[1]])
    print("finished")