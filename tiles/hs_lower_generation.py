from argparse import ArgumentParser
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import mercantile
from osgeo import gdal
from pyproj import Transformer
from tqdm import tqdm

gdal.UseExceptions()


def parse_args():
    parser = ArgumentParser("Generates hillshade tiles for zoom levels 3 - 6.")
    parser.add_argument(
        "--base_dir",
        help="base directory containing No_Mosaic and Contains_Mosaic folders",
        default="/Volumes/Crucial X10/relief_by_tile/",
    )
    return parser.parse_args()


def get_hs_path(tile: mercantile.Tile, root: Path) -> Path | None:
    """Returns the path to HS_cropped.tif for a given tile, searching both subdirectories."""
    folder_name = f"{tile.z}_{tile.x}_{tile.y}"
    for subdir in ["No_Mosaic", "Contains_Mosaic"]:
        path = root / subdir / "Tile_Data" / folder_name / "HS_cropped.tif"
        if path.exists():
            return path
    return None


def get_source_hs_for_tile(tile: mercantile.Tile, root: Path) -> list[Path]:
    """Returns paths to all zoom 7 hillshade files that fall under the given tile."""
    children = mercantile.children(tile, zoom=7)
    return [p for child in children if (p := get_hs_path(child, root)) is not None]


def get_region_bbox(root: Path) -> tuple:
    """
    Derives the region bounding box in EPSG:4326 degrees by scanning all
    z_x_y folders under both No_Mosaic/Tile_Data and Contains_Mosaic/Tile_Data.
    """
    transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

    tile_dirs = [
        root / "No_Mosaic" / "Tile_Data",
        root / "Contains_Mosaic" / "Tile_Data",
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

    if not tiles:
        raise ValueError(f"No valid tile folders found under {root}")

    all_bounds = [mercantile.xy_bounds(t) for t in tiles]
    min_x = min(b.left for b in all_bounds)
    min_y = min(b.bottom for b in all_bounds)
    max_x = max(b.right for b in all_bounds)
    max_y = max(b.top for b in all_bounds)

    west, south = transformer.transform(min_x, min_y)
    east, north = transformer.transform(max_x, max_y)

    return (west, south, east, north)


def tile_bounds_mercator(tile: mercantile.Tile) -> tuple:
    """Returns tile bounds in EPSG:3857 meters as (west, south, east, north)."""
    b = mercantile.xy_bounds(tile)
    return (b.left, b.bottom, b.right, b.top)


def generate_tile(
    tile: mercantile.Tile,
    source_files: list[Path],
    output_dir: Path,
    tile_size: int = 256,
) -> None:
    """
    Generates a single grayscale hillshade tile by mosaicking and resampling
    zoom 7 source files down to 256x256. Nodata value of 255 is masked out
    during resampling to prevent bleeding into valid pixels.
    """
    bounds = tile_bounds_mercator(tile)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = str(output_dir / f"{tile.z}_{tile.x}_{tile.y}.tif")

    vrt = gdal.BuildVRT(
        "",
        [str(p) for p in source_files],
        outputBounds=bounds,
        resampleAlg="average",
        srcNodata=255,
        VRTNodata=255,
    )

    gdal.Warp(
        output_file,
        vrt,
        outputBounds=bounds,
        width=tile_size,
        height=tile_size,
        resampleAlg="average",
        dstSRS="EPSG:3857",
        srcNodata=255,
        dstNodata=255,
        options=gdal.WarpOptions(
            creationOptions=["TILED=YES", "COMPRESS=LZW", "BIGTIFF=IF_SAFER"]
        ),
    )
    vrt = None


def process_tile(args):
    tile, source_files, output_dir = args
    generate_tile(tile, source_files, output_dir)
    return tile, len(source_files)


def main():
    cmd_args = parse_args()
    root = Path(cmd_args.base_dir)
    output_dir = root / "Low_Zoom" / "Hillshade"

    print("Deriving region bbox from zoom 7 folders...")
    region_bbox = get_region_bbox(root)
    print(f"Region bbox (degrees): {region_bbox}")

    for zoom in range(3, 7):
        tiles = list(mercantile.tiles(*region_bbox, zooms=zoom))

        tile_args = []
        for tile in tiles:
            sources = get_source_hs_for_tile(tile, root)
            if not sources:
                continue
            tile_args.append((tile, sources, output_dir))

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
