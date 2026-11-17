"""Layout-table transforms shared by the configured exporter."""
from __future__ import annotations

import struct

P = struct.pack
U = struct.unpack_from

def layout_features(table, wanted):
    """Keep only requested features, retaining lookup indices used by contexts.

    Lookup offsets are relative to the LookupList or Lookup table; copying the
    entire original LookupList preserves contextual lookup references.

    Scripts and language systems keep their own feature sets, so language-specific
    features such as Romanian locl stay tied to their language. A language system
    left with no features is dropped (it then falls back to its script's default),
    and so is a script left with none.
    """
    sl, fl, ll = U('>HHH', table, 4)
    keep, kept = {}, []
    for i in range(U('>H', table, fl)[0]):
        tag, off = U('>4sH', table, fl + 2 + i * 6)
        if tag.decode() not in wanted:
            continue
        params, count = U('>HH', table, fl + off)
        assert params == 0, f'feature {tag.decode()} has parameters'
        keep[i] = len(keep)
        kept.append((tag, table[fl + off:fl + off + 4 + count * 2]))
    # Feature offsets are relative to the FeatureList: count, records, then bodies.
    features, at = P('>H', len(kept)), 2 + 6 * len(kept)
    for tag, body in kept:
        features += tag + P('>H', at)
        at += len(body)
    features += b''.join(body for _, body in kept)

    def langsys(p):
        required, count = U('>HH', table, p + 2)
        indices = [keep[i] for i in U(f'>{count}H', table, p + 6) if i in keep]
        if not indices and keep.get(required) is None:
            return None
        return P('>HHH', 0, keep.get(required, 0xFFFF), len(indices)) + P(f'>{len(indices)}H', *indices)

    scripts = []
    for i in range(U('>H', table, sl)[0]):
        tag, off = U('>4sH', table, sl + 2 + i * 6)
        s = sl + off
        default_off, count = U('>HH', table, s)
        default = langsys(s + default_off) if default_off else None
        langs = [(t, ls) for t, o in (U('>4sH', table, s + 4 + j * 6) for j in range(count))
                 if (ls := langsys(s + o)) is not None]
        if default is None and not langs:
            continue
        head = 4 + 6 * len(langs)
        body, recs = b'', b''
        if default is not None:
            body = default
        for t, ls in langs:
            recs += t + P('>H', head + len(body))
            body += ls
        scripts.append((tag, P('>HH', head if default is not None else 0, len(langs)) + recs + body))
    script_list, at = P('>H', len(scripts)), 2 + 6 * len(scripts)
    for tag, body in scripts:
        script_list += tag + P('>H', at)
        at += len(body)
    script_list += b''.join(body for _, body in scripts)
    return (P('>IHHH', 0x10000, 10, 10 + len(script_list), 10 + len(script_list) + len(features))
            + script_list + features + table[ll:])


def transform_anchors(table, glyphs):
    """Map every mark-attachment anchor through its glyph's affine outline transform.

    Each glyph carries anchor = (a, b, c): x' = a*x + b*y + c, built up as the
    outline is shifted, refitted, emboldened and slanted. Anchor tables shared by
    several glyphs must receive identical results.
    """
    b=bytearray(table)
    u=lambda p:U('>H',b,p)[0]
    def coverage(p):
        if u(p)==1:
            return list(U('>'+str(u(p+2))+'H',b,p+4))
        assert u(p)==2
        return [gid for i in range(u(p+2)) for gid in range(u(p+4+i*6),u(p+6+i*6)+1)]
    changes={}
    def record(p,gid):
        assert u(p)==1,'This source uses format-1 anchors.'
        x,y=U('>hh',b,p+2)
        a,k,c=glyphs[gid]['anchor']
        point=(round(a*x+k*y+c),y)
        if p in changes:
            assert abs(changes[p][0]-point[0])<=1,('Conflicting shared anchor',glyphs[gid]['name'])
        changes[p]=point
    ll=u(8)
    for i in range(u(ll)):
        look=ll+u(ll+2+2*i)
        if u(look) not in (4,6):
            continue
        for j in range(u(look+4)):
            sub=look+u(look+6+2*j)
            assert u(sub)==1
            marks,bases=coverage(sub+u(sub+2)),coverage(sub+u(sub+4))
            classes=u(sub+6)
            ma,ba=sub+u(sub+8),sub+u(sub+10)
            for k,gid in enumerate(marks):
                record(ma+u(ma+4+4*k),gid)
            for k,gid in enumerate(bases):
                for cls in range(classes):
                    off=u(ba+2+2*(k*classes+cls))
                    if off: record(ba+off,gid)
    for p,point in changes.items():
        b[p+2:p+6]=P('>hh',*point)
    return bytes(b)


