"""Small, reproducible OpenType/CFF toolchain using the system FreeType library.

Outlines use M, L, C, Z commands in 1000-upem font units.
All exported paths are unhinted. Layout policy belongs to the shared exporter.
"""
from __future__ import annotations

import ctypes as C
import ctypes.util
import math
import struct
from pathlib import Path

P = struct.pack
U = struct.unpack_from


class Vector(C.Structure):
    _fields_ = [("x", C.c_long), ("y", C.c_long)]


class Generic(C.Structure):
    _fields_ = [("data", C.c_void_p), ("finalizer", C.c_void_p)]


class BBox(C.Structure):
    _fields_ = [(n, C.c_long) for n in ("xMin", "yMin", "xMax", "yMax")]


class Metrics(C.Structure):
    _fields_ = [(n, C.c_long) for n in ("width", "height", "horiBearingX", "horiBearingY", "horiAdvance", "vertBearingX", "vertBearingY", "vertAdvance")]


class Bitmap(C.Structure):
    _fields_ = [("rows", C.c_uint), ("width", C.c_uint), ("pitch", C.c_int), ("buffer", C.c_void_p), ("num_grays", C.c_ushort), ("pixel_mode", C.c_ubyte), ("palette_mode", C.c_ubyte), ("palette", C.c_void_p)]


class Outline(C.Structure):
    _fields_ = [("n_contours", C.c_short), ("n_points", C.c_short), ("points", C.POINTER(Vector)), ("tags", C.c_void_p), ("contours", C.c_void_p), ("flags", C.c_int)]


class Slot(C.Structure):
    _fields_ = [("library", C.c_void_p), ("face", C.c_void_p), ("next", C.c_void_p), ("glyph_index", C.c_uint), ("generic", Generic), ("metrics", Metrics), ("linearHoriAdvance", C.c_long), ("linearVertAdvance", C.c_long), ("advance", Vector), ("format", C.c_uint), ("bitmap", Bitmap), ("bitmap_left", C.c_int), ("bitmap_top", C.c_int), ("outline", Outline)]


class Face(C.Structure):
    _fields_ = [(n, C.c_long) for n in ("num_faces", "face_index", "face_flags", "style_flags", "num_glyphs")] + [("family_name", C.c_char_p), ("style_name", C.c_char_p), ("num_fixed_sizes", C.c_int), ("available_sizes", C.c_void_p), ("num_charmaps", C.c_int), ("charmaps", C.c_void_p), ("generic", Generic), ("bbox", BBox), ("units_per_EM", C.c_ushort)] + [(n, C.c_short) for n in ("ascender", "descender", "height", "max_advance_width", "max_advance_height", "underline_position", "underline_thickness")] + [("glyph", C.POINTER(Slot)), ("size", C.c_void_p), ("charmap", C.c_void_p)]


Move = C.CFUNCTYPE(C.c_int, C.POINTER(Vector), C.c_void_p)
Line = C.CFUNCTYPE(C.c_int, C.POINTER(Vector), C.c_void_p)
Conic = C.CFUNCTYPE(C.c_int, C.POINTER(Vector), C.POINTER(Vector), C.c_void_p)
Cubic = C.CFUNCTYPE(C.c_int, C.POINTER(Vector), C.POINTER(Vector), C.POINTER(Vector), C.c_void_p)


class OutlineFuncs(C.Structure):
    _fields_ = [("move_to", Move), ("line_to", Line), ("conic_to", Conic), ("cubic_to", Cubic), ("shift", C.c_int), ("delta", C.c_long)]


def freetype():
    lib = C.CDLL(C.util.find_library("freetype") or "/opt/homebrew/lib/libfreetype.dylib")
    lib.FT_Init_FreeType.argtypes = [C.POINTER(C.c_void_p)]
    lib.FT_New_Face.argtypes = [C.c_void_p, C.c_char_p, C.c_long, C.POINTER(C.POINTER(Face))]
    lib.FT_Load_Glyph.argtypes = [C.POINTER(Face), C.c_uint, C.c_int32]
    lib.FT_Get_Glyph_Name.argtypes = [C.POINTER(Face), C.c_uint, C.c_void_p, C.c_uint]
    lib.FT_Outline_Decompose.argtypes = [C.POINTER(Outline), C.POINTER(OutlineFuncs), C.c_void_p]
    lib.FT_Get_First_Char.argtypes = [C.POINTER(Face), C.POINTER(C.c_uint)]
    lib.FT_Get_First_Char.restype = C.c_ulong
    lib.FT_Get_Next_Char.argtypes = [C.POINTER(Face), C.c_ulong, C.POINTER(C.c_uint)]
    lib.FT_Get_Next_Char.restype = C.c_ulong
    lib.FT_Done_Face.argtypes = [C.POINTER(Face)]
    lib.FT_Done_FreeType.argtypes = [C.c_void_p]
    return lib


