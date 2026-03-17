from pathlib import Path
import numpy as np
from PIL import Image


def remove_edge_pixels(
    tile_ids: list, side: str, tiles_root: str, output_root: str = None
):
    side = side.lower()
    if side not in ("top", "bottom", "left", "right"):
        raise ValueError("side must be one of: top, bottom, left, right")

    tiles_root = Path(tiles_root)
    output_root = Path(output_root) if output_root else None

    for tile_id in tile_ids:
        z, x, y = tile_id.split("_")
        input_path = tiles_root / z / x / f"{y}.png"

        if not input_path.exists():
            print(f"  [MISSING] {input_path}")
            continue

        img = Image.open(input_path).convert("RGBA")
        arr = np.array(img)

        if side == "right":
            # For each row, find the rightmost non-transparent pixel and clear it
            for row in range(arr.shape[0]):
                cols = np.where(arr[row, :, 3] > 0)[0]
                if len(cols) > 0:
                    arr[row, cols[-1], :] = 0  # set rightmost to transparent

        elif side == "left":
            # For each row, find the leftmost non-transparent pixel and clear it
            for row in range(arr.shape[0]):
                cols = np.where(arr[row, :, 3] > 0)[0]
                if len(cols) > 0:
                    arr[row, cols[0], :] = 0

        elif side == "bottom":
            # For each column, find the bottommost non-transparent pixel and clear it
            for col in range(arr.shape[1]):
                rows = np.where(arr[:, col, 3] > 0)[0]
                if len(rows) > 0:
                    arr[rows[-1], col, :] = 0  # set bottommost to transparent

        elif side == "top":
            # For each column, find the topmost non-transparent pixel and clear it
            for col in range(arr.shape[1]):
                rows = np.where(arr[:, col, 3] > 0)[0]
                if len(rows) > 0:
                    arr[rows[0], col, :] = 0

        result = Image.fromarray(arr)

        if output_root:
            out_path = output_root / z / x / f"{y}.png"
            out_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            out_path = input_path

        result.save(out_path)
        print(f"  [DONE] {tile_id} ({side}) → {out_path}")


# --- Tile lists ---
remove_right = [
    "7_40_48",
    "7_40_47",
    "7_40_46",
    "6_19_24",
    "5_9_12",
    "3_2_3",
]

remove_bottom = [
    "7_36_55",
    "7_35_55",
    "7_34_55",
    "7_33_55",
    "7_32_55",
    "5_9_12",
    "4_4_6",
    "3_2_3",
]

# --- Run ---
tiles_root = "/Volumes/Crucial X10/relief_by_tile/XYZ/hillshade_new"
output_root = None

remove_edge_pixels(
    remove_right, side="right", tiles_root=tiles_root, output_root=output_root
)
remove_edge_pixels(
    remove_bottom, side="bottom", tiles_root=tiles_root, output_root=output_root
)
