# CR Relief Shading
This repo handles BlueTopo and Mosaic Multibeam data to create relief shading charts per a given tile region.

## Environment
I find it best to run this inside of a conda environment as gdal can be finicky. 
`conda create -n relief -c conda-forge python=3.11 gdal=3.12.2`

## Data
You must have the appropriate data and file structure before running this.

### BlueTopo Data
You can download the BlueTopo data using the instructions from this repo: https://github.com/noaa-ocs-hydrography/BlueTopo. Run both the fetch_tiles() and build_vrt() commands.
- Use your {tile}.gpkg as the area of interest.
- The download path should be Tile_Data/{tile}/

#### File Structure

- {base_dir}/
    - {data_dir}/
        - Tile_Bounds/
            - {tile}.gpkg
        - Tile_Data/
            - {tile}
                - BlueTopo/
                - BlueTopo_VRT/

{data_dir} is either No_Mosaic or Contains_Mosaic. I seperated these out because tiles containing multibeam data need to follow a different process than if they do not, specifically around extra cropping required which needs to be done on QGIS.

Both BlueTopo/ and BlueTopo_VRT/ are generating when gathering the BlueTopo Data.

#### Command
`python data/process_data.py`

#### Optional Parameters
- `--base_dir`: Base directory of No_Mosaic/ and Contains_Mosaic/
- `--zoom_levels`: Zoom levels to generate XYZ tiles for
- `--processes`: Number of processes to run on for tile generation


### Mosaic Multibeam 
You can download the data here: https://www.ncei.noaa.gov/maps/grid-extract/. Do it in sections by using your tile boundary as of the area of interst.

#### Hillshading
Once you have the data saved off run `python hillshading/mosaic.py` to run hillshading.


### Miscellaneous
There are a few helper files I created when I ran into random issues:
- `dem/pad_dem.py`: I noticed that there were specific regions with entire sizes missing exactly one pixel in width. This script adds a row or column of pixels to get rid of this gap.
- `tiles/dem_lower_generation.py`: This script generates the DEM files needed to generate XYZ tiles at any zoom level below the base zoom of 7. 
- `tiles/hs_lower_generation.py`: Similar to the previous one, this script generates the hillshading .tif files needed to generate XYZ tiles at any zoom level below the base zoom of 7.


## Steps to Create Relief Charts
- Run the process data script: `python data/process_data.py`
- Gather the multibeam data
- Run `python hillshading/mosaic.py`
- Crop the noise out of the multibeam data in QGIS
- In all tiles containing mosaic data, place the bluetopo hillshading underneath it to get a smooth hillshading
- Generate XYZ tiles for these in QGIS. Save into folders based on region. (ex. base dir: mosaic_xyz, sub_dirs: 7_54_34, 7_34_56, etc.)
- Run the `hillshading/mosaic_tiles.py` script to combine these XYZ tiles correctly