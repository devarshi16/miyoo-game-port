#!/usr/bin/env python3
"""Pack already extracted images/data into MPAK v1. A game-specific runtime reader is required.

Indexed images preserve exact RGBA colors, with RGBA32 fallback above 256 colors.
This helper does not unpack proprietary game containers or transcode audio.
"""
import argparse
import os
from pathlib import Path
import struct
import tempfile
from PIL import Image

MAGIC = b'MPAK'
VERSION = 1
TYPE_SPRITE_RGBA32 = 1
TYPE_SPRITE_INDEXED8 = 2
TYPE_GENERIC_DATA = 20


def quantize_indexed8(img):
    rgba = img.convert('RGBA')
    raw = rgba.tobytes()
    lookup, palette, indices = {}, bytearray(1024), bytearray()
    for pos in range(0, len(raw), 4):
        color = raw[pos:pos + 4]
        index = lookup.get(color)
        if index is None:
            if len(lookup) == 256:
                return None, None
            index = len(lookup)
            lookup[color] = index
            palette[index * 4:index * 4 + 4] = color
        indices.append(index)
    return indices, palette


def pack_assets(input_dir, output_file, fmt_mode='indexed8'):
    source = Path(input_dir)
    destination = Path(output_file)
    if not source.is_dir():
        raise ValueError('Extracted asset directory does not exist')
    if fmt_mode not in ('indexed8', 'rgba32'):
        raise ValueError('Unsupported image format')
    destination.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    opaque = [f for f in source.rglob('*') if f.is_file() and
              (f.suffix.lower() in ('.assets', '.ress', '.resource', '.pck', '.win', '.unx', '.xnb', '.unity3d') or
               f.name in ('globalgamemanagers', 'GameAssembly.dll', 'UnityPlayer.dll'))]
    if opaque:
        raise ValueError('Input still contains raw game containers; extract them before packing: ' + ', '.join(f.name for f in opaque[:5]))
    # Spool on disk so all assets need not coexist as Python byte arrays.
    with tempfile.TemporaryFile() as spool:
        for f in sorted(source.rglob('*')):
            if not f.is_file() or f.resolve() == destination.resolve():
                continue
            name = f.relative_to(source).as_posix()
            if len(name.encode('utf-8')) > 127:
                raise ValueError('MPAK v1 name exceeds 127 UTF-8 bytes: ' + name)
            offset = spool.tell()
            ext = f.suffix.lower()
            w = h = 0
            if ext in ('.png', '.jpg', '.jpeg', '.bmp'):
                with Image.open(f) as image:
                    w, h = image.size
                    if not (0 < w < 65536 and 0 < h < 65536):
                        raise ValueError('MPAK v1 dimensions out of range: ' + name)
                    pixels, palette = quantize_indexed8(image) if fmt_mode == 'indexed8' else (None, None)
                    if pixels is None:
                        kind = TYPE_SPRITE_RGBA32
                        spool.write(image.convert('RGBA').tobytes())
                    else:
                        kind = TYPE_SPRITE_INDEXED8
                        spool.write(palette); spool.write(pixels)
            elif ext in ('.wav', '.ogg', '.mp3', '.json', '.xml', '.txt', '.bin', '.dat'):
                kind = TYPE_GENERIC_DATA  # WAV retains its container header; it is not raw PCM.
                with f.open('rb') as inp:
                    for block in iter(lambda: inp.read(1024 * 1024), b''):
                        spool.write(block)
            else:
                continue
            length = spool.tell() - offset
            if not length:
                raise ValueError('Empty asset: ' + name)
            if spool.tell() >= 2**32:
                raise ValueError('MPAK v1 payload exceeds 32-bit offsets')
            entries.append((name, kind, w, h, offset, length))
        if not entries:
            raise ValueError('No extracted assets found. Proprietary containers must be extracted first.')
        table = b''.join(struct.pack('<128sHHHHII', n.encode().ljust(128, b'\0'), t, w, h, 0, off, length)
                         for n, t, w, h, off, length in entries)
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.mpak-', delete=False) as out:
            temporary = Path(out.name)
            try:
                out.write(struct.pack('<4sIII', MAGIC, VERSION, len(entries), 16 + len(table)))
                out.write(table)
                spool.seek(0)
                for block in iter(lambda: spool.read(1024 * 1024), b''):
                    out.write(block)
                out.close()
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
    print('Packed %d extracted assets: %s' % (len(entries), destination))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', '-i', required=True)
    ap.add_argument('--output', '-o', default='game.pack')
    ap.add_argument('--format', '-f', choices=['indexed8', 'rgba32'], default='indexed8')
    args = ap.parse_args()
    try:
        pack_assets(args.input, args.output, args.format)
    except (OSError, ValueError) as error:
        ap.exit(1, 'Packing failed: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
