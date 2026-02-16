# CR Relief Shading
This repo handles BlueTopo and Mosaic Multibeam data to create relief shading charts per a given tile region.

## Environment
I find it best to run this inside of a conda environment as gdal can be finicky. 
`conda create -n relief -c conda-forge python=3.11 gdal=3.12.2`

## BlueTopo HillShading and VRT
This script generates hillshades for BlueTopo data in a given region, combines those hillshades into one file and then crops that file to a specified tile boundary.

### Gathering BlueTopo Data
See https://github.com/noaa-ocs-hydrography/BlueTopo for instructions on how to fetch BlueTopo data. 

Make sure to run both the `fetch_tiles()` command and the `build_vrt()` command. This will generate both your BlueTopo/ and BlueTopo_VRT/ directories. `area_of_interest.gpkg` should be your {tile}.gpkg.

### Command
`python hillshading/bluetopo_hillshading.py <tile> <base_dir>`

Note that this script assumes you already downloaded the BLueTopo files and created a VRT in the steps above.

Base Directory structure:
- Tile_Data/
    - {tile}/
        - BlueTopo/
        - BlueTopo_VRT/
- Tile_Bounds/
    - {tile}.gpkg


## Mosaic Hillshading
This script generates hillshading for Mosaic Multibeam data.

### Gathering Mosaic Multibeam Data
Use https://www.ncei.noaa.gov/maps/bathymetry/ to extract the data. The data source is Multibeam Mosaic and the cell sizeis 3 arc-second (~90m). Use the coordinates from your tile in "Enter Coordinates". 

Save off the file in the same Tile_Data directory as your BlueTopo data like so:

- Tile_Data/
    - {tile}/
        - Mosaic/
            - Mosaic.tiff

### Command
`python hillshading/mosaic_hillshading.py <tile> <base_dir>`

### Cropping
Since mosaic data is super high res in some areas and contains random lines in others, we are going to want to crop it to only contain those high res areas. This must be done in QGIS...
- Import the hillshading to QGIS
- Create a polygon that encapsulates the region you want to keep
- Use "Clip raster by mask extend" where your input layer in the hillshade and the mask layer is the polygon
- Save off the cropped hillshading to the same location as your original Mosaic


## Styling Relief Shading in QGIS
In QGIS, style each hillshade as follows:
- render type: singleband gray
- blending mode: multiply
- brightness: 20
- contrast: 20

The hillshade layers should sit on top of the VRT color layer.