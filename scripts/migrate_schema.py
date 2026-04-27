"""One-shot migration: rewrite session_*.json and topic_*.json from snake_case to camelCase keys.

Pydantic models in engine/models.py use `populate_by_name=True`, so they accept either snake_case
field names or camelCase aliases. This script just round-trips each file through the model and
writes it back with `by_alias=True`, producing camelCase JSON. It also fills in Topic.updated
(seeding it from `created_at` if absent on disk).

Idempotent: re-running on already-migrated files is a no-op.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.models import Session, Topic


def migrate_sessions(sessions_dir: Path) -> int:
    n = 0
    for p in sorted(sessions_dir.glob("session_*.json")):
        s = Session.model_validate_json(p.read_text(encoding="utf-8"))
        p.write_text(s.model_dump_json(indent=2, by_alias=True), encoding="utf-8")
        n += 1
    return n


def migrate_topics(topics_dir: Path) -> int:
    n = 0
    for p in sorted(topics_dir.glob("topic_*.json")):
        t = Topic.model_validate_json(p.read_text(encoding="utf-8"))
        if t.updated_at is None:
            t.updated_at = t.created_at
        p.write_text(t.model_dump_json(indent=2, by_alias=True), encoding="utf-8")
        n += 1
    return n


def main() -> int:
    sessions_dir = ROOT / "data" / "1-sessions"
    topics_dir = ROOT / "data" / "3-topics"
    print(f"sessions: {migrate_sessions(sessions_dir)} files migrated in {sessions_dir}")
    print(f"topics:   {migrate_topics(topics_dir)} files migrated in {topics_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
