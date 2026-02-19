from pathlib import Path
import shutil
from osgeo import gdal
from osgeo_utils import gdal2tiles
from nbs.bluetopo import fetch_tiles, build_vrt

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
    print("\n--------- Step 1/6: Fetching BlueTopo Data ---------")
    fetch_tiles(download_path, tile_bounds)
    build_vrt(download_path)


def reproject_files(files: list, output_file: str, type: str, num_threads: int = 6):
    """
    Reprojects the data to Web Mercator (EPSG:3857).

    files: list
        a list of files to reproject
    output_file: str
        output file location of the reprojected files
    type: str
        type of files (either HS or DEM)
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


def generate_xyz_tiles(
    input_tif: str,
    output_dir: str,
    zoom_levels: str,
    processes: int,
) -> None:
    """
    Generates XYZ tiles from RGBA TIFF files and Hillshading files.

    input_tif: str
        input file location
    output_dir: str
        output file location for XYZ tiles
    zoom_levels: str
        zoom levels you want to generate XYZ tiles for
    processes: int
        the number of processes you want to use for generating tiles
    """
    input_tif = Path(input_tif)
    output_dir = Path(output_dir)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating tiles {zoom_levels}...")
    gdal2tiles.main(
        [
            "gdal2tiles.py",
            "-z",
            str(zoom_levels),
            "-w",
            "none",
            "--xyz",
            "-r",
            "near",
            "-x",
            f"--processes={processes}",
            str(input_tif),
            str(output_dir),
        ]
    )

    tile_count = sum(1 for _ in output_dir.rglob("*.png"))
    print(f"Generated {tile_count} tiles in {output_dir}")

    return True
