from argparse import ArgumentParser
import os
from osgeo import gdal
from pathlib import Path

from tqdm import tqdm

from data.utils import generate_xyz_tiles


def parse_args():
    """
    Parses a users command line arguments.
    """
    parser = ArgumentParser(
        description="Generates zoom levels 3-6 XYZ tiles for DEM tiles."
    )
    parser.add_argument(
        "--input_dir",
        help="Input directory where dem_rgba.tif files live",
        default="/Volumes/Crucial X10/relief_by_tile",
    )
    parser.add_argument(
        "--output_dir",
        help="Output directory for XYZ tiles",
        default="/Volumes/Crucial X10/relief_by_tile/XYZ/dem_low",
    )
    parser.add_argument("--min_zoom", help="Min zoom level needed", default=3)
    parser.add_argument(
        "--base_zoom", help="Base zoom level used in overview", default=7
    )
    return parser.parse_args()


def generate_overviews(
    dem_rgba_files: list, output_dir: str, min_zoom: int = 3, base_zoom: int = 7
) -> str:
    """
    Generates GDAL Overview for a list of files

    dem_rgba_files: list
        list of dem files to use in the overview
    output_dir: str
        output directory
    min_zoom: int (default: 3)
        minimum zoom level needed
    base_zoom: int (default: 7)
        zoom level that the given dem files were created with
    """
    os.makedirs(output_dir, exist_ok=True)

    # Build VRT
    vrt_path = Path(output_dir) / "dem_z7.vrt"
    print(f"Building VRT: {vrt_path}")
    vrt = gdal.BuildVRT(str(vrt_path), dem_rgba_files, resolution="highest")
    if vrt is None:
        raise RuntimeError("Failed to build VRT")
    vrt = None

    ds = gdal.Open(str(vrt_path), gdal.GA_Update)
    if ds is None:
        raise RuntimeError("Failed to open VRT for overviews")

    overview_levels = [
        2 ** (base_zoom - z) for z in range(base_zoom - 1, min_zoom - 1, -1)
    ]

    print(f"Building overviews for zooms {min_zoom}-{base_zoom-1}")
    with tqdm(total=100, desc="Building overviews", unit="%") as pbar:
        last_progress = 0

        def progress_cb(complete, message, unknown):
            nonlocal last_progress
            progress = int(complete * 100)
            pbar.update(progress - last_progress)
            last_progress = progress
            if message:
                tqdm.write(message)
            return 1

        ds.BuildOverviews("average", overview_levels, callback=progress_cb)

    ds = None
    return str(vrt_path)


def main() -> None:
    args = parse_args()

    cropped_dirs = Path(args.input_dir).glob("*Mosaic/Tile_Data/*/Cropped")
    inputs = []
    for cropped in cropped_dirs:
        extra = cropped / "dem_rgba_extra_pixel.tif"
        base = cropped / "dem_rgba.tif"

        if extra.exists():
            inputs.append(str(extra))
        elif base.exists():
            inputs.append(str(base))

    vrt_path = generate_overviews(inputs, args.output_dir)
    generate_xyz_tiles(vrt_path, args.output_dir, "3-6", 6)


if __name__ == "__main__":
    main()