def extract_font(path, embolden=0, index=0):
    """Decode outlines in font units; embolden is one strength or an (x, y) pair.

    FreeType keeps the lower-left edge fixed, so a strength s grows the outline
    by s toward the upper right; callers recentre with -s/2.
    """
    strength_x, strength_y = embolden if isinstance(embolden, tuple) else (embolden, embolden)
    lib = freetype()
    library = C.c_void_p()
    assert lib.FT_Init_FreeType(C.byref(library)) == 0
    face = C.POINTER(Face)()
    assert lib.FT_New_Face(library, str(path).encode(), index, C.byref(face)) == 0
    glyphs = []
    current = []

    @Move
    def move(p, _):
        if current:
            current.append(["Z"])
        current.append(["M", p.contents.x, p.contents.y])
        return 0

    @Line
    def line(p, _):
        current.append(["L", p.contents.x, p.contents.y])
        return 0

    @Conic
    def conic(p, end, _):
        x0, y0 = current[-1][-2:]
        x1, y1, x2, y2 = p.contents.x, p.contents.y, end.contents.x, end.contents.y
        current.append(["C", x0 + (x1 - x0) * 2 / 3, y0 + (y1 - y0) * 2 / 3, x2 + (x1 - x2) * 2 / 3, y2 + (y1 - y2) * 2 / 3, x2, y2])
        return 0

    @Cubic
    def cubic(a, b, end, _):
        current.append(["C", a.contents.x, a.contents.y, b.contents.x, b.contents.y, end.contents.x, end.contents.y])
        return 0

    funcs = OutlineFuncs(move, line, conic, cubic, 0, 0)
    for gid in range(face.contents.num_glyphs):
        assert lib.FT_Load_Glyph(face, gid, 11) == 0, gid
        current = []
        slot = face.contents.glyph.contents
        if slot.outline.n_points:
            if strength_x or strength_y:
                lib.FT_Outline_EmboldenXY.argtypes = [C.POINTER(Outline), C.c_long, C.c_long]
                assert lib.FT_Outline_EmboldenXY(C.byref(slot.outline), strength_x, strength_y) == 0
            assert lib.FT_Outline_Decompose(C.byref(slot.outline), C.byref(funcs), None) == 0
            current.append(["Z"])
        buf = C.create_string_buffer(256)
        lib.FT_Get_Glyph_Name(face, gid, buf, 256)
        glyphs.append({"name": buf.value.decode() or f"gid{gid}", "advance": slot.metrics.horiAdvance, "path": current})
    charmap = {}
    gid = C.c_uint()
    code = lib.FT_Get_First_Char(face, C.byref(gid))
    while gid.value:
        charmap[str(code)] = gid.value
        code = lib.FT_Get_Next_Char(face, code, C.byref(gid))
    result = {"upem": face.contents.units_per_EM, "family": face.contents.family_name.decode(), "cmap": charmap, "glyphs": glyphs}
    lib.FT_Done_Face(face)
    lib.FT_Done_FreeType(library)
    return result


def bbox(path):
    # Including the control points gives a conservative outline bounding box.
    points = [(c[i], c[i + 1]) for c in path for i in range(1, len(c), 2)]
    if not points:
        return (0, 0, 0, 0)
    xs, ys = zip(*points)
    return (math.floor(min(xs)), math.floor(min(ys)), math.ceil(max(xs)), math.ceil(max(ys)))


def contours(path):
    result, current = [], []
    for c in path:
        if c[0] == "M" and current:
            result.append(current)
            current = []
        current.append(c)
        if c[0] == "Z":
            result.append(current)
            current = []
    if current:
        result.append(current)
    return result


