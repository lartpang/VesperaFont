"""Strict, portable configuration; paths are relative to the configuration file."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re


@dataclass(frozen=True)
class Style:
    """One member of a family: a weight and an upright or italic slope."""
    name: str
    weight: str
    weight_class: int
    italic: bool

    @property
    def suffix(self):
        return self.name.replace(' ', '')

    @property
    def bold(self):
        return self.weight == 'Bold'

    @property
    def ribbi(self):
        """Legacy four-member style name used inside each style-linked group."""
        return {(False, False): 'Regular', (False, True): 'Italic',
                (True, False): 'Bold', (True, True): 'Bold Italic'}[(self.bold, self.italic)]


STYLES = {s.name: s for s in (
    Style('Light', 'Light', 300, False), Style('Light Italic', 'Light', 300, True),
    Style('Regular', 'Regular', 400, False), Style('Italic', 'Regular', 400, True),
    Style('Bold', 'Bold', 700, False), Style('Bold Italic', 'Bold', 700, True),
)}


@dataclass(frozen=True)
class FontConfig:
    path: Path
    source: Path
    source_sha256: str
    family: str
    version: str
    spacing: str
    styles: tuple[Style, ...]
    formats: tuple[str, ...]
    output_dir: Path
    metrics: Path | None = None
    metrics_sha256: str | None = None
    italic_source: Path | None = None
    italic_source_sha256: str | None = None
    italic_metrics: Path | None = None
    italic_metrics_sha256: str | None = None
    bold_metrics: Path | None = None
    bold_metrics_sha256: str | None = None
    bold_italic_metrics: Path | None = None
    bold_italic_metrics_sha256: str | None = None

    @property
    def monospaced(self):
        return self.spacing == 'monospace'

    def postscript(self, style):
        return self.family.replace(' ', '') + '-' + style.suffix

    def legacy_family(self, style):
        """Light is its own style-linked group, so RIBBI-only applications list it."""
        return self.family if style.weight in ('Regular', 'Bold') else f'{self.family} {style.weight}'

    @property
    def description(self):
        if self.monospaced:
            return ('Monospaced companion to Vespera Display: the same letters, wedge serifs, '
                    'lozenge dots and source punctuation, refitted to a 640-unit cell. '
                    'No automatic code ligatures or kerning. Unhinted; see README.md.')
        return ('Display Roman and Italic with extended wedge serifs, lozenge dots and '
                'calligraphic terminals; high-contrast optical size with a tight fit for '
                'headlines, branding and posters. Unhinted outlines; see README.md.')

    def target(self, style, extension):
        return self.output_dir / f'{self.postscript(style)}.{extension}'

    @property
    def font_version(self):
        """OpenType's X.YYY revision: release 1.2.3 becomes 1.203, 0.0.1 becomes 0.001."""
        parts = self.version.split('.')
        if len(parts) == 2:
            return self.version
        major, minor, patch = parts
        return f'{int(major)}.{int(minor)}{int(patch):02d}'

    @property
    def style_formats(self):
        """Formats written once per style; 'otc' is one collection per family."""
        return tuple(f for f in self.formats if f != 'otc')

    @property
    def collection_target(self):
        return self.output_dir / f"{self.family.replace(' ', '')}.otc"


