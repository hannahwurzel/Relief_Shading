from argparse import ArgumentParser
from glob import glob
from pathlib import Path
import re
import sys

from data.utils import (
    crop_data,
    fetch_bluetopo_data,
    reproject_files,
    generate_xyz_tiles,
)
from dem.encode import encode_dem_to_rgba
from hillshading.bluetopo_utils import (
    combine_hillshades,
    run_batch_hillshading,
)


def parse_args():
    """
    Parses a users command line arguments.
    """
    parser = ArgumentParser(
        description="Run multidirectional hillshading on BlueTopo tiles, combines them into \
              a single hillshade file and crops them into their level 7 zoom tile."
    )
    parser.add_argument(
        "--base_dir",
        help="Base directory where No_Mosaic/ and Contains_Mosaic/ live",
        default="/Volumes/Crucial X10/QGIS/relief_by_tile",
    )
    parser.add_argument(
        "--zoom_levels", help="Zoom levels for tile generation", default="7-15"
    )
    parser.add_argument(
        "--num_processes", help="Number of processes for tile generation", default=4
    )
    return parser.parse_args()


def crop_to_tile(tile: str, base_dir: str) -> None:
    """
    Crops the hillshade and DEM to the tile extent.

    tile: str
        a string denoting the tile we are working with (eg. 7_38_48)
    base_dir: str
        base directory where all of the files live
    """
    print("\n--------- Step 4/6: Croping data to tile extent ---------")
    base = Path(base_dir) / "Tile_Data"
    boundary_dir = Path(base_dir) / "Tile_Bounds" / f"{tile}.gpkg"

    output_dir = base / tile / "Cropped"
    output_dir.mkdir(parents=True, exist_ok=True)

    input_hs_file = base / tile / "hillshading" / "reprojected_bluetopo.tif"
    output_hs_file = output_dir / f"HS_cropped.tif"

    input_vrt_file = base / tile / "BlueTopo_VRT" / "reprojected_dem.tif"
    output_vrt_file = output_dir / f"dem_cropped.tif"

    crop_data(input_hs_file, output_hs_file, boundary_dir, "HS")
    crop_data(input_vrt_file, output_vrt_file, boundary_dir, "DEM")
    return


def reproject_data(tile: str, base_dir: str) -> None:
    """
    Reprojects input data into Web Mercator (EPSG:3857).

    tile: str
        a string denoting the tile we are working with (eg. 7_38_48)
    base_dir: str
        base directory where all of the files live
    """
    print("\n--------- Step 3/6: Reprojecting Data to Mercator ---------")
    hs_dir = Path(f"{base_dir}/Tile_Data/{tile}/hillshading/")
    hs_files = glob(f"{hs_dir}/HS*")
    dem_dir = Path(f"{base_dir}/Tile_Data/{tile}/BlueTopo_VRT/")
    dem_files = glob(f"{dem_dir}/BlueTopo_*.vrt")

    reproject_files(hs_files, hs_dir / "reprojected_bluetopo.tif", "HS")
    reproject_files(dem_files, dem_dir / "reprojected_dem.tif", "DEM")

    return


def process_data(data_dir: str, tile: str) -> None:
    """
    Runs the full data processing workflow for a given tile and UTM zone.

    data_dir: str
        data directory containing BlueTopo data
    tile: str
        a string denoting the tile we are working with (eg. 7_38_48)
    """
    files = glob(f"{data_dir}/Tile_Data/{tile}/BlueTopo/UTM*")
    utms = list(set(re.search(r"UTM(\d+)", f).group(1) for f in files))
    if not utms:
        print(f"No UTM directories found in Tile_Data/{tile}/BlueTopo")
        sys.exit(1)

    print("\n--------- Step 2/6: Running hillshading ---------")
    for utm in utms:
        run_batch_hillshading(tile, utm, data_dir)
        combine_hillshades(tile, utm, data_dir)

    reproject_data(tile, data_dir)
    crop_to_tile(tile, data_dir)


def generate_tiles(
    data_dir: str, tile: str, zoom_levels: str, processes: int, mosaic: bool = False
):
    """
    Generates XYZ tiles for the hillshade and DEM files.

    data_dir: str
        Data directory containing BlueTopo data
    tile: str
        A string denoting the tile we are working with (eg. 7_38_48)
    mosaic: bool
        Bool denoting whether or not tiles contain mosaic multibeam hillshading
    zoom_level: str
        Zoom levels to generate for
    processes: int
        Number of processes for tile generation
    """
    input_dem_file = f"{data_dir}/Tile_Data/{tile}/Cropped/dem_cropped.tif"
    rgba_output_file = f"{data_dir}/Tile_Data/{tile}/Cropped/dem_rgba.tif"
    xyz_dem_output_dir = f"{data_dir}/Tile_Data/{tile}/XYZ/DEM"

    print("\n--------- Step 5/6: Encoding DEM to RGBA ---------")
    encode_dem_to_rgba(input_dem_file, rgba_output_file)

    print("\n--------- Step 6/6: Generating XYZ tiles ---------")
    generate_xyz_tiles(
        rgba_output_file,
        xyz_dem_output_dir,
        zoom_levels,
        processes,
    )

    # only generate tiles for hillshading if it does not contain mosaic multibeam areas
    # if it does, this needs to be generated in QGIS as manual cropping needs to be done
    if not mosaic:
        input_hs_file = f"{data_dir}/Tile_Data/{tile}/Cropped/HS_cropped.tif"
        output_hs_tiles = f"{data_dir}/Tile_Data/{tile}/XYZ/hillshade"
        generate_xyz_tiles(
            input_hs_file,
            output_hs_tiles,
            zoom_levels,
            processes,
        )


def main() -> None:
    args = parse_args()

    datasets = glob(f"{args.base_dir}/*Mosaic")
    for dataset in datasets:
        tiles = [
            f.stem
            for f in (Path(dataset) / "Tile_Bounds").iterdir()
            if f.suffix == ".gpkg" and re.fullmatch(r"\d+_\d+_\d+", f.stem)
        ]
        includes_mosaic = datasets[0].endswith("Contains_Mosaic")

        for idx, tile in enumerate(tiles):
            print(
                f"\n___________ Tile Number {idx + 1} / {len(tiles)} for {dataset.split('/')[-1]} directory ___________"
            )
            download_path = Path(dataset) / "Tile_Data" / tile
            tile_path = Path(dataset) / "Tile_Bounds" / f"{tile}.gpkg"

            fetch_bluetopo_data(download_path, tile_path)
            process_data(dataset, tile)
            generate_tiles(
                dataset, tile, args.zoom_levels, args.num_processes, includes_mosaic
            )


if __name__ == "__main__":
    main()
