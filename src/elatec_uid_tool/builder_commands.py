"""Headless build, preview and import of analyzer results into a firmware project."""
from pathlib import Path

from .builder import BuilderProject, preview, project_from_match, save_project
from .builder_firmware import build_project
from .fw_commands import _resolve_match
from .registration_commands import toolchain_from_args


def command_build_project(args) -> int:
    project = BuilderProject.from_json(Path(args.project).read_text(encoding="utf-8"))
    result = build_project(project, devpack=Path(args.devpack),
                           output_dir=Path(args.output_dir) if args.output_dir else None,
                           toolchain=toolchain_from_args(args))
    print(f"BIX: {result.bix_path}\nProjekt: {result.project_path}\nManifest: {result.manifest_path}\nZdroje: {result.source_zip}")
    return 0


def command_preview_project(args) -> int:
    import json
    from dataclasses import asdict
    project = BuilderProject.from_json(Path(args.project).read_text(encoding="utf-8"))
    print(json.dumps(asdict(preview(project, args.raw, args.band, args.bits)), ensure_ascii=False, indent=2))
    return 0


def command_project_from_match(args) -> int:
    match, tag_type = _resolve_match(args)
    project = project_from_match(match, tag_type=tag_type, channel=args.channel)
    path = save_project(Path(args.output), project)
    print(f"Projekt převodního pravidla: {path}")
    return 0
