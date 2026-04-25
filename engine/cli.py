from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .exporter import export_archive, load_all_sessions, load_template_config
from .ipc import State, serve
from .parser import merge_visibility, parse_archive, write_processed


def _load_sync_cfg(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _state_from_args(args: argparse.Namespace) -> State:
    cfg = _load_sync_cfg(Path(args.config)) if args.config else {}
    raw_dir = Path(args.raw_dir or cfg.get("raw_dir"))
    processed_dir = Path(args.processed_dir or cfg.get("processed_dir", "warehouse/processed"))
    exports_dir = Path(args.exports_dir or cfg.get("exports_dir", "exports"))
    gap = int(args.gap_seconds or cfg.get("session_gap_seconds", 1800))
    template_path = Path(args.template or "export_template.yaml")
    return State(raw_dir=raw_dir, processed_dir=processed_dir, exports_dir=exports_dir, gap_seconds=gap, template_path=template_path)


def cmd_parse(args: argparse.Namespace) -> int:
    state = _state_from_args(args)
    archive = parse_archive(state.raw_dir, state.gap_seconds)
    merge_visibility(archive, state.processed_dir)
    written = write_processed(archive, state.processed_dir)
    print(f"sessions: {len(archive.sessions)}", file=sys.stderr)
    print(f"turns:    {sum(s.turn_count for s in archive.sessions)}", file=sys.stderr)
    print(f"wrote:    {len(written)} files into {state.processed_dir}", file=sys.stderr)
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    state = _state_from_args(args)
    template_cfg = load_template_config(state.template_path)
    sessions = load_all_sessions(state.processed_dir)
    written = export_archive(sessions, template_cfg, state.exports_dir, only_ids=args.session_ids)
    print(f"exported: {len(written)} files into {state.exports_dir}", file=sys.stderr)
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    state = _state_from_args(args)
    serve(state)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="engine.cli")
    sub = p.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", default="sync_config.yaml")
    common.add_argument("--raw-dir", dest="raw_dir")
    common.add_argument("--processed-dir", dest="processed_dir")
    common.add_argument("--exports-dir", dest="exports_dir")
    common.add_argument("--gap-seconds", dest="gap_seconds", type=int)
    common.add_argument("--template", default="export_template.yaml")

    p_parse = sub.add_parser("parse", parents=[common])
    p_parse.set_defaults(func=cmd_parse)

    p_export = sub.add_parser("export", parents=[common])
    p_export.add_argument("--session-ids", nargs="*")
    p_export.set_defaults(func=cmd_export)

    p_serve = sub.add_parser("serve", parents=[common])
    p_serve.set_defaults(func=cmd_serve)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
