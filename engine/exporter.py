from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import yaml
from jinja2 import Environment, StrictUndefined

from .models import Session, Topic

_FORBIDDEN_FS = re.compile(r'[\\/:"*?<>|\x00-\x1f]+')
_DASHES = re.compile(r"-{2,}")
_HEADER_LINE = re.compile(r"^(#+) ", flags=re.MULTILINE)


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


def _demote_headers(md: str) -> str:
    return _HEADER_LINE.sub(r"\1# ", md)


def load_template_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


# ---------- per-Session export (existing flow) ----------

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


# ---------- per-Topic export ----------

def render_topic(topic: Topic, sessions_by_id: Dict[str, Session], template_cfg: dict, turns_md_dir: Path) -> Optional[str]:
    env = Environment(undefined=StrictUndefined, autoescape=False)
    sep = template_cfg.get("turn_separator", "\n\n---\n\n")
    session_block_tpl = env.from_string(template_cfg.get("topic_session_header", "## Session: {{ title }}"))

    parts: List[str] = [f"# {topic.name}"]
    if topic.description.strip():
        parts.append(topic.description.strip())

    session_blocks: List[str] = []
    for sid in topic.session_ids:
        session = sessions_by_id.get(sid)
        if session is None:
            continue
        if not any(t.visibility_flag for t in session.turns):
            continue
        rendered_turns: List[str] = []
        for turn in session.turns:
            if not turn.visibility_flag:
                continue
            md_path = turns_md_dir / f"{turn.turn_id}.md"
            if not md_path.exists():
                continue
            rendered_turns.append(_demote_headers(md_path.read_text(encoding="utf-8").rstrip()))
        if not rendered_turns:
            continue
        block = (
            session_block_tpl.render(title=session.title, session_id=session.session_id,
                                     start_time=session.start_time, last_active_time=session.last_active_time)
            + f"\n\n_{session.start_time} – {session.last_active_time}_\n\n"
            + sep.join(rendered_turns)
        )
        session_blocks.append(block)

    if not session_blocks:
        return None

    parts.append("\n\n---\n\n".join(session_blocks))
    return "\n\n".join(parts).rstrip() + "\n"


def export_topic(topic: Topic, sessions_by_id: Dict[str, Session], template_cfg: dict, exports_dir: Path, turns_md_dir: Path) -> Optional[Path]:
    body = render_topic(topic, sessions_by_id, template_cfg, turns_md_dir)
    if body is None:
        return None
    exports_dir.mkdir(parents=True, exist_ok=True)
    pattern = template_cfg.get("topic_filename_pattern", "{date}_{topic_id}_{slug}.md")
    slug_max = int(template_cfg.get("slug_max_chars", 40))
    date = topic.created_at.split(" ", 1)[0]
    filename = pattern.format(date=date, topic_id=topic.topic_id, slug=_slugify(topic.name, slug_max))
    path = exports_dir / filename
    path.write_text(body, encoding="utf-8")
    return path


# ---------- archive-level dispatch ----------

def export_archive(
    sessions: Iterable[Session],
    template_cfg: dict,
    exports_dir: Path,
    turns_md_dir: Path,
    *,
    only_session_ids: Optional[List[str]] = None,
    topics: Optional[List[Topic]] = None,
    only_topic_ids: Optional[List[str]] = None,
) -> List[Path]:
    written: List[Path] = []
    sessions_list = list(sessions)
    sessions_by_id = {s.session_id: s for s in sessions_list}

    # Session exports
    if only_topic_ids is None:
        # default: also export per-Session unless caller asks for topics-only
        for session in sessions_list:
            if only_session_ids is not None and session.session_id not in only_session_ids:
                continue
            if not any(t.visibility_flag for t in session.turns):
                continue
            written.append(export_session(session, template_cfg, exports_dir, turns_md_dir))

    # Topic exports
    if topics:
        wanted = set(only_topic_ids) if only_topic_ids is not None else None
        for topic in topics:
            if wanted is not None and topic.topic_id not in wanted:
                continue
            path = export_topic(topic, sessions_by_id, template_cfg, exports_dir, turns_md_dir)
            if path is not None:
                written.append(path)
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
