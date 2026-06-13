#!/usr/bin/env python3
"""Deterministic cover-crop/resize for entry images.

Usage: crop-image.py <in> <out> --width W --height H [--quality N]

Scales the input to fill WxH preserving aspect ratio, center-crops the
overflow, and writes <out> in the format inferred from its extension.
"""
import argparse
import os
import sys

from PIL import Image

FORMATS = {".webp": "WEBP", ".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--width", type=int, required=True)
    p.add_argument("--height", type=int, required=True)
    p.add_argument("--quality", type=int, default=85)
    p.add_argument("--delete-input", action="store_true",
                   help="remove the input file after a successful save")
    args = p.parse_args()

    ext = "." + args.output.rsplit(".", 1)[-1].lower() if "." in args.output else ""
    fmt = FORMATS.get(ext)
    if fmt is None:
        sys.exit(f"crop-image: unsupported output extension: {args.output}")

    try:
        im = Image.open(args.input)
    except (FileNotFoundError, OSError) as e:
        sys.exit(f"crop-image: cannot open {args.input}: {e}")

    im = im.convert("RGB")
    w, h = args.width, args.height
    scale = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    left = (im.width - w) // 2
    top = (im.height - h) // 2
    im = im.crop((left, top, left + w, top + h))

    save_kwargs = {} if fmt == "PNG" else {"quality": args.quality}
    im.save(args.output, fmt, **save_kwargs)

    if args.delete_input:
        os.remove(args.input)


if __name__ == "__main__":
    main()
