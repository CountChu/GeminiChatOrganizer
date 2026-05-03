from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .models import Archive, Session, Turn, TurnKind

ACTIVITY_FILENAME = "我的活動.json"
TITLE_MAX_CHARS = 20
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


def _make_title(group: List[Turn]) -> str:
    src = next((t.prompt for t in group if t.kind == "prompted" and t.prompt), group[0].prompt) or ""
    src = " ".join(src.strip().splitlines())
    return src[:TITLE_MAX_CHARS] if src else "(untitled)"


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
        first = group[0]
        first_unix = int(datetime.fromisoformat(first.timestamp_utc.replace("Z", "+00:00")).timestamp())
        sessions.append(
            Session(
                session_id=f"S{first_unix}",
                title=_make_title(group),
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
        flags: Dict[str, bool] = {}
        prompt2s: Dict[str, str] = {}
        for t in existing.get("turns", []):
            tid = t.get("turnId", t.get("turn_id"))
            if tid is None:
                continue
            flags[tid] = bool(t.get("visibilityFlag", t.get("visibility_flag", True)))
            p2 = t.get("prompt2", "")
            if p2:
                prompt2s[tid] = p2
        for turn in session.turns:
            if turn.turn_id in flags:
                turn.visibility_flag = flags[turn.turn_id]
            if turn.turn_id in prompt2s:
                turn.prompt2 = prompt2s[turn.turn_id]
    return archive


def write_sessions(archive: Archive, sessions_dir: Path) -> List[Path]:
    sessions_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for session in archive.sessions:
        path = sessions_dir / f"session_{session.session_id}.json"
        path.write_text(session.model_dump_json(indent=2, by_alias=True), encoding="utf-8")
        written.append(path)
    return written
