#!/usr/bin/env python3
"""
balloonify.py — April Fools weapon sprite converter
====================================================
Takes weapon DMI spritesheets and applies a rubber-balloon aesthetic:
  - Boosts saturation (vivid balloon colors)
  - Slight brightness lift
  - Softens contrast (smooth rubber surface)
  - Adds a small elliptical shine spot per sprite cell (upper-left highlight)

Output: new DMI files with '_balloon' suffix, preserving all metadata
(state names, directions, frames) so they drop straight into the codebase.

Usage:
  python tools/balloonify.py
  python tools/balloonify.py --preview   # saves PNGs for quick visual check
  python tools/balloonify.py --shine 0.4 # tune shine intensity (0.0-1.0)

Requirements:
  pip install Pillow
"""

import argparse
import io
import os
import re
import struct
import zlib

try:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
except ImportError:
    raise SystemExit("Pillow is required: pip install Pillow")

# ---------------------------------------------------------------------------
# DMI metadata helpers
# BYOND DMI files are valid PNGs. Sprite metadata lives in a zTXt or tEXt
# chunk with key 'Description'. We need to preserve it exactly when saving.
# ---------------------------------------------------------------------------

def _read_chunks(data: bytes):
    """Yield (chunk_type, chunk_data, start_offset) for each PNG chunk."""
    pos = 8  # skip PNG signature
    while pos < len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        ctype = data[pos + 4 : pos + 8]
        cdata = data[pos + 8 : pos + 8 + length]
        yield ctype, cdata, pos
        pos += 12 + length


def read_dmi_metadata(path: str) -> str | None:
    """Return the raw DMI Description string, or None if not found."""
    with open(path, "rb") as f:
        data = f.read()
    for ctype, cdata, _ in _read_chunks(data):
        if ctype == b"zTXt":
            parts = cdata.split(b"\x00", 2)
            if parts[0] == b"Description":
                return zlib.decompress(parts[2]).decode("latin-1")
        elif ctype == b"tEXt":
            parts = cdata.split(b"\x00", 1)
            if parts[0] == b"Description":
                return parts[1].decode("latin-1")
    return None


def parse_dmi_metadata(meta: str):
    """
    Returns (icon_width, icon_height, states) where states is a list of dicts:
      { name, dirs, frames, delay, ... }
    """
    iw = int(re.search(r"icon_width\s*=\s*(\d+)", meta).group(1))
    ih = int(re.search(r"icon_height\s*=\s*(\d+)", meta).group(1))

    states = []
    # Each state block sits between 'state = "..."' and the next 'state' or end
    for m in re.finditer(
        r'state\s*=\s*"([^"]*)"(.*?)(?=\nstate\s*=|\Z)', meta, re.DOTALL
    ):
        name = m.group(1)
        block = m.group(2)
        dirs_m = re.search(r"dirs\s*=\s*(\d+)", block)
        frames_m = re.search(r"frames\s*=\s*(\d+)", block)
        dirs = int(dirs_m.group(1)) if dirs_m else 1
        frames = int(frames_m.group(1)) if frames_m else 1
        states.append({"name": name, "dirs": dirs, "frames": frames})
    return iw, ih, states


def write_dmi(img: Image.Image, path: str, original_meta: str | None):
    """Save PIL image as DMI, re-injecting the original metadata chunk."""
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
    png_data = buf.getvalue()

    if original_meta is None:
        with open(path, "wb") as f:
            f.write(png_data)
        return

    # Build a zTXt chunk (compressed) — matches what BYOND writes
    raw = b"Description\x00\x00" + zlib.compress(
        original_meta.encode("latin-1"), level=9
    )
    crc = struct.pack(">I", zlib.crc32(b"zTXt" + raw) & 0xFFFFFFFF)
    meta_chunk = struct.pack(">I", len(raw)) + b"zTXt" + raw + crc

    # Insert before the first IDAT chunk, removing any existing Description chunk
    new_chunks = bytearray(png_data[:8])  # PNG signature
    for ctype, cdata, _ in _read_chunks(png_data):
        if ctype in (b"zTXt", b"tEXt"):
            key = cdata.split(b"\x00", 1)[0]
            if key == b"Description":
                continue  # drop old metadata
        chunk_len = len(cdata)
        crc_val = struct.pack(
            ">I", zlib.crc32(ctype + cdata) & 0xFFFFFFFF
        )
        new_chunks += struct.pack(">I", chunk_len) + ctype + cdata + crc_val
        if ctype == b"IHDR":
            new_chunks += meta_chunk  # inject right after IHDR

    with open(path, "wb") as f:
        f.write(bytes(new_chunks))


# ---------------------------------------------------------------------------
# Balloon image processing
# ---------------------------------------------------------------------------

