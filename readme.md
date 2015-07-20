The idea for this script is shamelessly copied from https://github.com/BergWerkGIS/convert-bev-address-data

## Why?

The original script only runs on Windows systems. This one performs the same task as the original, but relies on Python.
The gdal Python-Module needs to be installed to perform reprojection.

## Usage

The main difference to the original is that you do not need to specify an input file name. Just execute the script from within the unzipped data from the BEV.
The coordinate system of the output file is the national EPSG:31287