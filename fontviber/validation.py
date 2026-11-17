"""Shared binary, shaping and native raster checks; no persistent test artifacts."""
from __future__ import annotations

import ctypes as C
import hashlib
import struct
import sys
import unicodedata

from .coretext import coretext_check, coretext_collection
from .font_io import Face, bbox, checksum, collection_tables, contours, extract_font, freetype, map_path, sfnt_tables
from .glyphs import CONFUSABLE_TEXT, DIGITS
from .export import naming
from .metrics import CELL, ITALIC_ANGLE, ITALIC_SLOPE
from .shaping import Type


def canonical_path(path):
    """Ignore implicit closing lines and degenerate segments added/removed by FreeType."""
    result = []
    for contour in contours(path):
        start = tuple(contour[0][1:])
        current = start
        commands = [contour[0]]
        for cmd in contour[1:]:
            if cmd[0] == 'Z':
                continue
            points = [tuple(cmd[i:i+2]) for i in range(1,len(cmd),2)]
            if all(p == current for p in points):
                continue
            commands.append(cmd)
            current = points[-1]
        if commands[-1] == ['L', *start]:
            commands.pop()
        result += commands + [['Z']]
    return result


def _names(table):
    _,count,offset = struct.unpack_from('>HHH',table)
    result = {}
    for i in range(count):
        platform,encoding,language,key,length,start = struct.unpack_from('>HHHHHH',table,6+i*12)
        if (platform,encoding,language) == (3,1,0x409):
            result[key] = table[offset+start:offset+start+length].decode('utf-16-be')
    return result


def _native_check(otf, data, monospaced):
    ft = freetype()
    library = C.c_void_p()
    assert ft.FT_Init_FreeType(C.byref(library)) == 0
    face = C.POINTER(Face)()
    try:
        assert ft.FT_New_Face(library,str(otf).encode(),0,C.byref(face)) == 0
        assert bool(face.contents.face_flags & 4) == monospaced
        ft.FT_Outline_Check.argtypes = [C.c_void_p]
        for gid,g in enumerate(data['glyphs']):
            assert ft.FT_Load_Glyph(face,gid,11) == 0
            assert ft.FT_Outline_Check(C.byref(face.contents.glyph.contents.outline)) == 0,g['name']
            if monospaced and g['advance'] and g['path']:
                x0,_,x1,_ = bbox(g['path'])
                assert 0 <= x0 <= x1 <= CELL,(g['name'],x0,x1)
        ft.FT_Set_Pixel_Sizes.argtypes = [C.POINTER(Face),C.c_uint,C.c_uint]
        ft.FT_Render_Glyph.argtypes = [C.c_void_p,C.c_int]
        sizes = (12,14,16,18,20,24) if monospaced else (24,36,48,72)
        for size in sizes:
            assert ft.FT_Set_Pixel_Sizes(face,0,size) == 0
            for cp in range(33,127):
                gid = data['cmap'][str(cp)]
                assert ft.FT_Load_Glyph(face,gid,0) == 0
                assert ft.FT_Render_Glyph(face.contents.glyph,0) == 0
                bitmap = face.contents.glyph.contents.bitmap
                assert bitmap.width and bitmap.rows and bitmap.pixel_mode == 2,(size,chr(cp))
                assert any(C.string_at(bitmap.buffer,abs(bitmap.pitch)*bitmap.rows)),(size,chr(cp))
        return list(sizes)
    finally:
        if face:
            ft.FT_Done_Face(face)
        ft.FT_Done_FreeType(library)


