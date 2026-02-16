import argparse
from pathlib import Path
from osgeo import gdal

gdal.UseExceptions()


def run_mosaic_hillshading(tile: str, base_dir: str) -> None:
    """
    Runs gdal hillshade on the Mosaic.tiff file.
    """
    base = Path(base_dir) / "Tile_Data"
    input_output_dir = base / tile / "Mosaic"

    print("Starting hillshading...")
    dem_options = gdal.DEMProcessingOptions(
        multiDirectional=True,
        zFactor=1.5,
    )
    gdal.DEMProcessing(
        str(input_output_dir / f"Mosaic_hillshade.tiff"),
        str(input_output_dir / f"Mosaic.tiff"),
        "hillshade",
        options=dem_options,
    )
    print("Hillshading complete.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run multidirectional hillshading on Mosaic data."
    )
    parser.add_argument("tile", help="Tile name in XYZ format (e.g. 7_40_37)")
    parser.add_argument(
        "--base_dir",
        help="Base directory where Mosaic lives",
        default="/Volumes/Crucial X10/QGIS/relief_by_tile",
    )

    args = parser.parse_args()
    run_mosaic_hillshading(args.tile, args.base_dir)


if __name__ == "__main__":
    main()
