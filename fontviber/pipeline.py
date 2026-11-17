"""Build, validate and publish from the original source in one temporary workspace."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile

from .design import build_design
from .export import export_font
from .font_io import make_collection, woff2_from_otf
from .spacing import load_spacing
from .source import load_source, tree_digest
from .mono import adapt_monospace
from .styles import display_style
from .validation import validate, validate_collection


def prepare(config, workdir):
    """Build and validate every configured style; returns {style: {extension: path}}."""
    # Sources are text files (fontviber/source.py); UFO directories and OTF files also work.
    if tree_digest(config.source)!=config.source_sha256:
        raise ValueError(f'{config.source.name}: source SHA-256 does not match configuration')
    source=load_source(config.source)
    if source['upem']!=1000:
        raise ValueError('The Vespera drawing master requires a 1000-unit Pagella source')
    def pinned(path,digest,kind):
        if tree_digest(path)!=digest:
            raise ValueError(f'{path.name}: {kind} SHA-256 does not match configuration')
        return path
    font=lambda path,digest,kind:load_source(pinned(path,digest,kind))
    # Spacing references are stored parameters (see fontviber/spacing.py), not fonts.
    spacing=lambda path,digest,kind:load_spacing(pinned(path,digest,kind))
    metrics=spacing(config.metrics,config.metrics_sha256,'metrics') if config.metrics else None
    italic_metrics=(spacing(config.italic_metrics,config.italic_metrics_sha256,'italic metrics')
                    if config.italic_metrics else None)
    # Drawn bold references: Bold uses Pagella X Bold's spacing, measured against Pagella X.
    weights={}
    if config.bold_metrics and metrics:
        weights[(True,False)]=(metrics,spacing(config.bold_metrics,config.bold_metrics_sha256,'bold metrics'))
    if config.bold_italic_metrics and italic_metrics:
        weights[(True,True)]=(italic_metrics,spacing(config.bold_italic_metrics,config.bold_italic_metrics_sha256,'bold italic metrics'))
    masters={}
    built={};reports=[]
    for style in config.styles:
        if style.italic not in masters:
            if style.italic and config.italic_source:
                # A true italic: its own outlines, layout tables and (optionally) spacing.
                italic=font(config.italic_source,config.italic_source_sha256,'italic source')
                master=build_design(italic,True,italic_metrics,cursive=True)
                master['base_tables']=italic['tables']
            else:
                master=build_design(source,style.italic,metrics)
                master['base_tables']=source['tables']
            masters[style.italic]=master
        if config.monospaced:
            data=adapt_monospace(masters[style.italic],config,style,workdir)
        else:
            data=display_style(masters[style.italic],config,style,workdir,weights.get((style.bold,style.italic)))
        otf=workdir/f'{config.postscript(style)}.otf'
        export_font(data,otf,config,style)
        files={}
        for extension in config.style_formats:
            path=workdir/f'{config.postscript(style)}.{extension}'
            if extension=='woff2':
                woff2_from_otf(otf,path,config.font_version)
            files[extension]=path
        reports.append(validate(otf,files,data,source,config,style))
        built[style]=files
    collection=None
    if 'otc' in config.formats:
        collection=workdir/config.collection_target.name
        otfs=[workdir/f'{config.postscript(s)}.otf' for s in config.styles]
        make_collection(otfs,collection)
        reports.append(validate_collection(collection,otfs,config))
    return built,reports,collection


def _publish(files):
    """Stage files next to their destinations, then replace with rollback on failure."""
    pending=[]
    replaced=[]
    try:
        for target,source in files:
            target.parent.mkdir(parents=True,exist_ok=True)
            previous=target.read_bytes() if target.exists() else None
            with tempfile.NamedTemporaryFile(prefix='.fontviber-',suffix='.tmp',dir=target.parent,delete=False) as handle:
                temporary=Path(handle.name)
                pending.append((target,temporary,previous))
                handle.write(source.read_bytes())
            os.chmod(temporary,0o644)
        for target,temporary,previous in pending:
            os.replace(temporary,target)
            replaced.append((target,previous))
    except BaseException:
        for target,previous in reversed(replaced):
            if previous is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(previous)
        raise
    finally:
        for _,temporary,_ in pending:
            temporary.unlink(missing_ok=True)


def run(configs, check=False):
    if not configs:
        raise ValueError('Select at least one configuration')
    destinations=set()
    for config in configs:
        targets=[config.target(style,extension) for style in config.styles for extension in config.style_formats]
        if 'otc' in config.formats:
            targets.append(config.collection_target)
        for path in targets:
            target=str(path).casefold()
            if target in destinations:
                raise ValueError(f'Configurations would overwrite the same font: {path}')
            destinations.add(target)
    results=[];publish=[]
    with tempfile.TemporaryDirectory(prefix='fontviber-') as temporary:
        for i,config in enumerate(configs):
            workdir=Path(temporary)/str(i)
            workdir.mkdir()
            built,reports,collection=prepare(config,workdir)
            outputs=[(config.target(style,extension),path) for style,files in built.items() for extension,path in files.items()]
            if collection:
                outputs.append((config.collection_target,collection))
            for target,path in outputs:
                if check:
                    if not target.is_file() or target.read_bytes()!=path.read_bytes():
                        raise ValueError(f'{target}: missing or different from a clean rebuild')
                else:
                    publish.append((target,path))
            results.extend(reports)
        if not check:
            _publish(publish)
    return results
