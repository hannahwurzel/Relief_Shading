from argparse import ArgumentParser
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import mercantile
import numpy as np
from osgeo import gdal
from pyproj import Transformer
from tqdm import tqdm

gdal.UseExceptions()


def parse_args():
    parser = ArgumentParser(
        "Generates the RGBA encoding for zoom levels 3 - 6 using the zoom level 7 DEM \
            and then generates XYZ tiles for those RGBA encoded tif files."
    )
    parser.add_argument(
        "--base_dir",
        help="input directory for dem_cropped.tif",
        default="/Volumes/Crucial X10/relief_by_tile/",
    )
    parser.add_argument(
        "--depth_min", help="min depth used for encoding", default=-6000.0
    )
    parser.add_argument(
        "--depth_max", help="max depth used for encoding", default=500.0
    )
    return parser.parse_args()


def process_tile(args: set):
    """
    Runs the generate_tile script. Checks that source_files exists first.

    args: set
        (tile, source_files, output_dir, depth_min, depth_max)
    """
    tile, source_files, output_dir, depth_min, depth_max = args
    if not source_files:
        return tile, 0

    generate_tile(
        tile, source_files, output_dir, depth_min=depth_min, depth_max=depth_max
    )
    return tile, len(source_files)


def get_dem_path(tile: mercantile.Tile, dem_root: Path) -> Path | None:
    """
    Returns the path to dem_cropped.tif for a given tile, searching both subdirectories.

    tile: mercantile.Tile
        given tile
    dem_root: Path
        path to DEM files

    returns: Path | None
        returns the path to a DEM file if it exists
    """
    # get_dem_path
    folder_name = f"{tile.z}_{tile.x}_{tile.y}"
    for subdir in ["No_Mosaic", "Contains_Mosaic"]:
        path = (
            dem_root
            / subdir
            / "Tile_Data"
            / folder_name
            / "Cropped"
            / "dem_cropped.tif"
        )
        if path.exists():
            return path
    return None


def get_source_dems_for_tile(tile: mercantile.Tile, dem_root: Path) -> list[Path]:
    """
    Returns paths to all zoom 7 DEM files that fall under the given tile.

    tile: mercantile.Tile
        given tile
    dem_root: Path
        path to DEM files

    returns: list[Path]
        a list of the paths that fall under a given tile
    """
    children = mercantile.children(tile, zoom=7)
    paths = []
    for child in children:
        path = get_dem_path(child, dem_root)
        if path is not None:
            paths.append(path)

    return paths


def get_region_bbox(dem_root: Path) -> tuple:
    """
    Gets the overall bounding box region containing all of the level 7 zoom DEM files.

    dem_root: Path
        path to DEM files

    returns: tuple
        returns the coordinates of the bounding box in this format: (west, south, east, north)
    """
    transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

    tile_dirs = [
        dem_root / "No_Mosaic" / "Tile_Data",
        dem_root / "Contains_Mosaic" / "Tile_Data",
    ]

    tiles = []
    for tile_dir in tile_dirs:
        if not tile_dir.exists():
            print(f"Warning: {tile_dir} does not exist, skipping.")
            continue
        for folder in tile_dir.iterdir():
            if folder.is_dir():
                parts = folder.name.split("_")
                if len(parts) == 3:
                    z, x, y = parts
                    tiles.append(mercantile.Tile(int(x), int(y), int(z)))

    all_bounds = [mercantile.xy_bounds(t) for t in tiles]
    min_x = min(b.left for b in all_bounds)
    min_y = min(b.bottom for b in all_bounds)
    max_x = max(b.right for b in all_bounds)
    max_y = max(b.top for b in all_bounds)

    west, south = transformer.transform(min_x, min_y)
    east, north = transformer.transform(max_x, max_y)

    return (west, south, east, north)


def tile_bounds_mercator(tile: mercantile.Tile) -> tuple:
    """
    Returns tile bounds in EPSG:3857 meters as (west, south, east, north).

    tile: mercantile.Tile
        the given tile

    returns: tuple
        tile bounds from the given tile
    """
    b = mercantile.xy_bounds(tile)
    return (b.left, b.bottom, b.right, b.top)


