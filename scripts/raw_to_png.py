#!/usr/bin/env python3
"""
raw_to_png.py — Framebuffer dump to PNG converter for Miyoo Mini / Mini Plus.

Extracts the active page from an uncached /dev/fb0 dump, handles the 180° LCD
panel rotation, and outputs a clean screenshot PNG.

Usage:
    # 1. On device:
    #    PAN=$(cat /sys/class/graphics/fb0/pan | cut -d',' -f2)
    #    cat /dev/fb0 > /tmp/fb.raw
    # 2. On PC:
    #    python3 raw_to_png.py /tmp/fb.raw screenshot.png --yoffset $PAN
"""

import sys
import argparse
from pathlib import Path

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

def convert_fb_to_png(raw_path, out_path, width=640, height=480, y_offset=0, bpp=32, rotate_180=True):
    if not HAS_PIL:
        print("Error: Pillow is required. Install via: pip install Pillow")
        sys.exit(1)

    raw_file = Path(raw_path)
    if not raw_file.exists():
        print(f"Error: {raw_path} not found.")
        sys.exit(1)

    bytes_per_pixel = bpp // 8
    frame_size = width * height * bytes_per_pixel
    start_byte = y_offset * width * bytes_per_pixel

    with open(raw_file, "rb") as f:
        f.seek(start_byte)
        data = f.read(frame_size)

    if len(data) < frame_size:
        print(f"Warning: Expected {frame_size} bytes, but only read {len(data)} bytes.")

    if bpp == 32:
        # ARGB / BGRA format commonly emitted by SigmaStar fb0
        img = Image.frombytes("RGBA", (width, height), data, "raw", "BGRA")
    elif bpp == 16:
        img = Image.frombytes("RGB", (width, height), data, "raw", "BGR;16")
    else:
        print(f"Unsupported bpp: {bpp}")
        sys.exit(1)

    if rotate_180:
        # Counteract the physically inverted LCD panel
        img = img.rotate(180)

    img.save(out_path)
    print(f"[+] Saved screenshot: {out_path} ({width}x{height}, offset y={y_offset})")

def main():
    parser = argparse.ArgumentParser(description="Convert Miyoo Mini /dev/fb0 raw dump to PNG.")
    parser.add_argument("input", help="Path to raw framebuffer dump")
    parser.add_argument("output", help="Path to output PNG")
    parser.add_argument("--width", type=int, default=640, help="Screen width (default: 640)")
    parser.add_argument("--height", type=int, default=480, help="Screen height (default: 480)")
    parser.add_argument("--yoffset", type=int, default=0, help="Active Y pan offset from /sys/class/graphics/fb0/pan")
    parser.add_argument("--bpp", type=int, default=32, help="Bits per pixel (default: 32)")
    parser.add_argument("--no-rotate", action="store_true", help="Do not apply 180° rotation")
    args = parser.parse_args()

    convert_fb_to_png(args.input, args.output, args.width, args.height, args.yoffset, args.bpp, not args.no_rotate)

if __name__ == "__main__":
    main()