def spans_at(path, y):
    """Dark runs crossing height y, left to right."""
    xs = []
    for contour in contours(path):
        points, current = [], None
        for cmd in contour:
            if cmd[0] == 'M':
                current = cmd[1:3]
                points.append(current)
            elif cmd[0] == 'L':
                current = cmd[1:3]
                points.append(current)
            elif cmd[0] == 'C':
                (x0, y0), (x1, y1, x2, y2, x3, y3) = current, cmd[1:]
                for i in range(1, 13):
                    t = i / 12
                    a, b = (1 - t) ** 3, 3 * (1 - t) ** 2 * t
                    c, d = 3 * (1 - t) * t * t, t ** 3
                    points.append((a * x0 + b * x1 + c * x2 + d * x3, a * y0 + b * y1 + c * y2 + d * y3))
                current = cmd[5:7]
        for (xa, ya), (xb, yb) in zip(points, points[1:] + points[:1]):
            if (ya <= y < yb) or (yb <= y < ya):
                xs.append(xa + (y - ya) * (xb - xa) / (yb - ya))
    xs.sort()
    return [(xs[i], xs[i + 1]) for i in range(0, len(xs) - 1, 2)]


def map_path(path, fn):
    return [[c[0]] + [v for i in range(1, len(c), 2) for v in fn(c[i], c[i + 1])] for c in path]


def sfnt_tables(path):
    data = Path(path).read_bytes()
    return {tag.decode(): data[offset:offset + length] for tag, _, offset, length in [U(">4sIII", data, 12 + i * 16) for i in range(U(">H", data, 4)[0])]}


def checksum(data):
    data = data + b"\0" * (-len(data) % 4)
    return sum(U(">I", data, i)[0] for i in range(0, len(data), 4)) & 0xFFFFFFFF


def make_sfnt(tables, flavor=b"OTTO"):
    tables = dict(tables)
    head = bytearray(tables["head"])
    head[8:12] = b"\0" * 4
    tables["head"] = bytes(head)
    n = len(tables)
    power = int(math.log2(n))
    directory = flavor + P(">HHHH", n, 16 * 2**power, power, n * 16 - 16 * 2**power)
    offset = 12 + n * 16
    chunks = []
    head_offset = 0
    for tag in sorted(tables):
        data = tables[tag]
        if tag == "head":
            head_offset = offset
        directory += P(">4sIII", tag.encode(), checksum(data), offset, len(data))
        chunks.append(data + b"\0" * (-len(data) % 4))
        offset += len(chunks[-1])
    result = bytearray(directory + b"".join(chunks))
    result[head_offset + 8:head_offset + 12] = P(">I", (0xB1B0AFBA - checksum(result)) & 0xFFFFFFFF)
    return bytes(result)


def _table_checksum(tag, data):
    """Directory checksum; head is summed with checkSumAdjustment cleared."""
    if tag == 'head':
        data = data[:8] + b'\0\0\0\0' + data[12:]
    return checksum(data)


def make_collection(paths, output):
    """An OpenType Collection (version 1.0) of the given fonts.

    Each member keeps its tables byte for byte, including its own head
    checkSumAdjustment; identical tables are stored once and shared.
    """
    fonts = [sfnt_tables(p) for p in paths]
    flavors = {Path(p).read_bytes()[:4] for p in paths}
    assert flavors == {b'OTTO'}, 'collections here hold CFF-flavoured OpenType fonts'
    header = 12 + 4 * len(fonts)
    directories = [12 + 16 * len(f) for f in fonts]
    offset = header + sum(directories)
    stored, blobs = {}, []
    for tables in fonts:
        for tag in sorted(tables):
            data = tables[tag]
            if data not in stored:
                stored[data] = offset
                blobs.append(data + b'\0' * (-len(data) % 4))
                offset += len(blobs[-1])
    out = b'ttcf' + P('>HHI', 1, 0, len(fonts))
    position = header
    for size in directories:
        out += P('>I', position)
        position += size
    for tables in fonts:
        n = len(tables)
        power = 2 ** int(math.log2(n))
        out += b'OTTO' + P('>HHHH', n, 16 * power, int(math.log2(power)), n * 16 - 16 * power)
        for tag in sorted(tables):
            data = tables[tag]
            out += P('>4sIII', tag.encode(), _table_checksum(tag, data), stored[data], len(data))
    Path(output).write_bytes(out + b''.join(blobs))


