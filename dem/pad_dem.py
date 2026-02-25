# the bluetopo repo sometimes has weird spacing between tiles where its mising exactly one pixel
# this script is meant to fix that given a tile extent

from argparse import ArgumentParser
from pathlib import Path

from osgeo import gdal
import numpy as np

from data.utils import generate_xyz_tiles


def parse_args():
    parser = ArgumentParser()
    parser.add_argument("input_dir", help="location of folder containing dem_rgba.tif")
    parser.add_argument(
        "--generate_tiles",
        help="flag whether or not to genreate new XYZ tiles using the newly padded tif",
        default=False,
    )
    parser.add_argument(
        "--tile_location",
        help="if args.generate_tiles is true then this is where to output those tiles to",
    )
    return parser.parse_args()


def pad_dem_rgba_tif(
    input_tif: str,
    output_tif: str,
    top: bool = False,
    bottom: bool = False,
    left: bool = False,
    right: bool = False,
):
    """
    Pads a tiff file by one pixel on a specified side.

    input_tif: str
        input directory for tif file
    output_tif: str
        output directory
    top: bool (default: False)
        flag to add pixel to top of tif
    bottom: bool (default: False)
        flag to add pixel to bottom of tif
    left: bool (default: False)
        flag to add pixel to left of tif
    right: bool (default: False)
        flag to add pixel to right of tif
    """
    src = gdal.Open(input_tif)
    bands = [src.GetRasterBand(i + 1).ReadAsArray() for i in range(4)]
    h, w = bands[0].shape

    new_h = h + int(top) + int(bottom)
    new_w = w + int(left) + int(right)

    padded_bands = []
    for band in bands:
        padded = np.zeros((new_h, new_w), dtype=band.dtype)
        padded[int(top) : int(top) + h, int(left) : int(left) + w] = band

        if top:
            padded[0, int(left) : int(left) + w] = band[0, :]
        if bottom:
            padded[-1, int(left) : int(left) + w] = band[-1, :]
        if left:
            padded[int(top) : int(top) + h, 0] = band[:, 0]
        if right:
            padded[int(top) : int(top) + h, -1] = band[:, -1]
        padded_bands.append(padded)

    driver = gdal.GetDriverByName("GTiff")
    out = driver.Create(
        output_tif, new_w, new_h, 4, gdal.GDT_Byte, ["TILED=YES", "COMPRESS=LZW"]
    )
    out.SetGeoTransform(src.GetGeoTransform())
    out.SetProjection(src.GetProjection())

    for i, band in enumerate(padded_bands):
        out.GetRasterBand(i + 1).WriteArray(band)

    out.FlushCache()
    out = None
    src = None


tile_out = f"/Volumes/Crucial X10/relief_by_tile/XYZ/DEM"


def main() -> None:
    args = parse_args()

    input = f"{Path(args.input_dir)}/dem_rgba.tif"
    output = f"{Path(args.input_dir)}/dem_rgba_extra_pixel.tif"
    pad_dem_rgba_tif(input, output, bottom=True)

    if args.generate_tiles:
        generate_xyz_tiles(args.tile_location, tile_out, "7-15", 4)


if __name__ == "__main__":
    main()
