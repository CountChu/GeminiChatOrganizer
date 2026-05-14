from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .models import TITLE_MAX_CHARS, Archive, Session, Turn, TurnKind

ACTIVITY_FILENAME = "我的活動.json"
RAW_DIR_PATTERN = re.compile(r"^Gemini Apps (\d{6})$")
__all__ = ["ACTIVITY_FILENAME", "RAW_DIR_PATTERN", "TITLE_MAX_CHARS"]
_RESOLVE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".md", ".txt", ".pdf", ".json")

_TITLE_PREFIX_TO_KIND: Dict[str, TurnKind] = {
    "Prompted": "prompted",
    "Created": "created",
    "Gave": "gave",
    "Selected": "selected",
}


def _format_local(dt_utc: datetime) -> str:
    return dt_utc.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _classify(title: str) -> Tuple[TurnKind, str]:
    if not title:
        return "other", ""
    head, _, rest = title.partition(" ")
    kind = _TITLE_PREFIX_TO_KIND.get(head, "other")
    if kind == "prompted":
        return kind, rest
    return kind, title


def _resolve_attachment(name: str, raw_dir: Path) -> str:
    """Resolve an attachment name against raw_dir.

    Takeout sometimes lists a different extension than what's saved on disk
    (e.g. `.png` for files saved as `.jpg`) or saves docs with no extension at
    all (e.g. listed `Foo.md`, on disk `Foo`). Try a small set of plausible
    alternates, then the bare stem. Falls back to the original name.
    """
    if (raw_dir / name).exists():
        return name
    stem = Path(name).stem
    for ext in _RESOLVE_EXTS:
        candidate = f"{stem}{ext}"
        if candidate != name and (raw_dir / candidate).exists():
            return candidate
    if (raw_dir / stem).exists():
        return stem
    return name


def _attachments_from_entry(entry: dict, raw_dir: Path) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()

    def add(name: str) -> None:
        resolved = _resolve_attachment(name, raw_dir)
        if resolved not in seen:
            seen.add(resolved)
            out.append(resolved)

    image = entry.get("imageFile")
    if isinstance(image, dict):
        name = image.get("name") or image.get("url")
        if name:
            add(str(name))
    elif isinstance(image, str):
        add(image)
    for af in entry.get("attachedFiles") or []:
        if isinstance(af, dict):
            name = af.get("name") or af.get("url")
            if name:
                add(str(name))
        elif isinstance(af, str):
            add(af)
    return out


def _entry_to_turn(entry: dict, raw_dir: Path) -> Optional[Turn]:
    time_raw = entry.get("time")
    if not time_raw:
        return None
    iso = time_raw.replace("Z", "+00:00")
    dt_utc = datetime.fromisoformat(iso).astimezone(timezone.utc)
    title = entry.get("title", "") or ""
    kind, prompt = _classify(title)
    html = ""
    safe = entry.get("safeHtmlItem")
    if isinstance(safe, list) and safe and isinstance(safe[0], dict):
        html = safe[0].get("html", "") or ""
    if not html and kind == "created":
        subs = entry.get("subtitles")
        if isinstance(subs, list) and subs and isinstance(subs[0], dict):
            name = subs[0].get("name", "")
            if name:
                html = f"<pre>{name}</pre>"
    turn_id = f"T{int(dt_utc.timestamp())}"
    return Turn(
        turn_id=turn_id,
        timestamp=_format_local(dt_utc),
        timestamp_utc=dt_utc.isoformat().replace("+00:00", "Z"),
        kind=kind,
        prompt=prompt,
        response=html,
        attachments=_attachments_from_entry(entry, raw_dir),
        visibility_flag=True,
    )


def _dedupe_turn_ids_in_session(turns: List[Turn]) -> None:
    """Suffix colliding turn_ids within a session deterministically by order.
    First occurrence keeps its base id; subsequent get `_1`, `_2`, ... .
    Caller is responsible for ordering (we expect timestamp_utc order)."""
    seen: Dict[str, int] = {}
    for t in turns:
        base = t.turn_id
        n = seen.get(base, 0)
        if n > 0:
            t.turn_id = f"{base}_{n}"
        seen[base] = n + 1


def _group_sessions(turns: List[Turn], gap_seconds: int) -> List[Session]:
    if not turns:
        return []
    turns_sorted = sorted(turns, key=lambda t: t.timestamp_utc)
    groups: List[List[Turn]] = [[turns_sorted[0]]]
    for prev, cur in zip(turns_sorted, turns_sorted[1:]):
        prev_dt = datetime.fromisoformat(prev.timestamp_utc.replace("Z", "+00:00"))
        cur_dt = datetime.fromisoformat(cur.timestamp_utc.replace("Z", "+00:00"))
        if (cur_dt - prev_dt).total_seconds() > gap_seconds:
            groups.append([cur])
        else:
            groups[-1].append(cur)
    sessions: List[Session] = []
    for group in groups:
        _dedupe_turn_ids_in_session(group)
        first = group[0]
        first_unix = int(datetime.fromisoformat(first.timestamp_utc.replace("Z", "+00:00")).timestamp())
        sessions.append(
            Session(
                session_id=f"S{first_unix}",
                start_time=group[0].timestamp,
                last_active_time=group[-1].timestamp,
                turns=group,
            )
        )
    return sessions