def collection_tables(path):
    """Tables of every member of an OpenType Collection, in order."""
    data = Path(path).read_bytes()
    assert data[:4] == b'ttcf', 'not an OpenType Collection'
    count = U('>I', data, 8)[0]
    members = []
    for i in range(count):
        at = U('>I', data, 12 + 4 * i)[0]
        n = U('>H', data, at + 4)[0]
        tables = {}
        for k in range(n):
            tag, check, offset, length = U('>4sIII', data, at + 12 + 16 * k)
            table = data[offset:offset + length]
            assert _table_checksum(tag.decode(), table) == check, (i, tag)
            tables[tag.decode()] = table
        members.append(tables)
    return members


def cff_num(n):
    n = round(n)
    if -107 <= n <= 107:
        return bytes([n + 139])
    if 108 <= n <= 1131:
        return bytes([(n - 108) // 256 + 247, (n - 108) % 256])
    if -1131 <= n <= -108:
        return bytes([(-n - 108) // 256 + 251, (-n - 108) % 256])
    if -32768 <= n <= 32767:
        return b"\x1c" + P(">h", n)
    return b"\x1d" + P(">i", n)


def cff_index(items):
    if not items:
        return b"\0\0"
    offsets, value = [1], 1
    for s in items:
        value += len(s)
        offsets.append(value)
    size = max(1, (value.bit_length() + 7) // 8)
    return P(">HB", len(items), size) + b"".join(x.to_bytes(size, "big") for x in offsets) + b"".join(items)


def type2(path, advance):
    data = cff_num(advance)
    x, y = 0, 0
    for c in path:
        op = c[0]
        coords = [round(v) for v in c[1:]]
        if op in ("M", "L"):
            nx, ny = coords
            data += cff_num(nx - x) + cff_num(ny - y) + (b"\x15" if op == "M" else b"\x05")
            x, y = nx, ny
        elif op == "C":
            for i in range(0, 6, 2):
                nx, ny = coords[i:i + 2]
                data += cff_num(nx - x) + cff_num(ny - y)
                x, y = nx, ny
            data += b"\x08"
        elif op == "Z":
            pass  # Type 2 closes the contour at the next moveto/endchar.
        else:
            raise ValueError(op)
    return data + b"\x0e"


def make_cff(glyphs, bounds, naming, version, fixed_pitch=False, italic_angle=0):
    """naming: postscript, full, family and weight strings for the Top DICT."""
    postscript = naming["postscript"]
    names = [g["name"].encode("ascii") for g in glyphs[1:]]
    extra = [version.encode(), naming["full"].encode(), naming["family"].encode(), naming["weight"].encode(), b"Derived from TeX Gyre Pagella; GUST Font License. See bundled license and source attribution."]
    first = 391 + len(names)
    strings = cff_index(names + extra)
    charstrings = cff_index([type2(g["path"], g["advance"]) for g in glyphs])
    charset = b"\0" + b"".join(P(">H", i + 390) for i in range(1, len(glyphs)))
    prefix = b"\x01\x00\x04\x04" + cff_index([postscript.encode()])
    top = b""
    for _ in range(8):
        start = len(prefix) + len(cff_index([top])) + len(strings) + 2
        charset_at, cs_at = start, start + len(charset)
        private_at = cs_at + len(charstrings)
        new = cff_num(first) + b"\0" + cff_num(first + 4) + b"\x01" + cff_num(first + 1) + b"\x02" + cff_num(first + 2) + b"\x03" + cff_num(first + 3) + b"\x04"
        new += b"".join(cff_num(v) for v in bounds) + b"\x05"
        if fixed_pitch:
            new += cff_num(1) + b"\x0c\x01"
        if italic_angle:
            new += cff_num(italic_angle) + b"\x0c\x02"
        new += cff_num(charset_at) + b"\x0f" + cff_num(cs_at) + b"\x11" + cff_num(0) + cff_num(private_at) + b"\x12"
        if new == top:
            break
        top = new
    else:
        raise AssertionError("CFF offsets did not converge")
    return prefix + cff_index([top]) + strings + b"\0\0" + charset + charstrings


def name_table(naming, version, description):
    """naming: typographic family/style, legacy (style-linked) family/style, full and PostScript names."""
    copyright_text = "Vespera modifications 2026. Based on TeX Gyre Pagella. Copyright 2006-2018 for TeX Gyre extensions by B. Jackowski, J.M. Nowacki, et al. (on behalf of TeX USERS GROUPS). Vietnamese characters by Han The Thanh. Based on URW Palladio L."
    postscript = naming["postscript"]
    entries = {
        0: copyright_text, 1: naming["legacy_family"], 2: naming["legacy_style"],
        3: f"{version};FVB;{postscript}", 4: naming["full"],
        5: f"Version {version}" + (f"; {naming['release']}" if naming.get('release', version) != version else ""),
        6: postscript,
        7: "Palatino is a trademark of its respective owner. Vespera is an independent derivative of TeX Gyre Pagella.",
        8: "FontViber",
        9: "Vespera modifications: FontViber. Original Pagella: Boguslaw Jackowski, Janusz M. Nowacki, Piotr Pianowski, Piotr Strzelczyk.",
        10: description,
        13: "Distributed under the GUST Font License (GFL), an instance of the LaTeX Project Public License 1.3c or later. See the bundled GUST-FONT-LICENSE.txt and lppl.txt.",
        14: "https://tug.org/fonts/licenses/GUST-FONT-LICENSE.txt",
        16: naming["family"], 17: naming["style"],
    }
    records, strings = [], b""
    for key, value in sorted(entries.items()):
        data = value.encode("utf-16-be")
        records.append(P(">HHHHHH", 3, 1, 0x409, key, len(data), len(strings)))
        strings += data
    return P(">HHH", 0, len(records), 6 + 12 * len(records)) + b"".join(records) + strings


def woff2_from_otf(otf, output, version):
    """WOFF2 with original CFF tables and Brotli font-mode compression."""
    # Fixed-width tags cannot be split on spaces because 'CFF ' is space-padded.
    tags = ["cmap", "head", "hhea", "hmtx", "maxp", "name", "OS/2", "post", "cvt ", "fpgm", "glyf", "loca", "prep", "CFF ", "VORG", "EBDT", "EBLC", "gasp", "hdmx", "kern", "LTSH", "PCLT", "VDMX", "vhea", "vmtx", "BASE", "GDEF", "GPOS", "GSUB", "EBSC", "JSTF", "MATH", "CBDT", "CBLC", "COLR", "CPAL", "SVG ", "sbix", "acnt", "avar", "bdat", "bloc", "bsln", "cvar", "fdsc", "feat", "fmtx", "fvar", "gvar", "hsty", "just", "lcar", "mort", "morx", "opbd", "prop", "trak", "Zapf", "Silf", "Glat", "Gloc", "Feat", "Sill"]

    def base128(n):
        parts = [n & 127]
        n >>= 7
        while n:
            parts.append((n & 127) | 128)
            n >>= 7
        return bytes(reversed(parts))

    tables = sfnt_tables(otf)
    head = bytearray(tables["head"])
    head[16:18] = P(">H", U(">H", head, 16)[0] | (1 << 11))
    tables["head"] = bytes(head)
    directory, raw = b"", b""
    for tag, table in sorted(tables.items()):
        idx = tags.index(tag) if tag in tags else 63
        directory += bytes([idx]) + (tag.encode() if idx == 63 else b"") + base128(len(table))
        raw += table
    lib = C.CDLL(C.util.find_library("brotlienc") or "/opt/homebrew/lib/libbrotlienc.dylib")
    lib.BrotliEncoderMaxCompressedSize.argtypes = [C.c_size_t]
    lib.BrotliEncoderMaxCompressedSize.restype = C.c_size_t
    lib.BrotliEncoderCompress.argtypes = [C.c_int, C.c_int, C.c_int, C.c_size_t, C.c_void_p, C.POINTER(C.c_size_t), C.c_void_p]
    size = C.c_size_t(lib.BrotliEncoderMaxCompressedSize(len(raw)))
    out = C.create_string_buffer(size.value)
    assert lib.BrotliEncoderCompress(11, 22, 2, len(raw), raw, C.byref(size), out) == 1
    compressed = out.raw[:size.value]
    length = 48 + len(directory) + len(compressed)
    padding = b"\0" * (-length % 4)
    major, minor = map(int, version.split('.'))
    header = P(">4s4sIHHIIHHIIIII", b"wOF2", b"OTTO", length + len(padding), len(tables), 0, Path(otf).stat().st_size, len(compressed), major, minor, 0, 0, 0, 0, 0)
    output.write_bytes(header + directory + compressed + padding)
