from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from . import topic_mgr
from .exporter import export_archive, load_all_sessions, load_template_config
from .ipc import State, serve
from .parser import parse_with_diff, write_sessions
from .render_md import render_all


def _load_sync_cfg(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _state_from_args(args: argparse.Namespace) -> State:
    cfg = _load_sync_cfg(Path(args.config)) if args.config else {}
    raw_dir = Path(args.raw_dir or cfg.get("rawDir"))
    sessions_dir = Path(args.sessions_dir or cfg.get("sessionsDir", "data/1-sessions"))
    turns_md_dir = Path(args.turns_md_dir or cfg.get("turnsMdDir", "data/2-turns_md"))
    topics_dir = Path(args.topics_dir or cfg.get("topicsDir", "data/3-topics"))
    exports_dir = Path(args.exports_dir or cfg.get("exportsDir", "data/4-exports"))
    gap = int(args.gap_seconds or cfg.get("sessionGapSeconds", 1800))
    sync_strategy = args.sync_strategy or cfg.get("syncStrategy", "archive")
    template_path = Path(args.template or "export_template.yaml")
    return State(
        raw_dir=raw_dir,
        sessions_dir=sessions_dir,
        turns_md_dir=turns_md_dir,
        topics_dir=topics_dir,
        exports_dir=exports_dir,
        gap_seconds=gap,
        sync_strategy=sync_strategy,
        template_path=template_path,
    )


def cmd_parse(args: argparse.Namespace) -> int:
    state = _state_from_args(args)
    archive = parse_with_diff(
        state.raw_dir,
        state.sessions_dir,
        state.gap_seconds,
        state.sync_strategy,
    )
    written = write_sessions(archive, state.sessions_dir)
    render_stats = render_all(state.sessions_dir, state.turns_md_dir, state.template_path)
    print(f"sessions: {len(archive.sessions)}", file=sys.stderr)
    print(f"turns:    {sum(s.turn_count for s in archive.sessions)}", file=sys.stderr)
    print(f"wrote:    {len(written)} files into {state.sessions_dir}", file=sys.stderr)
    print(f"rendered: {render_stats['rendered']} (skipped {render_stats['skipped']}) into {state.turns_md_dir}", file=sys.stderr)
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    state = _state_from_args(args)
    stats = render_all(state.sessions_dir, state.turns_md_dir, state.template_path)
    print(f"rendered: {stats['rendered']} (skipped {stats['skipped']}) across {stats['sessions']} sessions into {state.turns_md_dir}", file=sys.stderr)
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    state = _state_from_args(args)
    template_cfg = load_template_config(state.template_path)
    sessions = load_all_sessions(state.sessions_dir)
    topics = topic_mgr.load_topics(state.topics_dir)
    written = export_archive(
        sessions,
        template_cfg,
        state.exports_dir,
        state.turns_md_dir,
        only_session_ids=args.session_ids,
        topics=topics,
        only_topic_ids=args.topic_ids,
    )
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
    common.add_argument("--sessions-dir", dest="sessions_dir")
    common.add_argument("--turns-md-dir", dest="turns_md_dir")
    common.add_argument("--topics-dir", dest="topics_dir")
    common.add_argument("--exports-dir", dest="exports_dir")
    common.add_argument("--gap-seconds", dest="gap_seconds", type=int)
    common.add_argument("--sync-strategy", dest="sync_strategy", choices=["archive", "mirror"])
    common.add_argument("--template", default="export_template.yaml")

    p_parse = sub.add_parser("parse", parents=[common])
    p_parse.set_defaults(func=cmd_parse)

    p_render = sub.add_parser("render", parents=[common])
    p_render.set_defaults(func=cmd_render)

    p_export = sub.add_parser("export", parents=[common])
    p_export.add_argument("--session-ids", nargs="*")
    p_export.add_argument("--topic-ids", nargs="*")
    p_export.set_defaults(func=cmd_export)

    p_serve = sub.add_parser("serve", parents=[common])
    p_serve.set_defaults(func=cmd_serve)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
