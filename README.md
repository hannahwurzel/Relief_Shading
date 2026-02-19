# CR Relief Shading
This repo handles BlueTopo data to create relief shading charts per a given tile region. 

Process: fetches bluetopo data --> runs hillshading --> combines UTM hillshades --> reprojects data to Mercator --> crops data to tile specifications --> encodes DEM to RGBA --> generates XYZ tiles.

## Environment
I find it best to run this inside of a conda environment as gdal can be finicky. 
`conda create -n relief -c conda-forge python=3.11 gdal=3.12.2`

## Data
You must have the appropriate data and file structure before running this.

### BlueTopo Data
You can download the BlueTopo data using the instructions from this repo: https://github.com/noaa-ocs-hydrography/BlueTopo. Run both the fetch_tiles() and build_vrt() commands.
- Use your {tile}.gpkg as the area of interest.
- The download path should be Tile_Data/{tile}/

### File Structure

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

## Script

### Command
`python data/process_data.py`

#### Optional Parameters
- `--base_dir`: Base directory of No_Mosaic/ and Contains_Mosaic/
- `--zoom_levels`: Zoom levels to generate XYZ tiles for
- `--processes`: Number of processes to run on for tile generation