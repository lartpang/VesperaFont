"""Native HarfBuzz shaping, independent of any artwork or Python packages."""
from __future__ import annotations

import ctypes as C
import ctypes.util
from pathlib import Path



class GlyphInfo(C.Structure):
    _fields_ = [("codepoint", C.c_uint32), ("mask", C.c_uint32), ("cluster", C.c_uint32), ("var1", C.c_uint32), ("var2", C.c_uint32)]


class GlyphPosition(C.Structure):
    _fields_ = [("x_advance", C.c_int32), ("y_advance", C.c_int32), ("x_offset", C.c_int32), ("y_offset", C.c_int32), ("var", C.c_uint32)]


class Type:
    def __init__(self, font_path, data):
        self.path = Path(font_path)
        self.data = data
        self.upem = self.data["upem"]
        self.byname = {g["name"]: g for g in self.data["glyphs"]}
        h = self.hb = C.CDLL(C.util.find_library("harfbuzz") or "/opt/homebrew/lib/libharfbuzz.dylib")
        h.hb_blob_create_from_file_or_fail.argtypes = [C.c_char_p]
        h.hb_blob_create_from_file_or_fail.restype = C.c_void_p
        h.hb_face_create.argtypes = [C.c_void_p, C.c_uint]
        h.hb_face_create.restype = C.c_void_p
        h.hb_font_create.argtypes = [C.c_void_p]
        h.hb_font_create.restype = C.c_void_p
        h.hb_ot_font_set_funcs.argtypes = [C.c_void_p]
        h.hb_font_set_scale.argtypes = [C.c_void_p, C.c_int, C.c_int]
        h.hb_buffer_create.restype = C.c_void_p
        h.hb_buffer_add_utf8.argtypes = [C.c_void_p, C.c_char_p, C.c_int, C.c_uint, C.c_int]
        h.hb_buffer_guess_segment_properties.argtypes = [C.c_void_p]
        h.hb_shape.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p, C.c_uint]
        h.hb_buffer_get_glyph_infos.argtypes = [C.c_void_p, C.POINTER(C.c_uint)]
        h.hb_buffer_get_glyph_infos.restype = C.POINTER(GlyphInfo)
        h.hb_buffer_get_glyph_positions.argtypes = [C.c_void_p, C.POINTER(C.c_uint)]
        h.hb_buffer_get_glyph_positions.restype = C.POINTER(GlyphPosition)
        h.hb_buffer_destroy.argtypes = [C.c_void_p]
        h.hb_font_destroy.argtypes = [C.c_void_p]
        h.hb_face_destroy.argtypes = [C.c_void_p]
        h.hb_blob_destroy.argtypes = [C.c_void_p]
        self.blob = h.hb_blob_create_from_file_or_fail(str(self.path).encode())
        assert self.blob, self.path
        self.face = h.hb_face_create(self.blob, 0)
        self.font = h.hb_font_create(self.face)
        h.hb_ot_font_set_funcs(self.font)
        h.hb_font_set_scale(self.font, self.upem, self.upem)

    def close(self):
        if self.font:
            self.hb.hb_font_destroy(self.font)
            self.hb.hb_face_destroy(self.face)
            self.hb.hb_blob_destroy(self.blob)
            self.font = self.face = self.blob = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def shape(self, text, tracking=0):
        h = self.hb
        buf = h.hb_buffer_create()
        utf8 = text.encode()
        h.hb_buffer_add_utf8(buf, utf8, len(utf8), 0, -1)
        h.hb_buffer_guess_segment_properties(buf)
        h.hb_shape(self.font, buf, None, 0)
        count = C.c_uint()
        infos = h.hb_buffer_get_glyph_infos(buf, C.byref(count))
        positions = h.hb_buffer_get_glyph_positions(buf, C.byref(count))
        x, out = 0, []
        for i in range(count.value):
            inf, pos = infos[i], positions[i]
            out.append((inf.codepoint, x + pos.x_offset, pos.y_offset))
            x += pos.x_advance + tracking
        h.hb_buffer_destroy(buf)
        return out, x - (tracking if out else 0)

    def width(self, text, size, tracking=0):
        return self.shape(text, tracking)[1] * size / self.upem

