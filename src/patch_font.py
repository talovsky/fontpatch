#!/usr/bin/env python3
"""Patch a font with Cyrillic and Hebrew glyphs from two donor fonts.

Examples:
  python3 src/patch_font.py \
    --base TX-02/TX-02-Regular.otf \
    --cyrillic IoskeleyMono/Normal/Unhinted/IoskeleyMono-Regular.ttf \
    --hebrew Cousine/Cousine-Regular.ttf \
    --output TX-03/TX-03-Regular.otf --family TX-03 --subfamily Regular

The tool retains all base-font glyphs, adds only missing codepoints, scales
donor outlines to the base font UPM, and centres them in the base font's
monospace cell. It supports CFF OTF and TrueType glyf base fonts.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from fontTools.misc.transform import Transform
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

CYRILLIC_RANGES = ((0x0400, 0x052F), (0x2DE0, 0x2DFF), (0xA640, 0xA69F))
HEBREW_RANGES = ((0x0590, 0x05FF), (0xFB1D, 0xFB4F))
HEBREW_EXTRAS = {0x20AA}
HEBREW_MARKS = set(range(0x0591, 0x05BE)) | set(range(0x05BF, 0x05C8)) | {0xFB1E}


def included(codepoint: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(first <= codepoint <= last for first, last in ranges)


def recording(font: TTFont, glyph_name: str) -> DecomposingRecordingPen:
    pen = DecomposingRecordingPen(font.getGlyphSet())
    font.getGlyphSet()[glyph_name].draw(pen)
    return pen


def outline(font: TTFont, glyph_name: str, target_upm: int, advance: int, mark: bool, cff: bool):
    """Return a transformed CFF charstring or TrueType glyph and its LSB."""
    rec = recording(font, glyph_name)
    points = [point for _, args in rec.value for point in args if isinstance(point, tuple)]
    scale = target_upm / font["head"].unitsPerEm
    if points:
        xs = [point[0] for point in points]
        width = (max(xs) - min(xs)) * scale
        desired_x_min = -(advance + width) / 2 if mark else (advance - width) / 2
        translate_x = desired_x_min - min(xs) * scale
    else:
        translate_x = 0
    transform = Transform(scale, 0, 0, scale, translate_x, 0)
    pen = T2CharStringPen(width=0, glyphSet=None) if cff else TTGlyphPen(None)
    rec.replay(TransformPen(pen, transform))
    glyph = pen.getCharString() if cff else pen.glyph()
    return glyph, getattr(glyph, "xMin", 0)


def add_from_donor(target: TTFont, donor: TTFont, ranges, extras, tag: str) -> list[int]:
    cmap = target.getBestCmap() or {}
    donor_cmap = donor.getBestCmap() or {}
    advance = target["hmtx"].metrics[cmap[ord("A")]][0]
    target_upm = target["head"].unitsPerEm
    is_cff = "CFF " in target
    if not is_cff and "glyf" not in target:
        raise ValueError("Base font must contain a CFF or glyf outline table")
    if is_cff:
        top_dict = target["CFF "].cff.topDictIndex[0]
        charstrings = top_dict.CharStrings.charStrings
        charstring_index = top_dict.CharStrings.charStringsIndex
        glyph_store = top_dict.charset
    else:
        glyph_store = target["glyf"]

    added = []
    for codepoint in sorted(donor_cmap):
        if not (included(codepoint, ranges) or codepoint in extras) or codepoint in cmap:
            continue
        glyph_name = f"uni{codepoint:04X}.bridge.{tag}"
        if glyph_name in glyph_store:
            continue
        mark = tag == "hebrew" and codepoint in HEBREW_MARKS
        glyph, lsb = outline(donor, donor_cmap[codepoint], target_upm, advance, mark, is_cff)
        if is_cff:
            glyph.private = top_dict.Private
            glyph.globalSubrs = top_dict.GlobalSubrs
            charstrings[glyph_name] = len(charstring_index)
            charstring_index.append(glyph)
            glyph_store.append(glyph_name)
        else:
            glyph_store[glyph_name] = glyph
        target["hmtx"].metrics[glyph_name] = (0 if mark else advance, lsb)
        for subtable in target["cmap"].tables:
            if subtable.isUnicode():
                subtable.cmap[codepoint] = glyph_name
        cmap[codepoint] = glyph_name
        added.append(codepoint)
    return added


def font_name(font: TTFont, name_id: int) -> str:
    record = font["name"].getName(name_id, 3, 1, 0x409)
    return record.toUnicode() if record else "unknown donor"


def rename(font: TTFont, family: str, subfamily: str, cyrillic: TTFont, hebrew: TTFont) -> None:
    full = family if subfamily == "Regular" else f"{family} {subfamily}"
    postscript = full.replace(" ", "")
    # Keep the copyright statements of all three source fonts in the output;
    # renaming a derivative must not erase the attribution of its inputs.
    copyright = (
        f"Base: {font_name(font, 0)} | Cyrillic donor ({font_name(cyrillic, 1)}): "
        f"{font_name(cyrillic, 0)} | Hebrew donor ({font_name(hebrew, 1)}): "
        f"{font_name(hebrew, 0)} | Patched derivative."
    )
    values = {0: copyright, 1: family, 2: subfamily, 3: f"1.0;BRDG;{postscript}", 4: full,
              5: "Version 1.0", 6: postscript, 16: family, 17: subfamily}
    for name_id, value in values.items():
        font["name"].setName(value, name_id, 3, 1, 0x409)
        font["name"].setName(value, name_id, 1, 0, 0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", type=Path, required=True, help="base OTF or TTF")
    parser.add_argument("--cyrillic", type=Path, required=True, help="Cyrillic donor OTF or TTF")
    parser.add_argument("--hebrew", type=Path, required=True, help="Hebrew donor OTF or TTF")
    parser.add_argument("--output", type=Path, required=True, help="patched output path")
    parser.add_argument("--family", required=True, help="new font family name")
    parser.add_argument("--subfamily", default="Regular", help="new subfamily name (default: Regular)")
    args = parser.parse_args()

    base, cyrillic, hebrew = TTFont(args.base), TTFont(args.cyrillic), TTFont(args.hebrew)
    cyrillic_added = add_from_donor(base, cyrillic, CYRILLIC_RANGES, set(), "cyrillic")
    hebrew_added = add_from_donor(base, hebrew, HEBREW_RANGES, HEBREW_EXTRAS, "hebrew")
    rename(base, args.family, args.subfamily, cyrillic, hebrew)
    base["maxp"].numGlyphs = len(base.getGlyphOrder())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    base.save(args.output)
    print(f"wrote {args.output}: +{len(cyrillic_added)} Cyrillic, +{len(hebrew_added)} Hebrew")


if __name__ == "__main__":
    main()
