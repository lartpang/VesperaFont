"""Fail unless the release tag (v0.0.1 or 0.0.1) matches every family's configured version."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from fontviber.config import load_config  # noqa: E402


def main(tag):
    wanted = tag[1:] if tag.startswith('v') else tag
    configs = [load_config(path) for path in sorted((ROOT / 'configs').glob('*.json'))]
    mismatched = [f'{c.family}: {c.version}' for c in configs if c.version != wanted]
    if mismatched:
        print(f'Release tag {tag} does not match configs/*.json versions: ' + ', '.join(mismatched), file=sys.stderr)
        return 1
    for c in configs:
        print(f'{c.family} {c.version} (OpenType {c.font_version})')
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('usage: release_version.py <tag>')
    sys.exit(main(sys.argv[1]))