def load_config(path):
    path = Path(path).resolve()
    values = json.loads(path.read_text(encoding='utf-8'))
    required = {'schema_version', 'source', 'source_sha256', 'family', 'version',
                'spacing', 'styles', 'formats', 'output_dir'}
    # Optional fonts, each a (path, digest) pair: spacing for the roman, outlines
    # for a true italic, and spacing for that italic.
    pairs = {'metrics': ('metrics_source', 'metrics_sha256'),
             'italic_source': ('italic_source', 'italic_source_sha256'),
             'italic_metrics': ('italic_metrics_source', 'italic_metrics_sha256'),
             'bold_metrics': ('bold_metrics_source', 'bold_metrics_sha256'),
             'bold_italic_metrics': ('bold_italic_metrics_source', 'bold_italic_metrics_sha256')}
    optional = {k for pair in pairs.values() for k in pair}
    actual = set(values) if isinstance(values, dict) else set()
    if not isinstance(values, dict) or not required <= actual or actual - required - optional:
        raise ValueError(f'{path.name}: missing keys {sorted(required-actual)}; unknown keys {sorted(actual-required-optional)}')
    for a, b in pairs.values():
        if (a in actual) != (b in actual):
            raise ValueError(f'{a} and {b} must be given together')
    if ('italic_metrics_source' in actual) and ('italic_source' not in actual):
        raise ValueError('italic_metrics_source needs italic_source')
    if type(values['schema_version']) is not int or values['schema_version'] != 2:
        raise ValueError('schema_version must be 2')
    for key in required - {'schema_version', 'formats', 'styles'}:
        if not isinstance(values[key], str) or not values[key].strip():
            raise ValueError(f'{key} must be a non-empty string')
    family = values['family']
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9 -]*', family) or family != family.strip():
        raise ValueError('family must be an ASCII font name containing letters, digits, spaces or hyphens')
    if len(family.replace(' ', '') + '-LightItalic') > 63:
        raise ValueError('PostScript names must be at most 63 characters')
    if not (re.fullmatch(r'\d{1,3}\.\d{3}', values['version'])
            or re.fullmatch(r'\d{1,3}\.\d\.\d{1,2}', values['version'])):
        raise ValueError('version must be a release version such as 0.0.1 (minor 0-9, patch 0-99) '
                         'or an OpenType version such as 1.200')
    if not re.fullmatch(r'[0-9a-f]{64}', values['source_sha256']):
        raise ValueError('source_sha256 must be a lowercase SHA-256 digest')
    if values['spacing'] not in {'proportional', 'monospace'}:
        raise ValueError('spacing must be proportional or monospace')
    styles = values['styles']
    if (not isinstance(styles, list) or not styles or any(not isinstance(s, str) or s not in STYLES for s in styles)
            or len(styles) != len(set(styles))):
        raise ValueError(f'styles must be a non-empty list of distinct names from {list(STYLES)}')
    formats = values['formats']
    if not isinstance(formats, list) or not formats or any(f not in ('otf', 'woff2', 'otc') for f in formats):
        raise ValueError('formats must be a non-empty list of otf, woff2 and/or otc')
    if len(formats) != len(set(formats)):
        raise ValueError('formats must not contain duplicates')
    source = (path.parent / values['source']).resolve()
    if not (source.is_file() or (source.is_dir() and (source / 'metainfo.plist').is_file())):
        raise ValueError(f'source font (text source, UFO directory or OTF file) is missing: {source}')
    output = (path.parent / values['output_dir']).resolve()
    if output == source.parent or output == path.parent:
        raise ValueError('output_dir must be separate from source and configuration directories')
    extra = {}
    for field, (key, sha) in pairs.items():
        if key not in values:
            continue
        if not isinstance(values[key], str) or not values[key].strip():
            raise ValueError(f'{key} must be a non-empty string')
        if not isinstance(values[sha], str) or not re.fullmatch(r'[0-9a-f]{64}', values[sha]):
            raise ValueError(f'{sha} must be a lowercase SHA-256 digest')
        font = (path.parent / values[key]).resolve()
        if not (font.is_file() or (font.is_dir() and (font / 'metainfo.plist').is_file())):
            raise ValueError(f'{key} font is missing: {font}')
        extra[field] = font
        extra[field + '_sha256' if field != 'metrics' else 'metrics_sha256'] = values[sha]
    ordered = tuple(s for s in STYLES.values() if s.name in styles)
    config = FontConfig(path, source, values['source_sha256'], family, values['version'],
                        values['spacing'], ordered, tuple(formats), output, **extra)
    if (any(config.target(s, ext).resolve() == source for s in ordered for ext in config.style_formats)
            or ('otc' in formats and config.collection_target.resolve() == source)):
        raise ValueError('output must not overwrite the source font')
    return config
