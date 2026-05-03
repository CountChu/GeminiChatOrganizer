from __future__ import annotations

import secrets
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .models import Topic


def new_topic_id() -> str:
    return f"topic_{datetime.now().strftime('%Y%m%d')}_{secrets.token_hex(3)}"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _topic_path(topics_dir: Path, topic_id: str) -> Path:
    return topics_dir / f"{topic_id}.json"


def load_topics(topics_dir: Path) -> List[Topic]:
    if not topics_dir.exists():
        return []
    out: List[Topic] = []
    for p in sorted(topics_dir.glob("topic_*.json")):
        try:
            out.append(Topic.model_validate_json(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    out.sort(key=lambda t: t.created_at)
    return out


def load_topic(topics_dir: Path, topic_id: str) -> Topic:
    return Topic.model_validate_json(_topic_path(topics_dir, topic_id).read_text(encoding="utf-8"))


def save_topic(topic: Topic, topics_dir: Path) -> Path:
    topic.updated_at = _now()
    topics_dir.mkdir(parents=True, exist_ok=True)
    path = _topic_path(topics_dir, topic.topic_id)
    path.write_text(topic.model_dump_json(indent=2, by_alias=True), encoding="utf-8")
    return path


def delete_topic(topic_id: str, topics_dir: Path) -> None:
    path = _topic_path(topics_dir, topic_id)
    if path.exists():
        path.unlink()


def topic_id_for_session(topics: List[Topic], session_id: str) -> Optional[str]:
    for t in topics:
        if session_id in t.session_ids:
            return t.topic_id
    return None


def session_to_topic_map(topics: List[Topic]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for t in topics:
        for sid in t.session_ids:
            out[sid] = t.topic_id
    return out


def create_topic(topics_dir: Path, name: str, session_ids: List[str], description: str = "", tags: Optional[List[str]] = None) -> Topic:
    if not name.strip():
        raise ValueError("name must be non-empty")
    # Single-membership: pull these sessions out of any existing topic first.
    if session_ids:
        _strip_sessions_from_others(topics_dir, exclude_topic_id=None, session_ids=session_ids)
    topic = Topic(
        topic_id=new_topic_id(),
        name=name.strip(),
        description=description,
        session_ids=_dedupe_preserve_order(session_ids),
        tags=tags or [],
        created_at=_now(),
    )
    save_topic(topic, topics_dir)
    return topic


def update_topic(topics_dir: Path, topic_id: str, *, name: Optional[str] = None, description: Optional[str] = None, tags: Optional[List[str]] = None) -> Topic:
    topic = load_topic(topics_dir, topic_id)
    if name is not None:
        if not name.strip():
            raise ValueError("name must be non-empty")
        topic.name = name.strip()
    if description is not None:
        topic.description = description
    if tags is not None:
        topic.tags = list(tags)
    save_topic(topic, topics_dir)
    return topic


def add_sessions(topics_dir: Path, topic_id: str, session_ids: List[str]) -> Topic:
    if not session_ids:
        return load_topic(topics_dir, topic_id)
    _strip_sessions_from_others(topics_dir, exclude_topic_id=topic_id, session_ids=session_ids)
    topic = load_topic(topics_dir, topic_id)
    topic.session_ids = _dedupe_preserve_order(topic.session_ids + list(session_ids))
    save_topic(topic, topics_dir)
    return topic


def remove_sessions(topics_dir: Path, topic_id: str, session_ids: List[str]) -> Topic:
    topic = load_topic(topics_dir, topic_id)
    drop = set(session_ids)
    topic.session_ids = [s for s in topic.session_ids if s not in drop]
    save_topic(topic, topics_dir)
    return topic


def reorder_sessions(topics_dir: Path, topic_id: str, ordered_session_ids: List[str]) -> Topic:
    topic = load_topic(topics_dir, topic_id)
    existing = set(topic.session_ids)
    new_order = [s for s in ordered_session_ids if s in existing]
    if set(new_order) != existing:
        missing = existing - set(new_order)
        raise ValueError(f"reorder list missing sessions: {sorted(missing)}")
    topic.session_ids = new_order
    save_topic(topic, topics_dir)
    return topic


def _strip_sessions_from_others(topics_dir: Path, exclude_topic_id: Optional[str], session_ids: List[str]) -> None:
    drop = set(session_ids)
    for t in load_topics(topics_dir):
        if t.topic_id == exclude_topic_id:
            continue
        if not any(s in drop for s in t.session_ids):
            continue
        t.session_ids = [s for s in t.session_ids if s not in drop]
        save_topic(t, topics_dir)


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out
