from glob import glob

import numpy as np
from osgeo import gdal
import sys
from pathlib import Path

import rasterio

from data.utils import gdal_progress


gdal.UseExceptions()


def run_batch_hillshading(tile: str, utm: int, base_dir: str) -> None:
    """
    Runs gdal hillshade on all BlueTopo_*.tiff files using multidirectional shading and a z factor of 1.5.

    tile: str
        a string denoting the tile we are working with (eg. 7_38_48)
    utm: int
        the UTM zone for this section of data
    base_dir: str
        base directory where all of the files live
    """
    base = Path(base_dir) / "Tile_Data"
    files = sorted(base.glob(f"{tile}/BlueTopo/UTM{utm}/BlueTopo_*.tiff"))
    output_dir = base / tile / "hillshading" / f"hillshading_UTM{utm}"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not files:
        print(f"No BlueTopo_*.tiff files found.")
        sys.exit(1)

    total = len(files)
    for current, file in enumerate(files, start=1):
        filename = file.stem.split("_", 1)[1]
        output_file = output_dir / f"hillshade_{filename}.tiff"

        dem_options = gdal.DEMProcessingOptions(
            multiDirectional=True,
            zFactor=1.5,
        )
        gdal.DEMProcessing(
            str(output_file), str(file), "hillshade", options=dem_options
        )

        gdal_progress(current / total, None, None)

    print(f"\nUTM{utm} hillshading complete.")


def combine_hillshades(tile: str, utm: str, base_dir: str) -> None:
    """
    Combines individual hillshade tiles into a single mosaic file.

    tile: str
        a string denoting the tile we are working with (eg. 7_38_48)
    utm: int
        the UTM zone for this section of data
    base_dir: str
        base directory where all of the files live
    """
    print(f"Combining UTM{utm} hillshades...")
    base = Path(base_dir) / "Tile_Data"
    output_dir = base / tile / "hillshading" / f"hillshading_UTM{utm}"
    vrt_path = output_dir / "vrt_temp.vrt"
    merged_output = output_dir.parent / f"HS_{utm}_combined.tif"
    tiff_files = sorted(
        f for f in output_dir.glob("*.tiff") if not f.name.startswith("._")
    )

    vrt_options = gdal.BuildVRTOptions(resolution="highest")
    vrt_ds = gdal.BuildVRT(
        str(vrt_path), [str(f) for f in tiff_files], options=vrt_options
    )
    vrt_ds.FlushCache()
    vrt_ds = None

    translate_options = gdal.TranslateOptions(format="GTiff")
    gdal.Translate(str(merged_output), str(vrt_path), options=translate_options)

    vrt_path.unlink()
    print(f"Combined hillshades saved to {merged_output}")


def mask_land_data(tile: str, base_dir: str) -> None:
    print("\n--------- Step 2/7: Masking Land Data ---------")
    base = Path(base_dir) / "Tile_Data"
    files = sorted(base.glob(f"{tile}/BlueTopo/UTM*/BlueTopo_*.tiff"))

    if not files:
        print(f"No BlueTopo_*.tiff files found.")
        sys.exit(1)

    total = len(files)
    for current, file in enumerate(files, start=1):
        with rasterio.open(file) as src:
            data = src.read(1)
            profile = src.profile
            nodata_val = src.nodata if src.nodata is not None else -9999

        data = np.where(data >= 0, nodata_val, data)

        profile.update(dtype=rasterio.float32, nodata=nodata_val)
        with rasterio.open(file, "w", **profile) as dst:
            dst.write(data.astype(np.float32), 1)

        gdal_progress(current / total, None, None)

    print(f"Land masking complete.")
