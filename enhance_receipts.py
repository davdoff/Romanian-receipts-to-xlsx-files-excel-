"""
Receipt Image Enhancer
----------------------
Processes receipt images from an input folder and saves enhanced versions
to an output folder of your choice.

Enhancements applied (in order):
  1. Shadow removal      — flattens uneven lighting/shadows using morphological dilate + divide
  2. Crease reduction    — bilateral filter preserves edges while smoothing crease artifacts
  3. Text enhancement    — CLAHE contrast boost + sharpening kernel makes text crisper
  4. Trim items (opt)    — removes the line-items block, gluing header + totals together

Usage:
  python enhance_receipts.py --input ./receipts --output ./enhanced
  python enhance_receipts.py --input ./receipts --output ./enhanced --trim-items
  python enhance_receipts.py --input ./receipts --output ./enhanced --preview

Requirements:
  pip install opencv-python numpy
"""

import argparse
import sys
from pathlib import Path

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif"}


def check_dependencies():
    missing = []
    try:
        import cv2  # noqa: F401
    except ImportError:
        missing.append("opencv-python")
    try:
        import numpy  # noqa: F401
    except ImportError:
        missing.append("numpy")
    if missing:
        print(f"Missing packages: {', '.join(missing)}")
        print(f"Install with:  pip install {' '.join(missing)}")
        sys.exit(1)


def remove_shadows(img):
    """Flatten shadows by dividing each colour channel by a blurred background estimate."""
    import cv2
    import numpy as np

    rgb_planes = cv2.split(img)
    result_planes = []
    for plane in rgb_planes:
        dilated = cv2.dilate(plane, np.ones((7, 7), np.uint8))
        bg = cv2.medianBlur(dilated, 21)
        diff = 255 - cv2.absdiff(plane, bg)
        norm = cv2.normalize(diff, None, alpha=0, beta=255,
                             norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8UC1)
        result_planes.append(norm)
    return cv2.merge(result_planes)


def reduce_creases(img):
    """Smooth crease lines while preserving sharp text edges via bilateral filter."""
    import cv2
    return cv2.bilateralFilter(img, d=9, sigmaColor=75, sigmaSpace=75)


