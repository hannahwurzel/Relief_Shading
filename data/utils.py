from pathlib import Path
import shutil
import subprocess
import tempfile
import numpy as np
from osgeo import gdal
from PIL import Image
from nbs.bluetopo import fetch_tiles, build_vrt
import rasterio
from tqdm import tqdm


gdal.SetConfigOption("CPL_LOG", "/dev/null")


def gdal_progress(complete, message, data) -> None:
    """
    Displays a progress bar on the screen for the current gdal process.
    """
    filled = int(complete * 40)
    bar = "█" * filled + "░" * (40 - filled)
    percent = complete * 100
    print(f"\r[{bar}] {percent:.1f}%", end="", flush=True)
    if complete == 1.0:
        print()
    return 1


def fetch_bluetopo_data(download_path: str, tile_bounds: str) -> None:
    """
    Downloads BlueTopo tiles for the area of interest and builds a VRT.

    download_path: str
        Directory where tiles will be saved
    tile_bounds: str
        Path to {tile}.gpkg
    """
    print("\n--------- Step 1/7: Fetching BlueTopo Data ---------")
    fetch_tiles(download_path, tile_bounds)
    build_vrt(download_path)


def reproject_files(files: list, output_file: str, type: str, num_threads: int = 6):
    """
    Reprojects files to Mercator.

    files: list
        list of files to reproject
    output_file: str
        output file destination
    type: str
        type of file that is being reprojected
    num_threads: int
        number of threads to use while running (default: 6)
    """
    print(f"Reprojecting {type}...")

    nodata = 0 if type == "HS" else -9999
    warp_options = gdal.WarpOptions(
        dstSRS="EPSG:3857",
        dstNodata=nodata,
        format="GTiff",
        creationOptions=["COMPRESS=LZW", "BIGTIFF=YES", f"NUM_THREADS={num_threads}"],
        warpOptions=[f"NUM_THREADS={num_threads}"],
        multithread=True,
        callback=gdal_progress,
    )
    gdal.Warp(str(output_file), [str(f) for f in files], options=warp_options)

    # Post-warp masking for DEM to catch any land values that slipped through
    if type == "DEM":
        with rasterio.open(output_file, "r+") as dst:
            data = dst.read(1)
            data = np.where(data >= 0, -9999, data)
            dst.write(data.astype(np.float32), 1)

    print(f"Reprojected {type} saved to {output_file}.")


def crop_data(input_file: str, output_file: str, boundary_file: str, type: str) -> None:
    """
    Crops the given data to the given tile extent.

    input_file: str
        location of the input file
    output_file: str
        output file location of the cropped data
    boundary_dir: str
        the file containing the tile gpkg
    type: str
        type of data (either HS or DEM)
    """
    print(f"Cropping {type}...")
    warp_options = gdal.WarpOptions(
        cutlineDSName=str(boundary_file),
        cropToCutline=True,
        dstSRS="EPSG:3857",
        dstNodata=255,
        format="GTiff",
        creationOptions=["COMPRESS=LZW", "BIGTIFF=YES"],
        callback=gdal_progress,
    )
    gdal.Warp(str(output_file), str(input_file), options=warp_options)
    print(f"Cropped {type} saved to {output_file}.")


def count_valid_pixels(tile_path: Path) -> int:
    """
    Count non-transparent pixels in a PNG tile.

    tile_path: Path
        path to tile gpkg
    """
    img = np.array(Image.open(tile_path))
    if img.shape[2] == 4:  # has alpha channel
        return np.sum(img[:, :, 3] > 0)
    return img.shape[0] * img.shape[1]  # no alpha, all pixels valid


def generate_xyz_tiles(
    input: str,
    output_dir: str,
    zoom_levels: str,
    processes: int,
) -> None:
    """
    Generates XYZ tiles from RGBA TIFF files and Hillshading files within the boundaries
    in the given tile_path.

    input: str
        input file location
    output_dir: str
        output file location for XYZ tiles
    zoom_levels: str
        zoom levels you want to generate XYZ tiles for
    processes: int
        the number of processes you want to use for generating tiles
    """
    input = Path(input)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tmp_parent = Path("/Volumes/Crucial X10/tmp")
    tmp_parent.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory(dir=tmp_parent) as tmp_dir:
        subprocess.run(
            [
                "gdal2tiles.py",
                f"--zoom={zoom_levels}",
                "-w",
                "none",
                "--xyz",
                "-r",
                "near",
                "-x",
                f"--processes={processes}",
                str(input),
                tmp_dir,
            ],
            check=True,
        )

        copied = 0
        skipped = 0
        replaced = 0

        # gdal2tiles tends to create pngs in neighboring tiles with a few pixels
        # we need to check if a png already exists and if it does, compare it to
        # the existing one to see which one is the real one
        tiles = [f for f in Path(tmp_dir).rglob("*.png") if not f.name.startswith("._")]
        for tile in tqdm(tiles, desc="Copying tiles"):
            relative = tile.relative_to(tmp_dir)
            dest = output_dir / relative

            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(tile, dest)
                copied += 1
            else:
                new_pixels = count_valid_pixels(tile)
                existing_pixels = count_valid_pixels(dest)
                if new_pixels > existing_pixels:
                    shutil.copy2(tile, dest)
                    replaced += 1
                else:
                    skipped += 1

    print(
        f"Copied {copied} new, replaced {replaced} with better tiles, skipped {skipped}"
    )
    return True
