"""Configuration selection and concise command-line output."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .config import load_config
from .pipeline import run

ROOT=Path(__file__).resolve().parents[1]


def main(argv=None):
    parser=argparse.ArgumentParser(description='Build or check both Vespera families from their original open source font.')
    parser.add_argument('command',choices=('build','check','spacing','source'),
                        help='build fonts, verify existing fonts against a clean rebuild, '
                             'store a font\'s spacing parameters, or convert a font to a text source (.txt) or UFO (.ufo) (--font, --output)')
    parser.add_argument('--config',action='append',type=Path,help='JSON configuration; repeat to select multiple families (default: both bundled profiles)')
    parser.add_argument('--font',type=Path,help='spacing / source: the font to read')
    parser.add_argument('--output',type=Path,help='spacing / source: the file to write')
    args=parser.parse_args(argv)
    if not __debug__:
        parser.error('Run without -O: font validation assertions must remain enabled')
    if args.command=='source':
        if not args.font or not args.output:
            parser.error('source needs --font and --output')
        from .source import convert, tree_digest
        count=convert(args.font,args.output)
        kind='UFO 3 source' if args.output.suffix=='.ufo' else 'text source'
        print(f'{args.output}: {kind} with {count} glyphs from {args.font.name}, read back exactly')
        print(f'  sha256: {tree_digest(args.output)}')
        return 0
    if args.command=='spacing':
        if not args.font or not args.output:
            parser.error('spacing needs --font and --output')
        from .spacing import write_spacing
        count=write_spacing(args.font,args.output)
        print(f'{args.output}: {count} glyphs, advances, ink boxes and kerning from {args.font.name}')
        return 0
    paths=args.config or [ROOT/'configs/display.json',ROOT/'configs/mono.json']
    try:
        configs=[load_config(path) for path in paths]
        reports=run(configs,check=args.command=='check')
    except (OSError,ValueError,AssertionError,KeyError) as error:
        print(f'ERROR: {error or type(error).__name__}',file=sys.stderr)
        return 1
    targets={(c.family,s.name):(c,s) for c in configs for s in c.styles}
    for report in reports:
        if report.get('collection'):
            config=next(c for c in configs if c.family==report['family'])
            print(f"PASS {report['family']} collection {report['version']}: {report['collection']} styles in one file, {report['bytes']:,} bytes")
            print('  Every member matches its standalone font and opens by index'
                  + ('; CoreText lists all members' if sys.platform=='darwin' else ''))
            print(f"  {config.collection_target}  sha256:{report['sha256']['otc']}")
            continue
        config,style=targets[(report['family'],report['style'])]
        print(f"PASS {report['family']} {report['style']} {report['version']}: {report['glyphs']} glyphs / {report['mapped_codepoints']} Unicode mappings / {report['spacing']}")
        if report['ascii_pairs']:
            print(f"  {report['ascii_pairs']:,} ASCII pairs retain literal glyphs and fixed columns")
        print('  Names, style flags, outlines, shaping, combining marks and native rasterization verified'
              + ('; CoreText verified' if report['coretext'] else ''))
        for extension,digest in report['sha256'].items():
            print(f'  {config.target(style,extension)}  sha256:{digest}')
    return 0
