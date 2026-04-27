from __future__ import annotations

from pathlib import Path
from typing import List

import yaml
from jinja2 import Environment, StrictUndefined

from .html_to_md import html_to_markdown
from .models import Session, Turn


def _prompt_preview(prompt: str, limit: int = 80) -> str:
    if not prompt:
        return "(no prompt)"
    first_line = prompt.strip().splitlines()[0]
    return first_line[:limit] + ("…" if len(first_line) > limit else "")


def _render_attachments(turn: Turn) -> str:
    if not turn.attachments:
        return ""
    lines = ["**Attachments:**", ""]
    for a in turn.attachments:
        lines.append(f"- [{a}]({a})")
    return "\n".join(lines)


def render_turn(turn: Turn, template_cfg: dict, env: Environment) -> str:
    turn_header_tpl = env.from_string(template_cfg.get("turn_header", "## {{ timestamp }} — {{ prompt_preview }}"))
    prompt_block_tpl = env.from_string(template_cfg.get("prompt_block", "**Prompt:**\n\n{{ prompt }}"))
    response_block_tpl = env.from_string(template_cfg.get("response_block", "**Response:**\n\n{{ response_md }}"))
    response_md = html_to_markdown(turn.response) if turn.response else ""
    ctx = {
        "timestamp": turn.timestamp,
        "kind": turn.kind,
        "prompt": turn.prompt,
        "prompt_preview": _prompt_preview(turn.prompt),
        "response_md": response_md,
        "turnId": turn.turn_id,
    }
    parts: List[str] = [turn_header_tpl.render(**ctx)]
    if turn.prompt:
        parts.append(prompt_block_tpl.render(**ctx))
    if response_md:
        parts.append(response_block_tpl.render(**ctx))
    if turn.attachments:
        parts.append(_render_attachments(turn))
    return "\n\n".join(parts).rstrip() + "\n"


def _load_session(p: Path) -> Session:
    return Session.model_validate_json(p.read_text(encoding="utf-8"))


def _load_template(template_path: Path) -> dict:
    return yaml.safe_load(template_path.read_text(encoding="utf-8")) or {}


def render_all(sessions_dir: Path, turns_md_dir: Path, template_path: Path) -> dict:
    """Render any per-Turn MD files that don't already exist on disk.

    Idempotent and incremental: turn_id + content are immutable per parse, so
    presence of `<turns_md_dir>/<turn_id>.md` is sufficient to skip.
    """
    turns_md_dir.mkdir(parents=True, exist_ok=True)
    if not sessions_dir.exists():
        return {"rendered": 0, "skipped": 0, "sessions": 0}
    template_cfg = _load_template(template_path)
    env = Environment(undefined=StrictUndefined, autoescape=False)
    rendered = 0
    skipped = 0
    sessions = 0
    for session_path in sorted(sessions_dir.glob("session_*.json")):
        session = _load_session(session_path)
        sessions += 1
        for turn in session.turns:
            md_path = turns_md_dir / f"{turn.turn_id}.md"
            if md_path.exists():
                skipped += 1
                continue
            md_path.write_text(render_turn(turn, template_cfg, env), encoding="utf-8")
            rendered += 1
    return {"rendered": rendered, "skipped": skipped, "sessions": sessions}
