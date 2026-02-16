import argparse
from osgeo import gdal, osr
import sys
from pathlib import Path

gdal.UseExceptions()


def run_batch_hillshading(tile: str, utm: str, base_dir: str) -> None:
    """
    Runs gdal hillshade on all BlueTopo_*.tiff files using multidirectional shading and a z factor of 1.5.
    """
    base = Path(base_dir) / "Tile_Data"
    input_dir = base / tile / "BlueTopo" / f"UTM{utm}"
    output_dir = base / tile / f"UTM{utm}_hillshading"
    output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(input_dir.glob("BlueTopo_*.tiff"))

    if not files:
        print(f"No BlueTopo_*.tiff files found in {input_dir}")
        sys.exit(1)

    print("Starting hillshading...")

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

        percent = current * 100 // total
        filled = percent // 2
        bar = "█" * filled + "░" * (50 - filled)
        print(f"\r[{bar}] {current}/{total} ({percent}%)", end="", flush=True)

    print("\nHillshading complete.")


def combine_hillshades(tile: str, utm: str, base_dir: str) -> None:
    """
    Combines individual hillshade tiles into a single mosaic file.
    """
    base = Path(base_dir) / "Tile_Data"
    output_dir = base / tile / f"UTM{utm}_hillshading"
    vrt_path = output_dir / "vrt_temp.vrt"
    merged_output = output_dir / f"UTM{utm}_{tile}_HS.tif"
    tiff_files = sorted(
        f for f in output_dir.glob("*.tiff") if not f.name.startswith("._")
    )

    print("\nCombining Hillshades...")
    vrt_options = gdal.BuildVRTOptions(resolution="highest")
    vrt_ds = gdal.BuildVRT(
        str(vrt_path), [str(f) for f in tiff_files], options=vrt_options
    )
    vrt_ds.FlushCache()
    vrt_ds = None

    translate_options = gdal.TranslateOptions(format="GTiff")
    gdal.Translate(str(merged_output), str(vrt_path), options=translate_options)

    vrt_path.unlink()
    print(f"Mosaic saved to {merged_output}")


def check_crs(input_dir: Path, tiff: bool = True) -> str:
    """
    Checks if the input directory contains files with valid CRS.
    """
    if tiff:
        sample_file = next(input_dir.glob("*.tiff"), None)
    else:
        sample_file = next(input_dir.glob("*.vrt"), None)

    if sample_file is None:
        ext = "tiff" if tiff else "vrt"
        print(f"No .{ext} files found in {input_dir}")
        sys.exit(1)

    ds = gdal.Open(str(sample_file))
    wkt = ds.GetProjection()
    ds = None

    if not wkt:
        print(f"Could not determine CRS of {sample_file}")
        sys.exit(1)

    srs = osr.SpatialReference()
    srs.ImportFromWkt(wkt)
    crs = srs.ExportToProj4().strip()
    return crs


def crop_hillshade_and_vrt(tile: str, utm: str, base_dir: str) -> None:
    """
    Crops the combined hillshade and the VRT to the given tile extent.
    """
    base = Path(base_dir) / "Tile_Data"
    boundary_dir = Path(base_dir) / "Tile_Bounds" / f"{tile}.gpkg"

    output_dir = base / tile / "Cropped"
    output_dir.mkdir(parents=True, exist_ok=True)

    input_hs_file = base / tile / f"UTM{utm}_hillshading" / f"UTM{utm}_{tile}_HS.tif"
    output_hs_file = output_dir / f"UTM{utm}_HS_cropped.tif"

    input_vrt_file = base / tile / f"BlueTopo_VRT/BlueTopo_Fetched_UTM{utm}.vrt"
    output_vrt_file = output_dir / f"UTM{utm}_VRT_cropped.vrt"

    hs_crs = check_crs(input_hs_file.parent)
    vrt_crs = check_crs(input_vrt_file.parent, tiff=False)

    print(f"Cropping {input_hs_file.name}...")
    warp_options = gdal.WarpOptions(
        cutlineDSName=str(boundary_dir),
        cropToCutline=True,
        dstSRS=hs_crs,
        dstNodata=255,
        format="GTiff",
        creationOptions=["COMPRESS=LZW", "BIGTIFF=YES"],
    )
    gdal.Warp(str(output_hs_file), str(input_hs_file), options=warp_options)
    print(f"Cropped hillshade saved to {output_hs_file}.")

    print("Cropping VRT...")
    warp_options = gdal.WarpOptions(
        cutlineDSName=str(boundary_dir),
        cropToCutline=True,
        dstSRS=vrt_crs,
        dstNodata=-9999,
        format="GTiff",
        creationOptions=["COMPRESS=LZW", "BIGTIFF=YES"],
    )
    gdal.Warp(str(output_vrt_file), str(input_vrt_file), options=warp_options)
    print(f"Cropped VRT saved to {output_vrt_file}.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run multidirectional hillshading on BlueTopo tiles, combines them into \
              a single hillshade file and crops them into their level 7 zoom tile."
    )
    parser.add_argument("tile", help="Tile name in XYZ format (e.g. 7_40_37)")
    parser.add_argument(
        "--base_dir",
        help="Base directory where Tile_Data and Tile_Bounds live",
        default="/Volumes/Crucial X10/QGIS/relief_by_tile",
    )
    args = parser.parse_args()

    bluetopo_data_dir = Path(args.base_dir) / "Tile_Data" / args.tile / "BlueTopo"
    utm_dirs = [
        d
        for d in (bluetopo_data_dir).iterdir()
        if d.is_dir() and d.name.startswith("UTM")
    ]
    utms = [d.name.replace("UTM", "") for d in utm_dirs]

    if not utms:
        print(f"No UTM directories found in {bluetopo_data_dir / args.tile}")
        sys.exit(1)

    print(f"Found UTM zones: {', '.join(utms)}")

    for utm in utms:
        print(f"\n--- Processing UTM{utm} ---")
        run_batch_hillshading(args.tile, utm, args.base_dir)
        combine_hillshades(args.tile, utm, args.base_dir)
        crop_hillshade_and_vrt(args.tile, utm, args.base_dir)


if __name__ == "__main__":
    main()