def add_shine(img: Image.Image, cell_w: int, cell_h: int, intensity: float) -> Image.Image:
    """
    For each sprite cell in the sheet, add a small elliptical highlight in the
    upper-left quadrant — the defining feature of a rubber balloon surface.
    Works on RGBA images.
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    result = img.copy()
    pixels = result.load()
    sheet_w, sheet_h = result.size

    cols = sheet_w // cell_w
    rows = sheet_h // cell_h

    for row in range(rows):
        for col in range(cols):
            ox = col * cell_w
            oy = row * cell_h

            # Shine ellipse: top-left quarter of the cell, small
            sx = int(cell_w * 0.15)
            sy = int(cell_h * 0.12)
            sw = int(cell_w * 0.28)
            sh = int(cell_h * 0.20)

            # Create shine mask for this cell
            shine_layer = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
            draw = ImageDraw.Draw(shine_layer)
            draw.ellipse([0, 0, sw - 1, sh - 1], fill=(255, 255, 255, int(180 * intensity)))
            # Feather: apply a slight blur to the shine
            shine_layer = shine_layer.filter(ImageFilter.GaussianBlur(radius=1.5))

            for dy in range(sh):
                for dx in range(sw):
                    px = ox + sx + dx
                    py = oy + sy + dy
                    if px >= sheet_w or py >= sheet_h:
                        continue
                    sr, sg, sb, sa = shine_layer.getpixel((dx, dy))
                    or_, og, ob, oa = pixels[px, py]
                    if oa < 16:  # don't paint onto transparent pixels
                        continue
                    blend = sa / 255.0
                    nr = min(255, int(or_ + (255 - or_) * blend))
                    ng = min(255, int(og + (255 - og) * blend))
                    nb = min(255, int(ob + (255 - ob) * blend))
                    pixels[px, py] = (nr, ng, nb, oa)
    return result


def balloonify(img: Image.Image, cell_w: int, cell_h: int, shine: float) -> Image.Image:
    """Apply the full balloon treatment to a spritesheet."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    r, g, b, a = img.split()
    rgb = Image.merge("RGB", (r, g, b))

    # 1. Vivid balloon colors — high saturation
    rgb = ImageEnhance.Color(rgb).enhance(2.4)
    # 2. Slightly brighter (balloons are always cheerful)
    rgb = ImageEnhance.Brightness(rgb).enhance(1.12)
    # 3. Slightly flatter contrast (smooth rubber, not metallic)
    rgb = ImageEnhance.Contrast(rgb).enhance(0.82)
    # 4. Very gentle smoothing — softens sharp pixel edges a tiny bit
    rgb = rgb.filter(ImageFilter.SMOOTH_MORE)

    result = Image.merge("RGBA", (*rgb.split(), a))
    result = add_shine(result, cell_w, cell_h, shine)
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# DMI files to process, relative to repo root
WEAPON_DMIS = [
    "icons/obj/weapons.dmi",
    "icons/obj/guns/gun.dmi",
    "icons/obj/guns/charge.dmi",
    "icons/obj/guns/railgun.dmi",
    "icons/obj/guns/sr.dmi",
]


def main():
    parser = argparse.ArgumentParser(description="Balloonify weapon sprites.")
    parser.add_argument(
        "--shine",
        type=float,
        default=0.35,
        help="Shine highlight intensity (0.0 = none, 1.0 = full). Default: 0.35",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Also save flat .png previews alongside the output DMIs.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: same dir as input, with _balloon suffix on filename).",
    )
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)

    for dmi_rel in WEAPON_DMIS:
        input_path = os.path.join(repo_root, dmi_rel)
        if not os.path.exists(input_path):
            print(f"  skip (not found): {dmi_rel}")
            continue

        meta = read_dmi_metadata(input_path)
        if meta is None:
            print(f"  skip (no DMI metadata): {dmi_rel}")
            continue

        try:
            cell_w, cell_h, states = parse_dmi_metadata(meta)
        except Exception as e:
            print(f"  skip (metadata parse error: {e}): {dmi_rel}")
            continue

        img = Image.open(input_path).convert("RGBA")
        print(f"Processing {dmi_rel}  [{img.size[0]}x{img.size[1]}, cell {cell_w}x{cell_h}, {len(states)} states]")

        ballooned = balloonify(img, cell_w, cell_h, args.shine)

        base, ext = os.path.splitext(dmi_rel)
        out_rel = base + "_balloon" + ext
        if args.output_dir:
            out_path = os.path.join(args.output_dir, os.path.basename(out_rel))
        else:
            out_path = os.path.join(repo_root, out_rel)

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        write_dmi(ballooned, out_path, meta)
        print(f"  -> {out_rel}")

        if args.preview:
            preview_path = out_path.replace(".dmi", "_preview.png")
            ballooned.save(preview_path)
            print(f"  -> {os.path.basename(preview_path)} (preview)")


if __name__ == "__main__":
    main()
