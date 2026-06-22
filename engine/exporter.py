from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.parse import unquote

import yaml
from jinja2 import Environment, StrictUndefined

from .models import Session, Topic

_FORBIDDEN_FS = re.compile(r'[\\/:"*?<>|\x00-\x1f]+')
_DASHES = re.compile(r"-{2,}")
_HEADER_LINE = re.compile(r"^(#+) ", flags=re.MULTILINE)

# Inline Markdown image: ![alt](src) and ![alt](src "title")
_IMG_MD_RE = re.compile(r'(!\[[^\]]*\]\()(\s*)(<[^>]+>|[^)\s]+)([^)]*)(\))')
_ABS_SRC_RE = re.compile(r"^(?:[a-z][a-z0-9+.\-]*://|data:|/|#)", re.IGNORECASE)
# Same extension fallbacks the Parser uses when Takeout's name disagrees with disk.
_RESOLVE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg")


def _raw_search_dirs(raw_dir: Path) -> List[Path]:
    """Mirror the UI's /raw mount: each `Gemini Apps YYMMDD` subdir, newest
    first, then raw_dir itself as a fallback for single-directory layouts."""
    subdirs = sorted((p for p in raw_dir.glob("Gemini Apps *") if p.is_dir()), reverse=True)
    return [*subdirs, raw_dir]


def _find_raw_file(name: str, search_dirs: List[Path]) -> Optional[Path]:
    for d in search_dirs:
        if (d / name).exists():
            return d / name
        stem = Path(name).stem
        for ext in _RESOLVE_EXTS:
            cand = d / f"{stem}{ext}"
            if cand != d / name and cand.exists():
                return cand
        if (d / stem).exists():
            return d / stem
    return None


def _localize_images(md: str, search_dirs: List[Path], assets_dir: Path, rel_prefix: str) -> str:
    """Copy each referenced raw image into assets_dir and rewrite the link to
    rel_prefix + filename, so the exported Markdown is self-contained.

    Remote/absolute srcs are left untouched; unresolvable names (e.g. Gemini's
    `image_agent_tag_*` with no file on disk) are left as-is."""
    def repl(m: re.Match) -> str:
        open_, ws, raw_src, trailing, close = m.groups()
        src = raw_src[1:-1] if raw_src.startswith("<") and raw_src.endswith(">") else raw_src
        if _ABS_SRC_RE.match(src):
            return m.group(0)
        found = _find_raw_file(unquote(src), search_dirs)
        if found is None:
            return m.group(0)
        assets_dir.mkdir(parents=True, exist_ok=True)
        dest = assets_dir / found.name
        if not dest.exists():
            shutil.copy2(found, dest)
        return f"{open_}{ws}{rel_prefix}{found.name}{trailing}{close}"

    return _IMG_MD_RE.sub(repl, md)


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


def export_session(
    session: Session,
    template_cfg: dict,
    exports_dir: Path,
    turns_md_dir: Path,
    *,
    search_dirs: Optional[List[Path]] = None,
    assets_dir: Optional[Path] = None,
    rel_prefix: str = "",
) -> Path:
    exports_dir.mkdir(parents=True, exist_ok=True)
    pattern = template_cfg.get("filename_pattern", "{date}_{sid}_{slug}.md")
    slug_max = int(template_cfg.get("slug_max_chars", 40))
    date = session.start_time.split(" ", 1)[0]
    filename = pattern.format(date=date, sid=session.session_id, slug=_slugify(session.title, slug_max))
    path = exports_dir / filename
    body = render_session(session, template_cfg, turns_md_dir)
    if search_dirs and assets_dir is not None:
        body = _localize_images(body, search_dirs, assets_dir, rel_prefix)
    path.write_text(body, encoding="utf-8")
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


def export_topic(
    topic: Topic,
    sessions_by_id: Dict[str, Session],
    template_cfg: dict,
    exports_dir: Path,
    turns_md_dir: Path,
    *,
    search_dirs: Optional[List[Path]] = None,
    assets_dir: Optional[Path] = None,
    rel_prefix: str = "",
) -> Optional[Path]:
    body = render_topic(topic, sessions_by_id, template_cfg, turns_md_dir)
    if body is None:
        return None
    if search_dirs and assets_dir is not None:
        body = _localize_images(body, search_dirs, assets_dir, rel_prefix)
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
    raw_dir: Optional[Path] = None,
) -> List[Path]:
    written: List[Path] = []
    sessions_list = list(sessions)
    sessions_by_id = {s.session_id: s for s in sessions_list}

    # Session exports land in exports_dir/sessions, Topic exports in exports_dir/topics
    sessions_out = exports_dir / "sessions"
    topics_out = exports_dir / "topics"

    # Self-contained images: copy referenced raw images into exports_dir/assets
    # and rewrite links to ../assets/<name> (both sessions/ and topics/ sit one
    # level under exports_dir). Skipped when raw_dir is unknown.
    assets_dir = exports_dir / "assets"
    search_dirs = _raw_search_dirs(raw_dir) if raw_dir is not None else None
    rel_prefix = "../assets/"

    # Session exports
    if only_topic_ids is None:
        # default: also export per-Session unless caller asks for topics-only
        for session in sessions_list:
            if only_session_ids is not None and session.session_id not in only_session_ids:
                continue
            if not any(t.visibility_flag for t in session.turns):
                continue
            written.append(export_session(
                session, template_cfg, sessions_out, turns_md_dir,
                search_dirs=search_dirs, assets_dir=assets_dir, rel_prefix=rel_prefix,
            ))

    # Topic exports
    if topics:
        wanted = set(only_topic_ids) if only_topic_ids is not None else None
        for topic in topics:
            if wanted is not None and topic.topic_id not in wanted:
                continue
            path = export_topic(
                topic, sessions_by_id, template_cfg, topics_out, turns_md_dir,
                search_dirs=search_dirs, assets_dir=assets_dir, rel_prefix=rel_prefix,
            )
            if path is not None:
                written.append(path)
    return written


def load_session(sessions_dir: Path, session_id: str) -> Session:
    path = sessions_dir / f"session_{session_id}.json"
    return Session.model_validate_json(path.read_text(encoding="utf-8"))


def load_all_sessions(sessions_dir: Path) -> List[Session]:
    if not sessions_dir.exists():
        return []
    sessions: List[Session] = []
    for p in sorted(sessions_dir.glob("session_*.json")):
        sessions.append(Session.model_validate_json(p.read_text(encoding="utf-8")))
    sessions.sort(key=lambda s: s.start_time)
    return sessions
