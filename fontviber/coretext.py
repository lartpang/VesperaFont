"""macOS font loading and spacing checks, used when CoreText is available."""
import ctypes as C


def coretext_check(path, postscript_name, cell_advance=None):
    cf = C.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    ct = C.CDLL("/System/Library/Frameworks/CoreText.framework/CoreText")
    cf.CFURLCreateFromFileSystemRepresentation.argtypes = [C.c_void_p, C.c_char_p, C.c_long, C.c_bool]
    cf.CFURLCreateFromFileSystemRepresentation.restype = C.c_void_p
    ct.CTFontManagerCreateFontDescriptorsFromURL.argtypes = [C.c_void_p]
    ct.CTFontManagerCreateFontDescriptorsFromURL.restype = C.c_void_p
    cf.CFArrayGetCount.argtypes = [C.c_void_p]; cf.CFArrayGetCount.restype = C.c_long
    cf.CFArrayGetValueAtIndex.argtypes = [C.c_void_p, C.c_long]; cf.CFArrayGetValueAtIndex.restype = C.c_void_p
    ct.CTFontCreateWithFontDescriptor.argtypes = [C.c_void_p, C.c_double, C.c_void_p]
    ct.CTFontCreateWithFontDescriptor.restype = C.c_void_p
    ct.CTFontGetGlyphsForCharacters.argtypes = [C.c_void_p, C.POINTER(C.c_ushort), C.POINTER(C.c_ushort), C.c_long]
    ct.CTFontGetGlyphsForCharacters.restype = C.c_bool
    ct.CTFontCopyPostScriptName.argtypes = [C.c_void_p]; ct.CTFontCopyPostScriptName.restype = C.c_void_p
    cf.CFStringGetCString.argtypes = [C.c_void_p, C.c_void_p, C.c_long, C.c_uint32]
    cf.CFRelease.argtypes = [C.c_void_p]
    encoded = str(path).encode()
    url = cf.CFURLCreateFromFileSystemRepresentation(None, encoded, len(encoded), False)
    descs = ct.CTFontManagerCreateFontDescriptorsFromURL(url)
    assert descs and cf.CFArrayGetCount(descs) == 1
    desc = cf.CFArrayGetValueAtIndex(descs, 0)
    font = ct.CTFontCreateWithFontDescriptor(desc, 72, None)
    ps = ct.CTFontCopyPostScriptName(font)
    buffer = C.create_string_buffer(256)
    assert cf.CFStringGetCString(ps, buffer, len(buffer), 0x08000100)
    assert buffer.value == postscript_name.encode(), buffer.value
    text = "Vespera AMQR aergftij 0123456789 Éüñ"
    chars = (C.c_ushort * len(text))(*map(ord, text))
    glyphs = (C.c_ushort * len(text))()
    assert ct.CTFontGetGlyphsForCharacters(font, chars, glyphs, len(text))
    assert all(glyphs)
    if cell_advance is not None:
        class Size(C.Structure):
            _fields_ = [("width", C.c_double), ("height", C.c_double)]
        ct.CTFontGetSymbolicTraits.argtypes = [C.c_void_p]
        ct.CTFontGetSymbolicTraits.restype = C.c_uint32
        assert ct.CTFontGetSymbolicTraits(font) & (1 << 10), "CoreText must report monospaced."
        ct.CTFontGetAdvancesForGlyphs.argtypes = [C.c_void_p, C.c_uint32, C.POINTER(C.c_ushort), C.POINTER(Size), C.c_long]
        ct.CTFontGetAdvancesForGlyphs.restype = C.c_double
        advances = (Size * len(text))()
        ct.CTFontGetAdvancesForGlyphs(font, 0, glyphs, advances, len(text))
        assert all(abs(a.width - cell_advance * 72 / 1000) < 1e-6 for a in advances)
    for obj in (ps, font, descs, url): cf.CFRelease(obj)
    return ("PASS: macOS CoreText opens the font, reports the correct PostScript name and maps every probe character."
            + (" Its monospaced trait and native advances also match the cell width." if cell_advance is not None else ""))



def coretext_collection(path, postscript_names):
    """CoreText sees every member of a collection, under its own PostScript name."""
    cf = C.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    ct = C.CDLL("/System/Library/Frameworks/CoreText.framework/CoreText")
    cf.CFURLCreateFromFileSystemRepresentation.argtypes = [C.c_void_p, C.c_char_p, C.c_long, C.c_bool]
    cf.CFURLCreateFromFileSystemRepresentation.restype = C.c_void_p
    ct.CTFontManagerCreateFontDescriptorsFromURL.argtypes = [C.c_void_p]
    ct.CTFontManagerCreateFontDescriptorsFromURL.restype = C.c_void_p
    cf.CFArrayGetCount.argtypes = [C.c_void_p]; cf.CFArrayGetCount.restype = C.c_long
    cf.CFArrayGetValueAtIndex.argtypes = [C.c_void_p, C.c_long]; cf.CFArrayGetValueAtIndex.restype = C.c_void_p
    ct.CTFontCreateWithFontDescriptor.argtypes = [C.c_void_p, C.c_double, C.c_void_p]
    ct.CTFontCreateWithFontDescriptor.restype = C.c_void_p
    ct.CTFontCopyPostScriptName.argtypes = [C.c_void_p]; ct.CTFontCopyPostScriptName.restype = C.c_void_p
    cf.CFStringGetCString.argtypes = [C.c_void_p, C.c_void_p, C.c_long, C.c_uint32]
    cf.CFRelease.argtypes = [C.c_void_p]
    encoded = str(path).encode()
    url = cf.CFURLCreateFromFileSystemRepresentation(None, encoded, len(encoded), False)
    descs = ct.CTFontManagerCreateFontDescriptorsFromURL(url)
    assert descs and cf.CFArrayGetCount(descs) == len(postscript_names)
    found = set()
    for i in range(cf.CFArrayGetCount(descs)):
        font = ct.CTFontCreateWithFontDescriptor(cf.CFArrayGetValueAtIndex(descs, i), 12, None)
        ps = ct.CTFontCopyPostScriptName(font)
        buffer = C.create_string_buffer(256)
        assert cf.CFStringGetCString(ps, buffer, len(buffer), 0x08000100)
        found.add(buffer.value.decode())
        cf.CFRelease(ps); cf.CFRelease(font)
    cf.CFRelease(descs); cf.CFRelease(url)
    assert found == set(postscript_names), found
