from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, List, Optional

import yaml
from jinja2 import Environment, StrictUndefined

from .models import Session, Turn

_FORBIDDEN_FS = re.compile(r'[\\/:"*?<>|\x00-\x1f]+')
_DASHES = re.compile(r"-{2,}")


def _slugify(text: str, max_chars: int) -> str:
    text = text.strip().splitlines()[0] if text else "untitled"
    text = _FORBIDDEN_FS.sub("-", text)
    text = text.replace(" ", "-")
    text = _DASHES.sub("-", text).strip("-")
    if not text:
        text = "untitled"
    if len(text) > max_chars:
        text = text[:max_chars].rstrip("-")
    return text or "untitled"


def _prompt_preview(prompt: str, limit: int = 80) -> str:
    if not prompt:
        return "(no prompt)"
    first_line = prompt.strip().splitlines()[0]
    return first_line[:limit] + ("…" if len(first_line) > limit else "")


def load_template_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def render_session(session: Session, template_cfg: dict) -> str:
    env = Environment(undefined=StrictUndefined, autoescape=False)
    sep = template_cfg.get("turn_separator", "\n\n---\n\n")
    session_header_tpl = env.from_string(template_cfg.get("session_header", "# {{ title }}"))
    turn_header_tpl = env.from_string(template_cfg.get("turn_header", "## {{ timestamp }} — {{ prompt_preview }}"))
    prompt_block_tpl = env.from_string(template_cfg.get("prompt_block", "**Prompt:**\n\n{{ prompt }}"))
    response_block_tpl = env.from_string(template_cfg.get("response_block", "**Response:**\n\n{{ response_md }}"))

    out: List[str] = [session_header_tpl.render(title=session.title, id=session.id, start=session.start, end=session.end)]
    rendered_turns: List[str] = []
    for turn in session.turns:
        if not turn.visibility_flag:
            continue
        ctx = {
            "timestamp": turn.timestamp,
            "kind": turn.kind,
            "prompt": turn.prompt,
            "prompt_preview": _prompt_preview(turn.prompt),
            "response_md": turn.response_md,
            "id": turn.id,
        }
        parts: List[str] = [turn_header_tpl.render(**ctx)]
        if turn.prompt:
            parts.append(prompt_block_tpl.render(**ctx))
        if turn.response_md:
            parts.append(response_block_tpl.render(**ctx))
        if turn.attachments:
            parts.append(_render_attachments(turn))
        rendered_turns.append("\n\n".join(parts))
    if rendered_turns:
        out.append(sep.join(rendered_turns))
    return "\n\n".join(out).rstrip() + "\n"


def _render_attachments(turn: Turn) -> str:
    lines = ["**Attachments:**", ""]
    for a in turn.attachments:
        lines.append(f"- [{a}]({a})")
    return "\n".join(lines)


def export_session(session: Session, template_cfg: dict, exports_dir: Path) -> Path:
    exports_dir.mkdir(parents=True, exist_ok=True)
    pattern = template_cfg.get("filename_pattern", "{date}_{sid}_{slug}.md")
    slug_max = int(template_cfg.get("slug_max_chars", 40))
    date = session.start.split(" ", 1)[0]
    filename = pattern.format(date=date, sid=session.id, slug=_slugify(session.title, slug_max))
    path = exports_dir / filename
    path.write_text(render_session(session, template_cfg), encoding="utf-8")
    return path


def export_archive(
    sessions: Iterable[Session],
    template_cfg: dict,
    exports_dir: Path,
    only_ids: Optional[List[str]] = None,
) -> List[Path]:
    written: List[Path] = []
    for session in sessions:
        if only_ids is not None and session.id not in only_ids:
            continue
        written.append(export_session(session, template_cfg, exports_dir))
    return written


def load_session(processed_dir: Path, session_id: str) -> Session:
    path = processed_dir / f"session_{session_id}.json"
    return Session.model_validate_json(path.read_text(encoding="utf-8"))


def load_all_sessions(processed_dir: Path) -> List[Session]:
    if not processed_dir.exists():
        return []
    sessions: List[Session] = []
    for p in sorted(processed_dir.glob("session_*.json")):
        sessions.append(Session.model_validate_json(p.read_text(encoding="utf-8")))
    sessions.sort(key=lambda s: s.start)
    return sessions
