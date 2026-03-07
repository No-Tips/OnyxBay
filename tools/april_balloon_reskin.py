#!/usr/bin/env python3
"""
april_balloon_reskin.py
Replaces security weapon sprites in OnyxBay DMI files with balloon equivalents.

Source: icons/obj/balloons.dmi (states: stunbaton, revolver, shotgun, fireaxe, claymore, extinguisher)

Usage: python tools/april_balloon_reskin.py
"""

import struct, zlib, io, sys, subprocess
from pathlib import Path

# ── ensure Pillow ────────────────────────────────────────────────────────────
try:
    from PIL import Image
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow"])
    from PIL import Image

REPO = Path(__file__).resolve().parent.parent
BALLOON_DMI = REPO / "icons/obj/balloons.dmi"

# ── DMI low-level helpers ─────────────────────────────────────────────────────

def iter_chunks(data: bytes):
    pos = 8  # skip PNG signature
    while pos + 12 <= len(data):
        length = struct.unpack(">I", data[pos:pos+4])[0]
        ctype  = data[pos+4:pos+8].decode("ascii", errors="replace")
        cdata  = data[pos+8:pos+8+length]
        yield ctype, cdata, pos
        pos += 12 + length

def make_chunk(ctype: str, data: bytes) -> bytes:
    bt  = ctype.encode("ascii")
    crc = struct.pack(">I", zlib.crc32(bt + data) & 0xFFFFFFFF)
    return struct.pack(">I", len(data)) + bt + data + crc

def extract_meta(raw: bytes) -> str | None:
    for ctype, cdata, _ in iter_chunks(raw):
        if ctype not in ("tEXt", "zTXt", "iTXt"):
            continue
        try:
            ni  = cdata.index(b"\x00")
            kw  = cdata[:ni].decode("ascii", errors="replace")
            if kw != "Description":
                continue
            if ctype == "zTXt":
                return zlib.decompress(cdata[ni+2:]).decode("utf-8", errors="replace")
            return cdata[ni+1:].decode("utf-8", errors="replace")
        except Exception:
            pass
    return None

def parse_meta(text: str):
    """Returns (sw, sh, states_list). Each state is a dict."""
    sw = sh = 32
    states, cur = [], None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("width = "):
            sw = int(line.split(" = ", 1)[1])
        elif line.startswith("height = "):
            sh = int(line.split(" = ", 1)[1])
        elif line.startswith("state = "):
            if cur is not None:
                states.append(cur)
            cur = {"name": line.split('"')[1], "dirs": 1, "frames": 1}
        elif cur is not None:
            if line.startswith("dirs = "):
                cur["dirs"] = int(line.split(" = ", 1)[1])
            elif line.startswith("frames = "):
                cur["frames"] = int(line.split(" = ", 1)[1])
    if cur is not None:
        states.append(cur)
    return sw, sh, states

def build_offset_map(states):
    """state_name → flat sprite index (first occurrence wins for duplicate names)."""
    index, offset = {}, 0
    for s in states:
        count = s["dirs"] * s["frames"]
        if s["name"] not in index:
            index[s["name"]] = (offset, s)
        offset += count
    return index

# ── Sprite read / write ───────────────────────────────────────────────────────

def get_sprite(img: Image.Image, sw: int, sh: int, flat_idx: int) -> Image.Image:
    cols = img.width // sw
    col  = flat_idx % cols
    row  = flat_idx // cols
    return img.crop((col * sw, row * sh, (col+1) * sw, (row+1) * sh))

def set_sprite(img: Image.Image, sw: int, sh: int, flat_idx: int, sprite: Image.Image):
    cols = img.width // sw
    col  = flat_idx % cols
    row  = flat_idx // cols
    if sprite.size != (sw, sh):
        sprite = sprite.resize((sw, sh), Image.LANCZOS)
    img.paste(sprite, (col * sw, row * sh))

# ── Load / save DMI ───────────────────────────────────────────────────────────

def load_dmi(path: Path):
    raw  = path.read_bytes()
    meta = extract_meta(raw)
    if meta is None:
        raise ValueError(f"No DMI metadata in {path}")
    sw, sh, states = parse_meta(meta)
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    return img, sw, sh, states, raw

def save_dmi(img: Image.Image, original_raw: bytes, path: Path):
    """Re-encode image pixels into the original DMI, preserving all metadata chunks."""
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
    new_raw = buf.getvalue()

    # collect new IDAT blocks
    new_idats = [(ct, cd) for ct, cd, _ in iter_chunks(new_raw) if ct == "IDAT"]

    PNG_SIG = b"\x89PNG\r\n\x1a\n"
    out = bytearray(PNG_SIG)
    idat_done = False
    for ctype, cdata, _ in iter_chunks(original_raw):
        if ctype == "IDAT":
            if not idat_done:
                for nc, nd in new_idats:
                    out += make_chunk(nc, nd)
                idat_done = True
            # drop old IDAT
        else:
            out += make_chunk(ctype, cdata)

    path.write_bytes(bytes(out))
    print(f"  saved: {path.relative_to(REPO)}")