def encode_dem_to_rgba_from_ds(
    source: gdal.Dataset,
    output_file: str,
    depth_min: float = -6000.0,
    depth_max: float = 500.0,
) -> None:
    """
    Encodes an in-memory GDAL dataset to an RGBA GeoTIFF using 24-bit linear
    normalization. Valid pixel values are encoded as 1-16777215; 0 = nodata.

    source: gdal.Dataset
        the source DEM
    output_file: str
        output file location
    depth_min: float (Default: -6000.0)
        min depth to encode with
    depth_max: float (Default: 500.0)
        max depth to encode with
    """
    band = source.GetRasterBand(1)
    nodata = band.GetNoDataValue()
    x_size = source.RasterXSize
    y_size = source.RasterYSize

    driver = gdal.GetDriverByName("GTiff")
    out = driver.Create(
        output_file,
        x_size,
        y_size,
        4,
        gdal.GDT_Byte,
        ["TILED=YES", "COMPRESS=LZW", "BIGTIFF=IF_SAFER"],
    )
    out.SetGeoTransform(source.GetGeoTransform())
    out.SetProjection(source.GetProjection())

    data = band.ReadAsArray()
    valid = np.ones_like(data, dtype=bool)
    if nodata is not None:
        valid = data != nodata

    result = np.zeros_like(data, dtype=np.float32)
    result[valid] = (data[valid] - depth_min) / (depth_max - depth_min)
    result = np.clip(result, 0, 1)

    encoded = np.zeros_like(result, dtype=np.uint32)
    encoded[valid] = (result[valid] * 16777214).astype(np.uint32) + 1
    encoded[~valid] = 0

    r = (encoded >> 16).astype(np.uint8)
    g = ((encoded >> 8) & 0xFF).astype(np.uint8)
    b = (encoded & 0xFF).astype(np.uint8)
    a = np.where(valid, 255, 0).astype(np.uint8)
    r[~valid] = 0
    g[~valid] = 0
    b[~valid] = 0

    out.GetRasterBand(1).WriteArray(r)
    out.GetRasterBand(2).WriteArray(g)
    out.GetRasterBand(3).WriteArray(b)
    out.GetRasterBand(4).WriteArray(a)
    out.FlushCache()
    out = None


def generate_tile(
    tile: mercantile.Tile,
    source_files: list[Path],
    output_dir: Path,
    tile_size: int = 256,
    depth_min: float = -6000.0,
    depth_max: float = 500.0,
) -> None:
    """
    Generates a single RGBA encoded DEM tile. If no source DEMs exist for
    this tile, writes a fully nodata tile instead.

    tile: mercantile.Tile
        the given tile
    source_files: list[Path]
        list containing the source DEM files
    output_dir: Path
        path to output directory
    tile_size: int (Default: 256)
        size of tile
    depth_min: float (Default: -6000.0)
        minimum depth value to encode
    depth_max: float (Default: 500.0)
        maximum depth value to encode
    """
    bounds = tile_bounds_mercator(tile)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = str(output_dir / f"{tile.z}_{tile.x}_{tile.y}.tif")

    if not source_files:
        print(f"no source files for {tile}")
        return

    vrt = gdal.BuildVRT(
        "",
        [str(p) for p in source_files],
        outputBounds=bounds,
        resampleAlg="average",
    )

    warped = gdal.Warp(
        "",
        vrt,
        format="MEM",
        outputBounds=bounds,
        width=tile_size,
        height=tile_size,
        resampleAlg="average",
        dstSRS="EPSG:3857",
    )
    vrt = None

    encode_dem_to_rgba_from_ds(
        warped, output_file, depth_min=depth_min, depth_max=depth_max
    )
    warped = None


def main():
    cmd_args = parse_args()

    output_dir = Path(cmd_args.base_dir) / "Low_Zoom" / "DEM_RGBA"

    region_bbox = get_region_bbox(Path(cmd_args.base_dir))
    print(f"Region bbox (degrees): {region_bbox}")

    for zoom in range(4, 2, -1):
        tiles = list(mercantile.tiles(*region_bbox, zooms=zoom))
        tile_args = []
        for tile in tiles:
            sources = get_source_dems_for_tile(tile, Path(cmd_args.base_dir))
            if not sources:
                continue
            tile_args.append(
                (tile, sources, output_dir, cmd_args.depth_min, cmd_args.depth_max)
            )

        print(
            f"\n----- Zoom {zoom}: {len(tiles)} tiles ({len(tile_args)} with data) -----"
        )

        with ProcessPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(process_tile, args): args[0] for args in tile_args
            }
            with tqdm(total=len(futures), desc=f"Zoom {zoom}") as pbar:
                for future in as_completed(futures):
                    tile, n_sources = future.result()
                    pbar.set_postfix(
                        tile=f"{tile.z}_{tile.x}_{tile.y}", sources=n_sources
                    )
                    pbar.update(1)


if __name__ == "__main__":
    main()