def _marks_follow_letters(typ, data, italic):
    """Marks centred in the source stay centred over the ink, along the slant in italics."""
    # Italic capitals A, M, N carry swash feet, so their ink is no longer centred.
    texts = (('H\u0330', 'H\u0306', 'X\u0323', 'x\u0306', 'x\u0330') if italic else
             ('M\u0302', 'M\u0330', 'X\u0306', 'X\u0323', 'x\u0306', 'x\u0330'))
    for text in texts:
        sh, _ = typ.shape(text)
        assert len(sh) == 2 and all(gid for gid, _, _ in sh), text
        (base, bx, _), (mark, mx, my) = sh
        b, m = bbox(data['glyphs'][base]['path']), bbox(data['glyphs'][mark]['path'])
        base_x, base_y = bx + (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        mark_x, mark_y = mx + (m[0] + m[2]) / 2, my + (m[1] + m[3]) / 2
        expected = base_x + (ITALIC_SLOPE * (mark_y - base_y) if italic else 0)
        assert abs(mark_x - expected) < 40, (text, mark_x, expected)


def _display_checks(typ, data, italic):
    assert typ.shape('AV')[1] < typ.shape('A')[1]+typ.shape('V')[1]
    for text in ('fi','fl','ffi','ffl'):
        sh,_ = typ.shape(text)
        assert len(sh)<len(text) and all(gid for gid,_,_ in sh),text
    byname = typ.byname
    figure=byname['zero']['advance']
    assert all(byname[d]['advance']==figure for d in DIGITS)
    assert typ.shape('0123456789')[1] == 10*figure
    assert len(contours(byname['zero']['path']))==3 and len(contours(byname['O']['path']))==2
    if not italic:  # the barred 7 belongs to the roman; the italic keeps its cursive 7
        assert len(contours(byname['seven']['path']))==2
    # Slash widths follow the reference fonts (Pagella X Bold sets / at 296, \\ at 606).
    pairs=[('parenleft','parenright'),('bracketleft','bracketright'),('braceleft','braceright'),('less','greater')]
    for left,right in pairs:
        assert byname[left]['advance']==byname[right]['advance'],left
    for name in ('exclam','question'):
        cc=contours(byname[name]['path'])
        assert len(cc)==2
        assert max(bbox(c)[3]-bbox(c)[1] for c in cc)>450
        assert min(bbox(c)[3]-bbox(c)[1] for c in cc)<150


def _mono_checks(typ, data, tables, italic):
    assert {g['advance'] for g in data['glyphs']} == {0,CELL}
    assert struct.unpack_from('>I',tables['post'],12)[0]==1
    assert tables['OS/2'][35]==9
    assert struct.unpack_from('>h',tables['OS/2'],2)[0]==CELL
    assert struct.unpack_from('>H',tables['hhea'],10)[0]==CELL
    characters=''.join(chr(cp) for cp in range(32,127))
    for a in characters:
        for b in characters:
            sh,width=typ.shape(a+b)
            assert width==2*CELL and len(sh)==2,(a,b,sh,width)
            assert [g for g,_,_ in sh]==[data['cmap'][str(ord(a))],data['cmap'][str(ord(b))]],(a,b)
            assert sh[0][1:]==(0,0) and sh[1][1:]==(CELL,0),(a,b)
    for text in ('fi fl ffi ffl office affine','!= == === => -> <= >= && || /* */',
                 'MWmw iljfrt AV To','┌─┬┐ │▒█│ └─┴┘'):
        sh,width=typ.shape(text)
        assert len(sh)==len(text) and width==len(text)*CELL and all(g for g,_,_ in sh),text
    for text in ('H\u030B','x\u0301','i\u030B','M\u0308','n\u0323','a\u0302\u0301'):
        sh,width=typ.shape(text)
        assert width==CELL and all(g for g,_,_ in sh),(text,width)
        for gid,dx,_ in sh:
            x0,_,x1,_=bbox(data['glyphs'][gid]['path'])
            # Italic accents lean with the letter and may overhang like italic serifs.
            slack=64 if italic else 32
            assert -slack<=dx+x0 and dx+x1<=CELL+slack,(text,dx+x0,dx+x1)
        if len(sh)>1:
            assert abs(sh[-1][1]-CELL)>8,text
    for cp,gid in data['cmap'].items():
        if unicodedata.category(chr(int(cp))) in ('Mn','Me','Cf'):
            assert data['glyphs'][gid]['advance']==0
    assert bbox(data['glyphs'][data['cmap']['95']]['path'])[0::2]==(0,CELL)
    assert all(str(cp) in data['cmap'] for cp in range(0x2580,0x25A0))


def validate(otf, files, expected, source, config, style):
    tables=sfnt_tables(otf)
    assert checksum(otf.read_bytes())==0xB1B0AFBA,'OpenType checksum'
    names=_names(tables['name'])
    wanted=naming(config,style)
    assert (names[1],names[2],names[4],names[6])==(wanted['legacy_family'],wanted['legacy_style'],wanted['full'],wanted['postscript'])
    assert (names[16],names[17])==(config.family,style.name)
    assert names[5].split(';')[0]=='Version '+config.font_version and config.version in names[5]
    assert struct.unpack_from('>I',tables['head'],4)[0]==round(float(config.font_version)*65536)
    assert struct.unpack_from('>H',tables['OS/2'],4)[0]==style.weight_class
    selection=struct.unpack_from('>H',tables['OS/2'],62)[0]
    assert bool(selection&1)==style.italic and bool(selection&32)==style.bold
    assert bool(selection&64)==(style.ribbi=='Regular')
    assert struct.unpack_from('>H',tables['head'],44)[0]==(style.bold|style.italic<<1)
    assert struct.unpack_from('>i',tables['post'],4)[0]==(-ITALIC_ANGLE*65536 if style.italic else 0)
    # Validate the intermediate OTF even when the requested deliverable is WOFF2 only.
    for extension,path in {'otf':otf,**files}.items():
        loaded=extract_font(path)
        assert loaded['family'] in (config.family,wanted['legacy_family']) and loaded['upem']==1000
        assert loaded['cmap']==expected['cmap'] and len(loaded['glyphs'])==len(expected['glyphs'])
        for actual,want in zip(loaded['glyphs'],expected['glyphs']):
            assert actual['name']==want['name'] and actual['advance']==want['advance'],want['name']
            assert canonical_path(actual['path'])==canonical_path(want['path']),(extension,want['name'])
        if extension=='woff2':
            assert struct.unpack_from('>HH',path.read_bytes(),24)==tuple(map(int,config.font_version.split('.')))
    actual=extract_font(otf)
    assert all(str(cp) in actual['cmap'] for cp in range(32,127))
    sizes=_native_check(otf,actual,config.monospaced)
    with Type(otf,actual) as typ:
        for text in ('Élégance Über façade','São Tomé Ångström piñata','€ £ ¥ $ @ &',CONFUSABLE_TEXT):
            assert all(gid for gid,_,_ in typ.shape(text)[0]),text
        literal,_=typ.shape(CONFUSABLE_TEXT)
        assert [g for g,_,_ in literal]==[actual['cmap'][str(ord(ch))] for ch in CONFUSABLE_TEXT]
        _marks_follow_letters(typ,actual,style.italic)
        if config.monospaced:
            _mono_checks(typ,actual,tables,style.italic)
        else:
            _display_checks(typ,actual,style.italic)
    if sys.platform=='darwin':
        coretext_check(otf,config.postscript(style),CELL if config.monospaced else None)
    return {'family':config.family,'style':style.name,'version':config.version,'spacing':config.spacing,
            'glyphs':len(actual['glyphs']),'mapped_codepoints':len(actual['cmap']),
            'ascii_pairs':9025 if config.monospaced else None,'raster_sizes':sizes,
            'coretext':sys.platform=='darwin',
            'sha256':{ext:hashlib.sha256(path.read_bytes()).hexdigest() for ext,path in files.items()}}


def validate_collection(path, otfs, config):
    """Every member equals its standalone font table for table, and opens by index."""
    members = collection_tables(path)
    assert len(members) == len(otfs) == len(config.styles)
    for i, (tables, otf, style) in enumerate(zip(members, otfs, config.styles)):
        assert tables == sfnt_tables(otf), (style.name, 'tables differ from the standalone font')
        member, single = extract_font(path, index=i), extract_font(otf)
        assert member['cmap'] == single['cmap'] and len(member['glyphs']) == len(single['glyphs'])
        assert [g['advance'] for g in member['glyphs']] == [g['advance'] for g in single['glyphs']]
        assert _names(tables['name'])[6] == config.postscript(style)
    if sys.platform == 'darwin':
        coretext_collection(path, [config.postscript(s) for s in config.styles])
    return {'family': config.family, 'style': 'collection', 'version': config.version,
            'collection': len(members), 'bytes': path.stat().st_size,
            'sha256': {'otc': hashlib.sha256(path.read_bytes()).hexdigest()}}