# ── Core replacement ──────────────────────────────────────────────────────────

def apply_replacements(balloon_sprite: Image.Image, dmi_path: Path, target_states: list[str]):
    full_path = REPO / dmi_path
    if not full_path.exists():
        print(f"  SKIP (not found): {dmi_path}")
        return

    img, sw, sh, states, raw = load_dmi(full_path)
    offset_map = build_offset_map(states)
    changed = 0

    for name in target_states:
        if name not in offset_map:
            continue
        flat_start, state = offset_map[name]
        count = state["dirs"] * state["frames"]
        for i in range(count):
            set_sprite(img, sw, sh, flat_start + i, balloon_sprite)
        changed += count

    if changed:
        save_dmi(img, raw, full_path)
        print(f"    replaced {changed} sub-sprites across {len([n for n in target_states if n in offset_map])} states")
    else:
        print(f"  no matching states in {dmi_path}")

# ── Mapping ───────────────────────────────────────────────────────────────────

REPLACEMENTS = {
    # balloon state → list of (relative_dmi_path, [states_to_replace])
    "revolver": [
        ("icons/obj/guns/gun.dmi", [
            "taserold",       "taserold0",       "taserold25",       "taserold50",       "taserold75",       "taserold100",
            "taser",          "taser0",           "taser25",          "taser50",          "taser75",          "taser100",
            "taser_smg",      "taser_smg0",       "taser_smg25",      "taser_smg50",      "taser_smg75",      "taser_smg100",
            "taser_rifle",    "taser_rifle0",     "taser_rifle25",    "taser_rifle50",    "taser_rifle75",    "taser_rifle100",
            "stunrevolver",   "stunrevolver100",  "stunrevolver75",   "stunrevolver50",   "stunrevolver25",   "stunrevolver0",
            "smallgunstun",   "smallgunstun0",    "smallgunstun25",   "smallgunstun50",   "smallgunstun75",   "smallgunstun100",
            "smallgunshock",  "smallgunshock0",   "smallgunshock25",  "smallgunshock50",  "smallgunshock75",  "smallgunshock100",
            "smallgunkill",   "smallgunkill0",    "smallgunkill25",   "smallgunkill50",   "smallgunkill75",   "smallgunkill100",
            "tasertacticalstun",  "tasertacticalstun0",  "tasertacticalstun25",  "tasertacticalstun50",  "tasertacticalstun75",  "tasertacticalstun100",
            "tasertacticalshock", "tasertacticalshock0", "tasertacticalshock25", "tasertacticalshock50", "tasertacticalshock75", "tasertacticalshock100",
            "tasertacticalkill",  "tasertacticalkill0",  "tasertacticalkill25",  "tasertacticalkill50",  "tasertacticalkill75",  "tasertacticalkill100",
            "tasercarbine",   "tasercarbine0",    "tasercarbine25",   "tasercarbine50",   "tasercarbine75",   "tasercarbine100",
            "stunrifle",
            "egunstun",       "egunstun0",        "egunstun25",       "egunstun50",       "egunstun75",       "egunstun100",
            "egunshock",
            "energystun",     "energystun0",      "energystun25",     "energystun50",     "energystun75",     "energystun100",
            "energyshock",    "energyshock0",     "energyshock25",    "energyshock50",    "energyshock75",    "energyshock100",
            "btaser",         "btaser0",          "btaser25",         "btaser50",         "btaser75",         "btaser100",
        ]),
        ("icons/mob/onmob/items/lefthand_guns.dmi", [
            "taser",          "taser0",           "taser25",          "taser50",          "taser75",          "taser100",
            "taser_smg",      "taser_smg0",       "taser_smg25",      "taser_smg50",      "taser_smg75",      "taser_smg100",
            "taser_rifle",    "taser_rifle0",     "taser_rifle25",    "taser_rifle50",    "taser_rifle75",    "taser_rifle100",
            "taser_rifle0-wielded", "taser_rifle25-wielded", "taser_rifle50-wielded", "taser_rifle75-wielded", "taser_rifle100-wielded", "taser_rifle-wielded",
            "stunrevolver",
            "tasertacticalstun",  "tasertacticalstun0",  "tasertacticalstun25",  "tasertacticalstun50",  "tasertacticalstun75",  "tasertacticalstun100",
            "tasertacticalshock", "tasertacticalshock0", "tasertacticalshock25", "tasertacticalshock50", "tasertacticalshock75", "tasertacticalshock100",
            "tasertacticalkill",  "tasertacticalkill0",  "tasertacticalkill25",  "tasertacticalkill50",  "tasertacticalkill75",  "tasertacticalkill100",
            "tasercarbine",   "tasercarbine0",    "tasercarbine25",   "tasercarbine50",   "tasercarbine75",   "tasercarbine100",  "tasercarbine-wielded",
            "stunrifle",      "stunrifle-wielded",
            "smallgunstun",   "smallgunstun0",    "smallgunstun25",   "smallgunstun50",   "smallgunstun75",   "smallgunstun100",
            "smallgunshock",  "smallgunshock0",   "smallgunshock25",  "smallgunshock50",  "smallgunshock75",  "smallgunshock100",
            "smallgunkill",   "smallgunkill0",    "smallgunkill25",   "smallgunkill50",   "smallgunkill75",   "smallgunkill100",
            "egunstun",       "egunstun0",        "egunstun25",       "egunstun50",       "egunstun75",       "egunstun100",
            "energystun",     "energystun0",      "energystun25",     "energystun50",     "energystun75",     "energystun100",
            "energyshock",    "energyshock0",     "energyshock25",    "energyshock50",    "energyshock75",    "energyshock100",
        ]),
        ("icons/mob/onmob/items/righthand_guns.dmi", [
            "taser",          "taser0",           "taser25",          "taser50",          "taser75",          "taser100",
            "taser_smg",      "taser_smg0",       "taser_smg25",      "taser_smg50",      "taser_smg75",      "taser_smg100",
            "taser_rifle",    "taser_rifle0",     "taser_rifle25",    "taser_rifle50",    "taser_rifle75",    "taser_rifle100",
            "taser_rifle0-wielded", "taser_rifle25-wielded", "taser_rifle50-wielded", "taser_rifle75-wielded", "taser_rifle100-wielded", "taser_rifle-wielded",
            "stunrevolver",
            "tasertacticalstun",  "tasertacticalstun0",  "tasertacticalstun25",  "tasertacticalstun50",  "tasertacticalstun75",  "tasertacticalstun100",
            "tasertacticalshock", "tasertacticalshock0", "tasertacticalshock25", "tasertacticalshock50", "tasertacticalshock75", "tasertacticalshock100",
            "tasertacticalkill",  "tasertacticalkill0",  "tasertacticalkill25",  "tasertacticalkill50",  "tasertacticalkill75",  "tasertacticalkill100",
            "tasercarbine",   "tasercarbine0",    "tasercarbine25",   "tasercarbine50",   "tasercarbine75",   "tasercarbine100",  "tasercarbine-wielded",
            "stunrifle",      "stunrifle-wielded",
            "smallgunstun",   "smallgunstun0",    "smallgunstun25",   "smallgunstun50",   "smallgunstun75",   "smallgunstun100",
            "smallgunshock",  "smallgunshock0",   "smallgunshock25",  "smallgunshock50",  "smallgunshock75",  "smallgunshock100",
            "smallgunkill",   "smallgunkill0",    "smallgunkill25",   "smallgunkill50",   "smallgunkill75",   "smallgunkill100",
            "egunstun",       "egunstun0",        "egunstun25",       "egunstun50",       "egunstun75",       "egunstun100",
            "energystun",     "energystun0",      "energystun25",     "energystun50",     "energystun75",     "energystun100",
            "energyshock",    "energyshock0",     "energyshock25",    "energyshock50",    "energyshock75",    "energyshock100",
        ]),
    ],

    "shotgun": [
        ("icons/obj/guns/gun.dmi", [
            "shotgun", "cshotgun", "dshotgun", "sawnshotgun", "compact-shotgun",
            "riotgun",
        ]),
        ("icons/mob/onmob/items/lefthand_guns.dmi", [
            "shotgun", "shotgun-wielded",
            "cshotgun", "cshotgun-wielded",
            "compact-shotgun", "compact-shotgun-wielded",
            "dshotgun", "dshotgun-wielded",
            "sawnshotgun",
            "riotgun",
        ]),
        ("icons/mob/onmob/items/righthand_guns.dmi", [
            "shotgun", "shotgun-wielded",
            "cshotgun", "cshotgun-wielded",
            "compact-shotgun", "compact-shotgun-wielded",
            "dshotgun", "dshotgun-wielded",
            "sawnshotgun",
            "riotgun",
        ]),
    ],

    "stunbaton": [
        # world-object sprites
        ("icons/obj/weapons.dmi", [
            "stunbaton", "stunbaton_active", "stunbaton_nocell",
            "baton",
            "mounted baton", "mounted baton_active", "mounted baton_nocell",
        ]),
        # inhand sprites
        ("icons/mob/onmob/items/lefthand.dmi",  ["baton", "classic_baton"]),
        ("icons/mob/onmob/items/righthand.dmi", ["baton", "classic_baton"]),
        # inventory slot icons
        ("icons/inv_slots/belts/icon.dmi",             ["stunbaton"]),
        ("icons/inv_slots/belts/mob.dmi",              ["baton", "classic_baton"]),
        ("icons/inv_slots/belts/mob_fat.dmi",          ["baton", "classic_baton"]),
        ("icons/inv_slots/belts/mob_slim.dmi",         ["baton", "classic_baton"]),
        ("icons/inv_slots/items/melee_l_default.dmi",  ["stunbaton", "baton"]),
        ("icons/inv_slots/items/melee_l_slim.dmi",     ["stunbaton", "baton"]),
        ("icons/inv_slots/items/melee_r_default.dmi",  ["stunbaton", "baton"]),
        ("icons/inv_slots/items/melee_r_slim.dmi",     ["stunbaton", "baton"]),
        ("icons/inv_slots/suitstorage/mob.dmi",        ["baton", "classic_baton"]),
        ("icons/inv_slots/suitstorage/mob_fat.dmi",    ["baton", "classic_baton"]),
        ("icons/inv_slots/suitstorage/mob_slim.dmi",   ["baton", "classic_baton"]),
    ],

    "fireaxe": [
        ("icons/obj/weapons.dmi", ["fireaxe0", "fireaxe1"]),
        ("icons/mob/onmob/items/lefthand.dmi",  ["fireaxe0", "fireaxe1"]),
        ("icons/mob/onmob/items/righthand.dmi", ["fireaxe0", "fireaxe1"]),
        ("icons/inv_slots/back/mob.dmi",               ["fireaxe0", "fireaxe1"]),
        ("icons/inv_slots/back/mob_fat.dmi",           ["fireaxe0", "fireaxe1"]),
        ("icons/inv_slots/back/mob_slim.dmi",          ["fireaxe0", "fireaxe1"]),
        ("icons/inv_slots/back/mob_slim_m.dmi",        ["fireaxe0", "fireaxe1"]),
        ("icons/inv_slots/items/items_l_default.dmi",  ["fireaxe0", "fireaxe1"]),
        ("icons/inv_slots/items/items_r_default.dmi",  ["fireaxe0", "fireaxe1"]),
    ],

    "claymore": [
        ("icons/obj/weapons.dmi", ["claymore"]),
        ("icons/mob/onmob/items/lefthand.dmi",  ["claymore"]),
        ("icons/mob/onmob/items/righthand.dmi", ["claymore"]),
        ("icons/inv_slots/back/mob.dmi",               ["claymore"]),
        ("icons/inv_slots/back/mob_fat.dmi",           ["claymore"]),
        ("icons/inv_slots/back/mob_slim.dmi",          ["claymore"]),
        ("icons/inv_slots/back/mob_slim_m.dmi",        ["claymore"]),
        ("icons/inv_slots/belts/mob.dmi",              ["claymore"]),
        ("icons/inv_slots/belts/mob_fat.dmi",          ["claymore"]),
        ("icons/inv_slots/belts/mob_slim.dmi",         ["claymore"]),
        ("icons/inv_slots/items/items_l_default.dmi",  ["claymore"]),
        ("icons/inv_slots/items/items_r_default.dmi",  ["claymore"]),
    ],

    "extinguisher": [
        ("icons/obj/items.dmi", ["fire_extinguisher0", "fire_extinguisher1"]),
    ],
}

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"Loading balloon source: {BALLOON_DMI.relative_to(REPO)}")
    bal_img, bal_sw, bal_sh, bal_states, _ = load_dmi(BALLOON_DMI)
    bal_index = build_offset_map(bal_states)

    for balloon_state, targets in REPLACEMENTS.items():
        if balloon_state not in bal_index:
            print(f"\n[WARN] Balloon state '{balloon_state}' not found in balloons.dmi — skipping")
            continue

        flat_start, bstate = bal_index[balloon_state]
        # use first sub-sprite (dir 0 frame 0) as the source
        source_sprite = get_sprite(bal_img, bal_sw, bal_sh, flat_start)

        print(f"\n-- {balloon_state} ({bal_sw}x{bal_sh}px source) ------------------")
        for dmi_rel, state_names in targets:
            print(f"  {dmi_rel}")
            apply_replacements(source_sprite, dmi_rel, state_names)

    print("\nDone.")

if __name__ == "__main__":
    main()