def trim_items_section(img):
    """
    Remove the line-items block from a receipt and return header + totals glued together.

    How it works:
      1. Binarize (Otsu) → compute a row-wise dark-pixel count (projection profile).
      2. Smooth the profile and threshold it to label each row as "text" or "blank".
      3. Group consecutive text rows into blocks.
      4. The items block = the largest contiguous text block whose centre falls in
         the middle 15–85 % of the image height (header and footer are excluded).
      5. Slice out that block (plus a small margin) and vstack the two halves.

    Returns (result_img, trimmed: bool).
    Falls back to the original if fewer than 3 text blocks are found or if the
    detected block covers almost the entire image.
    """
    import cv2
    import numpy as np

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Row projection: total dark pixels per row
    row_profile = binary.sum(axis=1).astype(float)

    # Smooth with a window ~1 % of image height to bridge intra-word gaps
    win = max(5, img.shape[0] // 80)
    kernel = np.ones(win) / win
    smoothed = np.convolve(row_profile, kernel, mode='same')

    blank_threshold = smoothed.max() * 0.04
    is_text = smoothed >= blank_threshold

    # Collect contiguous text blocks as (start_row, end_row)
    blocks = []
    in_block = False
    start = 0
    for y, text in enumerate(is_text):
        if text and not in_block:
            in_block = True
            start = y
        elif not text and in_block:
            in_block = False
            blocks.append((start, y))
    if in_block:
        blocks.append((start, len(is_text)))

    if len(blocks) < 3:
        return img, False

    h = img.shape[0]
    # Only consider blocks whose centre lies in the middle band of the receipt
    mid_lo, mid_hi = h * 0.15, h * 0.85
    candidates = [(s, e) for s, e in blocks if mid_lo < (s + e) / 2 < mid_hi]
    if not candidates:
        return img, False

    items_start, items_end = max(candidates, key=lambda b: b[1] - b[0])

    # Sanity check: don't trim if the block is almost the whole image
    if (items_end - items_start) > h * 0.75:
        return img, False

    margin = max(4, h // 150)
    cut_top    = max(0, items_start - margin)
    cut_bottom = min(h, items_end   + margin)

    top_part    = img[:cut_top]
    bottom_part = img[cut_bottom:]

    if top_part.shape[0] < 10 or bottom_part.shape[0] < 10:
        return img, False

    # Thin grey separator so the join is visually obvious
    sep = np.full((3, img.shape[1], 3), 160, dtype=np.uint8)
    result = np.vstack([top_part, sep, bottom_part])
    return result, True


def enhance_text(img):
    """CLAHE contrast boost on the lightness channel, then a sharpening kernel."""
    import cv2
    import numpy as np

    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    l_ch = clahe.apply(l_ch)
    enhanced = cv2.cvtColor(cv2.merge([l_ch, a_ch, b_ch]), cv2.COLOR_LAB2BGR)

    sharpen_kernel = np.array([
        [ 0, -1,  0],
        [-1,  5, -1],
        [ 0, -1,  0],
    ], dtype=np.float32)
    return cv2.filter2D(enhanced, -1, sharpen_kernel)


def process_image(input_path: Path, output_path: Path,
                  do_trim: bool = False, preview: bool = False):
    import cv2

    img = cv2.imread(str(input_path))
    if img is None:
        print(f"  [!] Could not read: {input_path.name}")
        return False

    img = remove_shadows(img)
    img = reduce_creases(img)
    img = enhance_text(img)

    trimmed = False
    if do_trim:
        img, trimmed = trim_items_section(img)

    ext = output_path.suffix.lower()
    params = []
    if ext in (".jpg", ".jpeg"):
        params = [cv2.IMWRITE_JPEG_QUALITY, 95]
    elif ext == ".png":
        params = [cv2.IMWRITE_PNG_COMPRESSION, 1]

    cv2.imwrite(str(output_path), img, params)

    if preview:
        cv2.imshow(f"Enhanced — {input_path.name}", img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return trimmed


def main():
    parser = argparse.ArgumentParser(
        description="Enhance receipt images: remove shadows, reduce creases, sharpen text."
    )
    parser.add_argument("--input",    required=True, help="Folder containing raw receipt images")
    parser.add_argument("--output",   required=True, help="Folder to save enhanced images")
    parser.add_argument("--trim-items", action="store_true",
                        help="Detect and remove the line-items block, keeping header + totals")
    parser.add_argument("--preview",    action="store_true",
                        help="Show each enhanced image in a window before saving")
    args = parser.parse_args()

    check_dependencies()

    input_folder  = Path(args.input)
    output_folder = Path(args.output)

    if not input_folder.exists():
        print(f"Input folder not found: {input_folder}")
        sys.exit(1)

    output_folder.mkdir(parents=True, exist_ok=True)

    images = [f for f in sorted(input_folder.iterdir())
              if f.suffix.lower() in SUPPORTED_EXTENSIONS]

    if not images:
        print(f"No supported images found in {input_folder}")
        sys.exit(0)

    print(f"Found {len(images)} image(s) in '{input_folder}'")
    print(f"Saving enhanced images to '{output_folder}'\n")

    ok = trimmed_count = failed = 0
    for i, img_path in enumerate(images, 1):
        out_path = output_folder / img_path.name
        print(f"[{i}/{len(images)}] {img_path.name} ... ", end="", flush=True)
        result = process_image(img_path, out_path,
                               do_trim=args.trim_items,
                               preview=args.preview)
        if result is False:
            print("FAILED")
            failed += 1
        else:
            trimmed = result
            note = "items trimmed + enhanced" if trimmed else "enhanced"
            if trimmed:
                trimmed_count += 1
            print(note)
            ok += 1

    trim_note = f", {trimmed_count} items-trimmed" if args.trim_items else ""
    print(f"\nComplete: {ok} processed{trim_note}, {failed} failed.")
    print(f"Results saved to: {output_folder.resolve()}")


if __name__ == "__main__":
    main()
