from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Optional

import yaml
from jinja2 import Environment, StrictUndefined

from .models import Session

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


def load_template_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def render_session(session: Session, template_cfg: dict, turns_md_dir: Path) -> str:
    env = Environment(undefined=StrictUndefined, autoescape=False)
    sep = template_cfg.get("turn_separator", "\n\n---\n\n")
    session_header_tpl = env.from_string(template_cfg.get("session_header", "# {{ title }}"))

    header = session_header_tpl.render(
        title=session.title,
        session_id=session.session_id,
        start_time=session.start_time,
        last_active_time=session.last_active_time,
    )

    rendered_turns: List[str] = []
    for turn in session.turns:
        if not turn.visibility_flag:
            continue
        md_path = turns_md_dir / f"{turn.turn_id}.md"
        if not md_path.exists():
            continue
        rendered_turns.append(md_path.read_text(encoding="utf-8").rstrip())

    body = sep.join(rendered_turns)
    return (header + "\n\n" + body).rstrip() + "\n"


def export_session(session: Session, template_cfg: dict, exports_dir: Path, turns_md_dir: Path) -> Path:
    exports_dir.mkdir(parents=True, exist_ok=True)
    pattern = template_cfg.get("filename_pattern", "{date}_{sid}_{slug}.md")
    slug_max = int(template_cfg.get("slug_max_chars", 40))
    date = session.start_time.split(" ", 1)[0]
    filename = pattern.format(date=date, sid=session.session_id, slug=_slugify(session.title, slug_max))
    path = exports_dir / filename
    path.write_text(render_session(session, template_cfg, turns_md_dir), encoding="utf-8")
    return path


def export_archive(
    sessions: Iterable[Session],
    template_cfg: dict,
    exports_dir: Path,
    turns_md_dir: Path,
    only_ids: Optional[List[str]] = None,
) -> List[Path]:
    written: List[Path] = []
    for session in sessions:
        if only_ids is not None and session.session_id not in only_ids:
            continue
        if not any(t.visibility_flag for t in session.turns):
            continue
        written.append(export_session(session, template_cfg, exports_dir, turns_md_dir))
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
    sessions.sort(key=lambda s: s.start_time)
    return sessions