def cmap_table(cmap):
    pairs=sorted((int(cp),gid) for cp,gid in cmap.items())
    bmp=[(cp,gid) for cp,gid in pairs if cp < 0xFFFF]+[(0xFFFF,0)]
    n=len(bmp);power=1<<(n.bit_length()-1)
    f4=P('>HHHHHHH',4,16+n*8,0,n*2,power*2,power.bit_length()-1,n*2-power*2)
    f4+=b''.join(P('>H',cp) for cp,_ in bmp)+P('>H',0)
    f4+=b''.join(P('>H',cp) for cp,_ in bmp)
    f4+=b''.join(P('>H',(gid-cp)&0xFFFF) for cp,gid in bmp)+b'\0\0'*n
    f12=P('>HHIII',12,0,16+len(pairs)*12,0,len(pairs))
    f12+=b''.join(P('>III',cp,cp,gid) for cp,gid in pairs)
    header=P('>HH',0,3)+P('>HHI',0,4,28+len(f4))+P('>HHI',3,1,28)+P('>HHI',3,10,28+len(f4))
    return header+f4+f12



# --- Kerning ported from a metrics font -------------------------------------

def _coverage(t, p):
    if U('>H', t, p)[0] == 1:
        n = U('>H', t, p + 2)[0]
        return list(U('>%dH' % n, t, p + 4))
    out = []
    for i in range(U('>H', t, p + 2)[0]):
        first, last, _ = U('>HHH', t, p + 4 + i * 6)
        out.extend(range(first, last + 1))
    return out


def _classes(t, p):
    if U('>H', t, p)[0] == 1:
        start, n = U('>HH', t, p + 2)
        return {start + i: c for i, c in enumerate(U('>%dH' % n, t, p + 6)) if c}
    out = {}
    for i in range(U('>H', t, p + 2)[0]):
        first, last, c = U('>HHH', t, p + 4 + i * 6)
        if c:
            out.update(dict.fromkeys(range(first, last + 1), c))
    return out


def read_kerning(gpos):
    """Pair-adjustment subtables of every 'kern' lookup, in source glyph ids.

    Returns [[('pairs', {first: {second: x_advance}}) | ('classes', coverage,
    class1, class2, counts, values)], ...], one list per lookup.
    """
    t = gpos
    fl, ll = U('>HH', t, 6)
    indices = []
    for i in range(U('>H', t, fl)[0]):
        tag, off = U('>4sH', t, fl + 2 + i * 6)
        if tag == b'kern':
            f = fl + off
            for j in range(U('>H', t, f + 2)[0]):
                index = U('>H', t, f + 4 + 2 * j)[0]
                if index not in indices:
                    indices.append(index)
    lookups = []
    for index in sorted(indices):
        look = ll + U('>H', t, ll + 2 + 2 * index)[0]
        kind, _, count = U('>HHH', t, look)
        subs = []
        for j in range(count):
            st = look + U('>H', t, look + 6 + 2 * j)[0]
            if kind == 9:
                assert U('>H', t, st + 2)[0] == 2
                st += U('>I', t, st + 4)[0]
            else:
                assert kind == 2
            fmt, cov, vf1, vf2 = U('>HHHH', t, st)
            assert (vf1, vf2) == (4, 0), 'only x-advance kerning is supported'
            firsts = _coverage(t, st + cov)
            if fmt == 1:
                pairs = {}
                for k, first in enumerate(firsts):
                    ps = st + U('>H', t, st + 10 + 2 * k)[0]
                    n = U('>H', t, ps)[0]
                    pairs[first] = {U('>H', t, ps + 2 + 4 * r)[0]: U('>h', t, ps + 4 + 4 * r)[0] for r in range(n)}
                subs.append(('pairs', pairs))
            else:
                cd1, cd2, n1, n2 = U('>HHHH', t, st + 8)
                values = list(U('>%dh' % (n1 * n2), t, st + 16))
                subs.append(('classes', firsts, _classes(t, st + cd1), _classes(t, st + cd2), (n1, n2), values))
        lookups.append(subs)
    return lookups


def remap_kerning(lookups, mapping):
    """Translate glyph ids with mapping {old: new}; pairs with unknown glyphs are dropped."""
    out = []
    for subs in lookups:
        mapped = []
        for sub in subs:
            if sub[0] == 'pairs':
                pairs = {}
                for first, row in sub[1].items():
                    if first in mapping:
                        new = {mapping[s]: v for s, v in row.items() if s in mapping}
                        if new:
                            pairs[mapping[first]] = new
                mapped.append(('pairs', pairs))
            else:
                _, cov, c1, c2, counts, values = sub
                mapped.append(('classes', sorted({mapping[g] for g in cov if g in mapping}),
                               {mapping[g]: c for g, c in c1.items() if g in mapping},
                               {mapping[g]: c for g, c in c2.items() if g in mapping}, counts, values))
        out.append(mapped)
    return out


