# Sources

English | [简体中文](README.zh-CN.md)

This folder holds all the original data the build needs, all of it text:

- `texgyrepagella-regular.txt`: text source of **TeX Gyre Pagella Regular 2.501**, the origin of the roman outlines and layout tables;
- `texgyrepagella-italic.txt`: text source of **TeX Gyre Pagella Italic 2.501**, the origin of the cursive italic;
- `spacing/TeXGyrePagellaX-*.json.gz`: **spacing parameters** extracted from **TeX Gyre Pagella X** Regular, Italic, Bold and BoldItalic (Michael Sharpe's extension of Pagella, shipped with the newpx package, taken from TeX Live 2026): each glyph's name, advance and ink box, the Unicode mapping, and the kerning.

## Text sources

Each font is one UTF-8 text file (the format is defined in `fontviber/source.py`), containing in order:

- the header `fontviber-source 1`, and the file name and SHA-256 of the font it was converted from (`from …`);
- `info` lines: family name, units per em, ascender and descender, x-height, cap height, italic angle, and the original copyright, trademark, designer and license notices (values are JSON);
- one block per glyph, in glyph order (mark positioning refers to glyph ids, so the order must be kept): `glyph` name, `advance` width, `unicode` code points, and the outline commands `M x y` (start), `L x y` (line), `C x1 y1 x2 y2 x y` (cubic curve) and `Z` (close), in font units with y up;
- at the end, the 8 OpenType tables the build reuses as they are (GDEF, GPOS, GSUB, OS/2, head, hhea, maxp, post), in hexadecimal. Writing the ligature and mark-positioning rules as a readable `.fea` file would need a feature compiler to rebuild them, and this project uses only the standard library, so the original tables are kept.

```text
glyph A
advance 778
unicode 0041
M 15 -3
C 51 -1 88 0 124 0
…
Z
```

Both text sources were converted from the original OTFs (`texgyrepagella-regular.otf` SHA-256 `44e64260716d8f2bbe412baa1ee99b7c995190ac4573177c24def0b9200438c7`, `texgyrepagella-italic.otf` SHA-256 `069bb27f48eb98a741715227fc6e4b7baf3639c29fc13925f70d1ed8884ac29a`, both from TeX Live 2026). Every glyph and table is read back and compared after conversion, so fonts built from the text sources are byte-identical to fonts built from the original OTFs, and the same font always converts to the same bytes. To convert again:

```bash
python3 build.py source --font /usr/local/texlive/2026/texmf-dist/fonts/opentype/public/tex-gyre/texgyrepagella-regular.otf --output sources/texgyrepagella-regular.txt
```

To inspect a source in a font editor such as FontForge, Glyphs or RoboFont, export it as UFO 3 (an output path ending in `.ufo`; the same command converts a UFO back to a text source):

```bash
python3 build.py source --font sources/texgyrepagella-regular.txt --output texgyrepagella-regular.ufo
```

## Spacing parameters

The spacing files are gzip-compressed JSON (read them with `gunzip -c`); each records the file name and SHA-256 of the font it was extracted from. To replace or update a spacing reference, extract it again from the Pagella X font:

```bash
python3 build.py spacing --font TeXGyrePagellaX-Regular.otf --output sources/spacing/TeXGyrePagellaX-Regular.json.gz
```

The same font always gives the same bytes. After converting or extracting again, update the matching `*_sha256` in `configs/*.json`.

Digests:

```text
ff8920a7d55f525a94ff02e4f35d847c1be059459a27c9e90be94769586e6483  texgyrepagella-regular.txt
f3a512dfc5f7ac886239c1b6e6664627cafe423807556fa5b9f5264531629070  texgyrepagella-italic.txt
f72c17473f1a8b3b5f7b5dc274f850bbb1aeb60d249112707570394c781470b1  spacing/TeXGyrePagellaX-Regular.json.gz
e246c62eafa1f285ec621e49d317d0304329878d942c6d08d3cb88bd1dc5f60b  spacing/TeXGyrePagellaX-Italic.json.gz
cab2e03efe1170d431be85a90e556d2d9355614957629161294dd970bfaaf957  spacing/TeXGyrePagellaX-Bold.json.gz
31305eec9835f9b33dbf37db4eff528f3b7d0b4ff051f691c5e1ed1a98c15d4a  spacing/TeXGyrePagellaX-BoldItalic.json.gz
```

The parameters were extracted from these Pagella X fonts (SHA-256):

```text
3c1857b64342b89a585c6c065c0ba4a5c608d42c88b87bd5255b623d0128ef2d  TeXGyrePagellaX-Regular.otf
9cb8432910882fa9e417795597806d289f5b50322e5f2c3395f8325cccf47e8d  TeXGyrePagellaX-Italic.otf
824327ff1ffa8134a20ac7cdc212854aa69851af24ca3107c6ca7c73a7ae91af  TeXGyrePagellaX-Bold.otf
edb659487607638919866d51b226efc07816f8916ba4898d746ef0b4c8c89601  TeXGyrePagellaX-BoldItalic.otf
```

These files are kept together with the original [GUST Font License](../licenses/GUST-FONT-LICENSE.txt), [LPPL](../licenses/lppl.txt), [author and copyright notes](../licenses/README-TeX-Gyre-Pagella.txt) and [original manifest](../licenses/MANIFEST-TeX-Gyre-Pagella.txt); the Pagella X extension is described in [MANIFEST-newpx.txt](../licenses/MANIFEST-newpx.txt) (newpx is distributed under LPPL 1.3). The complete upstream works are at [CTAN TeX Gyre](https://ctan.org/tex-archive/fonts/tex-gyre) and [CTAN newpx](https://ctan.org/pkg/newpx).

The derived letter designs live in the Python code in `fontviber/`. Outlines produced during a build exist only in memory; no decoded copies, earlier fonts or pre-generated Display / Mono outlines need to be kept.
