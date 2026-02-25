from argparse import ArgumentParser
from pathlib import Path
import shutil

from tqdm import tqdm

from data.utils import count_valid_pixels


def parse_args():
    parser = ArgumentParser(
        description="Extra tiles containing only a few pixels are created in QGIS and GDAL \
            when you generate XYZ tiles. This checks that these mistake tiles aren't \
            overriding legit tiles."
    )
    parser.add_argument(
        "--input_dir",
        help="Base directory where bluetopo & mosaic combined hillshading lives",
        default="/Users/hannahwurzel/Desktop/mosaic_xyz",
    )
    parser.add_argument(
        "--output_dir",
        help="Base directory where bluetopo & mosaic combined hillshading lives",
        default="/Volumes/Crucial X10/relief_by_tile/XYZ/hillshade",
    )
    return parser.parse_args()


def merge_mosaic_tiles(mosaic_dir: str, output_dir: str):
    """
    This checks if a tile has a duplicate and selects the one with the most pixels.

    mosaic_dir: str
        directory containing xyz files
    output_dir: str
        output directory
    """
    mosaic_path = Path(mosaic_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    copied = replaced = skipped = 0

    subregions = [d for d in mosaic_path.iterdir() if d.is_dir()]

    for subregion in subregions:
        tiles = [f for f in subregion.rglob("*.png") if not f.name.startswith("._")]

        for tile in tqdm(tiles, desc=f"Processing {subregion.name}"):
            relative = tile.relative_to(subregion)
            dest = output_path / relative

            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(tile, dest)
                copied += 1
            else:
                new_pixels = count_valid_pixels(tile)
                existing_pixels = count_valid_pixels(dest)
                if new_pixels >= existing_pixels:
                    shutil.copy2(tile, dest)
                    replaced += 1
                else:
                    skipped += 1

    print(f"\nDone. Copied: {copied}, Replaced: {replaced}, Skipped: {skipped}")


def main() -> None:
    args = parse_args()

    merge_mosaic_tiles(args.input_dir, args.output_dir)


if __name__ == "__main__":
    main()