def _coverage_bytes(gids):
    gids = sorted(gids)
    return P('>HH', 1, len(gids)) + b''.join(P('>H', g) for g in gids)


def _classdef_bytes(classes):
    ranges = []
    for g in sorted(classes):
        if ranges and ranges[-1][1] == g - 1 and ranges[-1][2] == classes[g]:
            ranges[-1][1] = g
        else:
            ranges.append([g, g, classes[g]])
    return P('>HH', 2, len(ranges)) + b''.join(P('>HHH', *r) for r in ranges)


def _pairpos_bytes(sub):
    if sub[0] == 'classes':
        _, cov, c1, c2, (n1, n2), values = sub
        body = P('>%dh' % len(values), *values)
        cov_b, c1_b, c2_b = _coverage_bytes(cov), _classdef_bytes(c1), _classdef_bytes(c2)
        at = 16 + len(body)
        head = P('>HHHHHHHH', 2, at, 4, 0, at + len(cov_b), at + len(cov_b) + len(c1_b), n1, n2)
        return [head + body + cov_b + c1_b + c2_b]
    # Format 1, split so every 16-bit offset stays in range.
    firsts = sorted(sub[1])
    chunks, current, size = [], [], 0
    for first in firsts:
        need = 4 + 2 + 4 * len(sub[1][first])
        if current and size + need > 60000:
            chunks.append(current)
            current, size = [], 0
        current.append(first)
        size += need
    if current:
        chunks.append(current)
    out = []
    for chunk in chunks:
        cov_b = _coverage_bytes(chunk)
        at = 10 + 2 * len(chunk)
        sets, offsets, pos = b'', [], at + len(cov_b)
        for first in chunk:
            row = sorted(sub[1][first].items())
            data = P('>H', len(row)) + b''.join(P('>Hh', s, v) for s, v in row)
            offsets.append(pos + len(sets))
            sets += data
        out.append(P('>HHHHH', 1, at, 4, 0, len(chunk)) + b''.join(P('>H', o) for o in offsets) + cov_b + sets)
    return out


def with_kerning(table, lookups):
    """Replace the 'kern' feature with the given lookups (wrapped as Extension
    lookups appended to the existing LookupList); other features keep their lookups."""
    fl, ll = U('>HH', table, 6)
    features = []
    for i in range(U('>H', table, fl)[0]):
        tag, off = U('>4sH', table, fl + 2 + i * 6)
        name = tag.decode()
        if name in ('kern', 'size') or any(name == f for f, _ in features):
            continue
        f = fl + off
        n = U('>H', table, f + 2)[0]
        features.append((name, list(U('>%dH' % n, table, f + 4))))
    old = table[ll:]
    n = U('>H', old, 0)[0]
    tables = [[b for sub in subs for b in _pairpos_bytes(sub)] for subs in lookups]
    k = len(tables)
    head = 2 + 2 * (n + k)
    block_sizes = [6 + 2 * len(t) + 8 * len(t) for t in tables]
    blocks_end = head + sum(block_sizes)
    body = old[2 + 2 * n:]
    delta = blocks_end - (2 + 2 * n)
    offsets = [U('>H', old, 2 + 2 * i)[0] + delta for i in range(n)]
    assert max(offsets) < 65536
    data_at = blocks_end + len(body)
    blocks, extra, pos = b'', b'', head
    for t, size in zip(tables, block_sizes):
        offsets.append(pos)
        look = P('>HHH', 9, 0, len(t)) + b''.join(P('>H', 6 + 2 * len(t) + 8 * j) for j in range(len(t)))
        for j, sub in enumerate(t):
            ext_at = pos + 6 + 2 * len(t) + 8 * j
            look += P('>HHI', 1, 2, data_at + len(extra) - ext_at)
            extra += sub
        blocks += look
        pos += size
    lookup_list = P('>H', n + k) + b''.join(P('>H', o) for o in offsets) + blocks + body + extra
    features.append(('kern', list(range(n, n + k))))
    features.sort(key=lambda f: f[0])
    records, bodies = b'', b''
    for tag, idx in features:
        records += tag.encode() + P('>H', 2 + 6 * len(features) + len(bodies))
        bodies += P('>HH', 0, len(idx)) + b''.join(P('>H', i) for i in idx)
    feature_list = P('>H', len(features)) + records + bodies
    lang = P('>HHH', 0, 0xFFFF, len(features)) + b''.join(P('>H', i) for i in range(len(features)))
    script = P('>HH', 4, 0) + lang
    scripts = P('>H', 2) + b'DFLT' + P('>H', 14) + b'latn' + P('>H', 14 + len(script)) + script + script
    return (P('>IHHH', 0x10000, 10, 10 + len(scripts), 10 + len(scripts) + len(feature_list))
            + scripts + feature_list + lookup_list)