def parse_archive(raw_dir: Path, session_gap_seconds: int) -> Archive:
    activity_path = raw_dir / ACTIVITY_FILENAME
    if not activity_path.exists():
        raise FileNotFoundError(f"Activity file not found: {activity_path}")
    data = json.loads(activity_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected list at top level of {activity_path}, got {type(data).__name__}")
    turns: List[Turn] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        if entry.get("header") != "Gemini Apps":
            continue
        turn = _entry_to_turn(entry, raw_dir)
        if turn is not None:
            turns.append(turn)
    sessions = _group_sessions(turns, session_gap_seconds)
    return Archive(source=str(raw_dir), sessions=sessions)


def merge_visibility(archive: Archive, sessions_dir: Path) -> Archive:
    if not sessions_dir.exists():
        return archive
    for session in archive.sessions:
        path = sessions_dir / f"session_{session.session_id}.json"
        if not path.exists():
            continue
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        # Key by timestamp_utc — stable and unique even when turn_ids on disk
        # collide from a pre-dedup parser run.
        flags: Dict[str, bool] = {}
        prompt2s: Dict[str, str] = {}
        collapse_flags: Dict[str, bool] = {}
        for t in existing.get("turns", []):
            ts = t.get("timestampUtc", t.get("timestamp_utc"))
            if ts is None:
                continue
            flags[ts] = bool(t.get("visibilityFlag", t.get("visibility_flag", True)))
            p2 = t.get("prompt2", "")
            if p2:
                prompt2s[ts] = p2
            collapse_flags[ts] = bool(t.get("collapseFlag", t.get("collapse_flag", False)))
        for turn in session.turns:
            ts = turn.timestamp_utc
            if ts in flags:
                turn.visibility_flag = flags[ts]
            if ts in prompt2s:
                turn.prompt2 = prompt2s[ts]
            if ts in collapse_flags:
                turn.collapse_flag = collapse_flags[ts]
    return archive


def write_sessions(archive: Archive, sessions_dir: Path) -> List[Path]:
    sessions_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for session in archive.sessions:
        path = sessions_dir / f"session_{session.session_id}.json"
        path.write_text(
            session.model_dump_json(indent=2, by_alias=True, exclude={"title"}),
            encoding="utf-8",
        )
        written.append(path)
    return written


def discover_raw_dirs(raw_root: Path) -> List[Path]:
    if not raw_root.exists() or not raw_root.is_dir():
        return []
    matches: List[Tuple[str, Path]] = []
    for child in raw_root.iterdir():
        if not child.is_dir():
            continue
        m = RAW_DIR_PATTERN.match(child.name)
        if m:
            matches.append((m.group(1), child))
    matches.sort(key=lambda pair: pair[0])
    return [p for _, p in matches]


def parse_with_diff(
    raw_root: Path,
    sessions_dir: Path,
    gap_seconds: int,
    sync_strategy: str = "archive",
) -> Archive:
    dirs = discover_raw_dirs(raw_root)
    if not dirs:
        # Legacy: rawDir already names a single date dir.
        if (raw_root / ACTIVITY_FILENAME).exists():
            archive = parse_archive(raw_root, gap_seconds)
            merge_visibility(archive, sessions_dir)
            return archive
        raise FileNotFoundError(
            f"No `Gemini Apps YYMMDD` subdirectories under {raw_root}, "
            f"and no {ACTIVITY_FILENAME} directly inside it."
        )
    if len(dirs) == 1:
        archive = parse_archive(dirs[0], gap_seconds)
        archive.source = str(raw_root)
        merge_visibility(archive, sessions_dir)
        return archive

    older = parse_archive(dirs[-2], gap_seconds)
    newer = parse_archive(dirs[-1], gap_seconds)
    old_idx: Dict[str, Turn] = {t.timestamp_utc: t for s in older.sessions for t in s.turns}
    new_idx: Dict[str, Turn] = {t.timestamp_utc: t for s in newer.sessions for t in s.turns}

    merged: List[Turn] = list(new_idx.values())
    if sync_strategy == "archive":
        deleted = old_idx.keys() - new_idx.keys()
        for k in deleted:
            ghost = old_idx[k]
            ghost.missing = True
            merged.append(ghost)

    archive = Archive(
        source=str(raw_root),
        sessions=_group_sessions(merged, gap_seconds),
    )
    merge_visibility(archive, sessions_dir)
    return archive
