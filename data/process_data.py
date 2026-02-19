from argparse import ArgumentParser
from glob import glob
from pathlib import Path
import re
import sys

from data.utils import crop_data, reproject_files, generate_xyz_tiles
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
    parser.add_argument("tile", help="Tile name in XYZ format (e.g. 7_40_37)")
    parser.add_argument(
        "--base_dir",
        help="Base directory where Tile_Data and Tile_Bounds live",
        default="/Volumes/Crucial X10/QGIS/relief_by_tile",
    )
    parser.add_argument(
        "--zoom_levels", help="Zoom levels for tile generation", default="3-15"
    )
    parser.add_argument(
        "--processes", help="Number of processes for tile generation", default=4
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
    print("\n--------- Step 3/5: Croping data to tile extent ---------")
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
    print("\n--------- Step 2/5: Reprojecting Data to Mercator ---------")
    hs_dir = Path(f"{base_dir}/Tile_Data/{tile}/hillshading/")
    hs_files = glob(f"{hs_dir}/HS*")
    dem_dir = Path(f"{base_dir}/Tile_Data/{tile}/BlueTopo_VRT/")
    dem_files = glob(f"{dem_dir}/BlueTopo_*.vrt")

    reproject_files(hs_files, hs_dir / "reprojected_bluetopo.tif", "HS")
    reproject_files(dem_files, dem_dir / "reprojected_dem.tif", "DEM")

    return


def process_data(args: ArgumentParser) -> None:
    """
    Runs the full data processing workflow for a given tile and UTM zone.

    args: ArgumentParser
        Command line args specified by the user
    """
    files = glob(f"{args.base_dir}/Tile_Data/{args.tile}/BlueTopo/UTM*")
    utms = list(set(re.search(r"UTM(\d+)", f).group(1) for f in files))
    if not utms:
        print(f"No UTM directories found in Tile_Data/{args.tile}/BlueTopo")
        sys.exit(1)

    print("\n--------- Step 1/5: Running hillshading ---------")
    for utm in utms:
        run_batch_hillshading(args.tile, utm, args.base_dir)
        combine_hillshades(args.tile, utm, args.base_dir)

    reproject_data(args.tile, args.base_dir)
    crop_to_tile(args.tile, args.base_dir)


def generate_tiles(args: ArgumentParser):
    """
    Generates XYZ tiles for the hillshade and DEM files.

    args: ArgumentParser
        Command line args specified by the user
    """
    input_dem_file = f"{args.base_dir}/Tile_Data/{args.tile}/Cropped/dem_cropped.tif"
    rgba_output_file = f"{args.base_dir}/Tile_Data/{args.tile}/Cropped/dem_rgba.tif"
    xyz_dem_output_dir = f"{args.base_dir}/Tile_Data/{args.tile}/XYZ/DEM"

    print("\n--------- Step 4/5: Encoding DEM to RGBA ---------")
    encode_dem_to_rgba(input_dem_file, rgba_output_file)

    print("\n--------- Step 5/5: Generating XYZ tiles ---------")
    generate_xyz_tiles(
        rgba_output_file,
        xyz_dem_output_dir,
        args.zoom_levels,
        args.processes,
    )

    input_hs_file = f"{args.base_dir}/Tile_Data/{args.tile}/Cropped/HS_cropped.tif"
    output_hs_tiles = f"{args.base_dir}/Tile_Data/{args.tile}/XYZ/hillshade"
    generate_xyz_tiles(
        input_hs_file,
        output_hs_tiles,
        args.zoom_levels,
        args.processes,
    )


def main() -> None:
    args = parse_args()
    process_data(args)
    generate_tiles(args)


if __name__ == "__main__":
    main()
