"""
extract_pages.py — Pull specific pages out of a PDF into a new file.

Usage:
    python extract_pages.py input.pdf output.pdf 1 3 5-8 12

    Pages can be individual numbers or ranges (e.g. 5-8).
    Page numbers are 1-based (like the page numbers you see in a PDF viewer).

Requirements:
    pip install pypdf
"""

import sys
from pypdf import PdfReader, PdfWriter


def parse_page_args(args):
    """Parse page arguments like ['1', '3', '5-8', '12'] into a sorted list of 0-based indices."""
    pages = set()
    for arg in args:
        if '-' in arg:
            start, end = arg.split('-', 1)
            pages.update(range(int(start) - 1, int(end)))  # convert to 0-based
        else:
            pages.add(int(arg) - 1)  # convert to 0-based
    return sorted(pages)


def extract_pages(input_path, output_path, page_indices):
    reader = PdfReader(input_path)
    total = len(reader.pages)
    writer = PdfWriter()

    for idx in page_indices:
        if idx < 0 or idx >= total:
            print(f"  ⚠️  Page {idx + 1} is out of range (document has {total} pages) — skipping.")
            continue
        writer.add_page(reader.pages[idx])
        print(f"  ✓ Added page {idx + 1}")

    with open(output_path, "wb") as f:
        writer.write(f)

    print(f"\nDone! Saved {len(writer.pages)} page(s) to: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    input_pdf  = sys.argv[1]
    output_pdf = sys.argv[2]
    page_args  = sys.argv[3:]

    page_indices = parse_page_args(page_args)
    print(f"Extracting pages: {[i + 1 for i in page_indices]}")
    extract_pages(input_pdf, output_pdf, page_indices)
