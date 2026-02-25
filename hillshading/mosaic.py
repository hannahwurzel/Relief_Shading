import argparse
from pathlib import Path
import re
from osgeo import gdal

from data.utils import gdal_progress

gdal.UseExceptions()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run multidirectional hillshading on Mosaic data."
    )
    parser.add_argument(
        "--base_dir",
        help="Base directory where Mosaic lives",
        default="/Volumes/Crucial X10/relief_by_tile/Contains_Mosaic/lat_lon_bounds",
    )
    return parser.parse_args()


def run_mosaic_hillshading(tile: str, base_dir: str) -> None:
    """
    Runs gdal hillshade on the Mosaic.tiff file.
    """
    input_dir = Path(base_dir) / f"{tile}.tiff"
    output_dir = Path(base_dir) / f"{tile}_HS.tiff"

    print("Starting hillshading...")
    dem_options = gdal.DEMProcessingOptions(
        multiDirectional=True,
        zFactor=2.0,
    )
    gdal.DEMProcessing(
        str(output_dir),
        str(input_dir),
        "hillshade",
        options=dem_options,
    )

    print("Hillshading complete.")


def reproject_hillshading(file: str, output_file: str, num_threads: int = 6):
    """
    Reprojects Mosaic hillshading files to Mercator.

    file: str
        destination of file to reproject
    output_file: str
        output file destination
    num_threads: int
        number of threads to use while running (default: 6)
    """
    print(f"Reprojecting Mosaic tile...")

    warp_options = gdal.WarpOptions(
        dstSRS="EPSG:3857",
        srcNodata=0,
        format="GTiff",
        creationOptions=["COMPRESS=LZW", "BIGTIFF=YES", f"NUM_THREADS={num_threads}"],
        warpOptions=[f"NUM_THREADS={num_threads}"],
        multithread=True,
        callback=gdal_progress,
    )
    gdal.Warp(str(output_file), file, options=warp_options)
    Path(file).unlink()

    print(f"Reprojected Mosaic saved to {output_file}.")


def main() -> None:
    args = parse_args()

    tiles = [
        f.stem
        for f in (Path(args.base_dir)).iterdir()
        if f.suffix == ".tiff" and re.fullmatch(r"\d+_\d+_\d+", f.stem)
    ]

    for tile in tiles:
        run_mosaic_hillshading(tile, args.base_dir)

        file = f"{args.base_dir}/{tile}_HS.tiff"
        output = f"{args.base_dir}/{tile}_reprojected.tiff"
        reproject_hillshading(file, output)


if __name__ == "__main__":
    main()
