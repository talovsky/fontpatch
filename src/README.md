# Generic Font Patcher

`patch_font.py` adds **missing** Cyrillic characters from one donor font and
**missing** Hebrew characters from another donor font to a base font. It does
not replace any glyph already present in the base font.

It was written as the reusable implementation behind the TX-03 work, so it is
kept separate from the TX-02-specific build script.

## Requirements

Python 3.10+ and [fontTools](https://github.com/fonttools/fonttools):

```sh
python3 -m pip install 'fonttools>=4.50'
```

## Static checking

Run `basedpyright` at the repository root. The root `pyrightconfig.json`
keeps standard checking enabled and suppresses diagnostics that result from
FontTools' dynamic font-table API and incomplete type stubs.

## Usage

Run from the repository root and provide one base font plus one donor for each
script:

```sh
python3 src/patch_font.py \
  --base path/to/Base-Regular.otf \
  --cyrillic path/to/Cyrillic-Donor-Regular.ttf \
  --hebrew path/to/Hebrew-Donor-Regular.ttf \
  --output path/to/Patched-Regular.otf \
  --family 'Patched Font' \
  --subfamily Regular
```

For an italic/bold face, pass donors of the equivalent style and set the
matching subfamily:

```sh
python3 src/patch_font.py \
  --base path/to/Base-BoldItalic.ttf \
  --cyrillic path/to/Cyrillic-Donor-BoldItalic.ttf \
  --hebrew path/to/Hebrew-Donor-BoldItalic.ttf \
  --output path/to/Patched-BoldItalic.ttf \
  --family 'Patched Font' \
  --subfamily 'Bold Italic'
```

## Behaviour

- Covers Cyrillic U+0400–U+052F, U+2DE0–U+2DFF, and U+A640–U+A69F.
- Covers Hebrew U+0590–U+05FF and U+FB1D–U+FB4F, plus the shekel sign U+20AA.
- Scales each donor outline to the base font's units-per-em and centres it in
  the advance width of the base font's `A` glyph. Hebrew combining marks get a
  zero advance and are offset over the preceding cell.
- Preserves the base font's existing glyphs, tables, and feature definitions.
- Renames the output using the requested family/subfamily and retains the
  copyright strings from the base and both donor fonts in its name table.

## Supported inputs and limitations

The base font must be a static OpenType font containing either a legacy CFF
(`CFF `) outline table or a TrueType `glyf` outline table. Donor fonts may be
OTF or TTF. Variable fonts and CFF2 fonts are not supported.

The tool is intended for monospace base fonts. It uses the `A` glyph’s advance
as the target cell width; edit `patch_font.py` if a different reference glyph
or layout is needed. It transfers outlines only: it does not copy donor GPOS,
GSUB, hinting, or script-specific mark anchors.

## Licensing

The result is a derivative of all three input fonts. Confirm that their
licences permit the intended use and redistribution, and distribute the
required licence texts and attributions with any output font.
