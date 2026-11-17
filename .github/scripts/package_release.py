"""Collect the built fonts into release assets: one zip, the two collections and checksums."""
from hashlib import sha256
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from fontviber.config import load_config  # noqa: E402

# A fixed timestamp keeps the archive identical for identical fonts.
STAMP = (2026, 1, 1, 0, 0, 0)


def add(archive, path, name):
    info = zipfile.ZipInfo(name, STAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, path.read_bytes())


def main(tag, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    version = tag[1:] if tag.startswith('v') else tag
    configs = [load_config(p) for p in sorted((ROOT / 'configs').glob('*.json'))]
    fonts = []
    for c in configs:
        fonts += [c.target(s, ext) for s in c.styles for ext in c.style_formats]
        if 'otc' in c.formats:
            fonts.append(c.collection_target)
    missing = [str(f) for f in fonts if not f.is_file()]
    if missing:
        sys.exit('Build the fonts first; missing: ' + ', '.join(missing))
    bundle = out / f'Vespera-{version}.zip'
    folder = f'Vespera-{version}'
    with zipfile.ZipFile(bundle, 'w') as archive:
        for font in sorted(fonts):
            sub = {'.otf': 'otf', '.woff2': 'woff2', '.otc': 'otc'}[font.suffix]
            add(archive, font, f'{folder}/{sub}/{font.name}')
        # The READMEs show the specimen images in docs/images, so they travel with them.
        docs = sorted(p.relative_to(ROOT).as_posix() for folder in ('docs/images', 'licenses')
                      for p in (ROOT / folder).iterdir() if p.name != '.DS_Store')
        for doc in ['README.md', 'README.zh-CN.md', 'MANIFEST-Vespera.txt', *docs]:
            add(archive, ROOT / doc, f'{folder}/{doc}')
    assets = [bundle]
    for c in configs:
        if 'otc' in c.formats:
            copy = out / f"{c.family.replace(' ', '')}-{version}.otc"
            copy.write_bytes(c.collection_target.read_bytes())
            assets.append(copy)
    sums = out / 'SHA256SUMS.txt'
    sums.write_text(''.join(f'{sha256(a.read_bytes()).hexdigest()}  {a.name}\n' for a in assets))
    for asset in assets + [sums]:
        print(f'{asset.name}  {asset.stat().st_size:,} bytes')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit('usage: package_release.py <tag> <output-directory>')
    main(*sys.argv[1:])
