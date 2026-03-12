"""
Encode alpha channel of hillshade XYZ tiles based on pixel brightness.
Useful to get rid of noise in flat areas as these alpha values are associated with opacity.
"""

import argparse
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from scipy.ndimage import uniform_filter

try:
    from PIL import Image
    import numpy as np
except ImportError:
    print("Missing dependencies. Install with:")
    print("  pip install Pillow numpy --break-system-packages")
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Encode hillshade tile alpha channel from pixel brightness."
    )
    parser.add_argument(
        "input_folder",
        help="Root folder containing XYZ tile structure (z/x/y.png)",
    )
    parser.add_argument(
        "--inplace",
        action="store_true",
        help="Overwrite original tiles instead of writing to a new folder.",
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=8,
        help="Number of parallel worker threads (default: 8).",
    )
    return parser.parse_args()


def process_tile(src_path: Path, dst_path: Path) -> tuple[str, bool, str]:
    """Process a single tile: encode alpha from brightness."""
    try:
        img = Image.open(src_path).convert("RGBA")
        arr = np.array(img, dtype=np.float32)

        # Compute luminance from RGB channels (standard perceptual weights)
        luminance = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]

        # Sigmoid ramp
        midpoint = 0.3
        steepness = 10
        darkness = 1.0 - luminance / 255.0
        alpha_sigmoid = 1.0 / (1.0 + np.exp(-steepness * (darkness - midpoint)))

        # Boost alpha where there is local contrast (e.g. light face of a ridge next to a dark face)
        blur = uniform_filter(luminance, size=5)
        contrast = np.abs(luminance - blur) / 255.0
        contrast_boost = 3.0
        alpha_combined = np.clip(alpha_sigmoid + contrast * contrast_boost, 0, 1)

        alpha = (alpha_combined * 255.0).astype(np.uint8)

        # Preserve intentionally transparent pixels from the source
        alpha[arr[:, :, 3] == 0] = 0

        # Build output RGBA: keep original RGB, replace alpha
        out = arr.astype(np.uint8)
        out[:, :, 3] = alpha

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(out, "RGBA").save(dst_path, "PNG", optimize=False)

        return str(src_path), True, ""
    except Exception as e:
        return str(src_path), False, str(e)


def collect_tiles(src_root: Path) -> list[tuple[Path, Path]]:
    """Walk XYZ folder structure and collect (src, dst) pairs."""
    pairs = []
    for p in sorted(src_root.rglob("*.png")):
        rel = p.relative_to(src_root)
        pairs.append((p, rel))
    return pairs


def main():
    args = parse_args()

    src_root = Path(args.input_folder).resolve()
    if not src_root.is_dir():
        print(f"Error: '{src_root}' is not a directory.")
        sys.exit(1)

    if args.inplace:
        dst_root = src_root
    else:
        dst_root = src_root.parent / "alpha"

    tiles = collect_tiles(src_root)
    if not tiles:
        print(f"No PNG tiles found under '{src_root}'.")
        sys.exit(1)

    print(f"Found {len(tiles):,} tiles")
    print(f"Input:  {src_root}")
    print(f"Output: {dst_root}")
    print(f"Workers: {args.workers}")
    print()

    ok = 0
    fail = 0
    errors = []

    jobs = [(src, dst_root / rel) for src, rel in tiles]

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process_tile, src, dst): src for src, dst in jobs}
        for i, future in enumerate(as_completed(futures), 1):
            path, success, err = future.result()
            if success:
                ok += 1
            else:
                fail += 1
                errors.append((path, err))

            if i % 500 == 0 or i == len(tiles):
                pct = i / len(tiles) * 100
                print(
                    f"  [{i:>{len(str(len(tiles)))}}/{len(tiles)}] {pct:5.1f}%  ✓ {ok}  ✗ {fail}",
                    end="\r",
                )

    print()
    print(f"\nDone. {ok:,} succeeded, {fail:,} failed.")

    if errors:
        print("\nFailed tiles:")
        for path, err in errors[:20]:
            print(f"  {path}: {err}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more.")


if __name__ == "__main__":
    main()
