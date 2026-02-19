from osgeo import gdal
import numpy as np

gdal.UseExceptions()


def encode_dem_to_rgba(
    input_file: str,
    output_file: str,
    block_size: int = 14000,
    depth_min: float = -5000.0,
    depth_max: float = 500.0,
) -> None:
    """
    Encodes DEM file to RGBA format.

    input_file: str
        input file location
    output_file: str
        location where you want the output rgba encoded dem
    block_size: int
        #TO DO
    depth_min: float
        minimum depth value across all tiles
    depth_max: float
        maximum depth value across all tiles
    """
    print("Encoding DEM to RGBA...")
    try:
        source = gdal.Open(input_file)
        band = source.GetRasterBand(1)
        nodata = band.GetNoDataValue()

        x_size = source.RasterXSize
        y_size = source.RasterYSize

        driver = gdal.GetDriverByName("GTiff")
        out = driver.Create(
            str(output_file),
            x_size,
            y_size,
            4,
            gdal.GDT_Byte,
            ["TILED=YES", "COMPRESS=LZW", "BIGTIFF=IF_SAFER"],
        )
        out.SetGeoTransform(source.GetGeoTransform())
        out.SetProjection(source.GetProjection())

        r_band = out.GetRasterBand(1)
        g_band = out.GetRasterBand(2)
        b_band = out.GetRasterBand(3)
        a_band = out.GetRasterBand(4)

        for y_off in range(0, y_size, block_size):
            y_block = min(block_size, y_size - y_off)
            for x_off in range(0, x_size, block_size):
                x_block = min(block_size, x_size - x_off)

                data = band.ReadAsArray(x_off, y_off, x_block, y_block)

                valid = np.ones_like(data, dtype=bool)
                if nodata is not None:
                    valid = data != nodata

                # Linear normalization
                result = np.zeros_like(data, dtype=np.float32)
                result[valid] = (data[valid] - depth_min) / (depth_max - depth_min)
                result = np.clip(result, 0, 1)

                # Scale to 24-bit, reserve 0 for nodata
                encoded = np.zeros_like(result, dtype=np.uint32)
                encoded[valid] = (result[valid] * 16777214).astype(
                    np.uint32
                ) + 1  # 1 to 16777215
                encoded[~valid] = 0  # nodata = 0

                r = (encoded >> 16).astype(np.uint8)
                g = ((encoded >> 8) & 0xFF).astype(np.uint8)
                b = (encoded & 0xFF).astype(np.uint8)
                a = np.zeros_like(r, dtype=np.uint8)
                a[valid] = 255
                a[~valid] = 0

                r[~valid] = 0
                g[~valid] = 0
                b[~valid] = 0

                # Write chunk
                r_band.WriteArray(r, x_off, y_off)
                g_band.WriteArray(g, x_off, y_off)
                b_band.WriteArray(b, x_off, y_off)
                a_band.WriteArray(a, x_off, y_off)

                # Free memory
                del data, result, encoded, r, g, b, a, valid

        out.FlushCache()
        out = None
        source = None

        return True

    except RuntimeError as e:
        print(f"Error opening {input_file}: {e}")
        return False
