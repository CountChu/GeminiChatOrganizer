from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .exporter import export_archive, load_session, load_template_config
from .models import Session, SessionSummary
from .parser import merge_visibility, parse_archive, write_processed
from .render_md import render_all


class State:
    def __init__(
        self,
        raw_dir: Path,
        processed_dir: Path,
        turns_md_dir: Path,
        exports_dir: Path,
        gap_seconds: int,
        template_path: Path,
    ) -> None:
        self.raw_dir = raw_dir
        self.processed_dir = processed_dir
        self.turns_md_dir = turns_md_dir
        self.exports_dir = exports_dir
        self.gap_seconds = gap_seconds
        self.template_path = template_path
        self._sessions_cache: Optional[List[Session]] = None

    def ensure_loaded(self) -> List[Session]:
        if self._sessions_cache is not None:
            return self._sessions_cache
        archive = parse_archive(self.raw_dir, self.gap_seconds)
        merge_visibility(archive, self.processed_dir)
        write_processed(archive, self.processed_dir)
        render_all(self.processed_dir, self.turns_md_dir, self.template_path)
        self._sessions_cache = archive.sessions
        return archive.sessions

    def reload(self) -> List[Session]:
        self._sessions_cache = None
        return self.ensure_loaded()

    def get_session(self, sid: str) -> Session:
        for s in self.ensure_loaded():
            if s.session_id == sid:
                return s
        return load_session(self.processed_dir, sid)

    def write_session(self, session: Session) -> None:
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        path = self.processed_dir / f"session_{session.session_id}.json"
        path.write_text(session.model_dump_json(indent=2), encoding="utf-8")
        if self._sessions_cache is not None:
            for i, s in enumerate(self._sessions_cache):
                if s.session_id == session.session_id:
                    self._sessions_cache[i] = session
                    break


def _summary(s: Session) -> SessionSummary:
    visible = sum(1 for t in s.turns if t.visibility_flag)
    return SessionSummary(
        session_id=s.session_id,
        title=s.title,
        start_time=s.start_time,
        last_active_time=s.last_active_time,
        turn_count=s.turn_count,
        visible_count=visible,
    )


def cmd_list_sessions(state: State, _args: dict) -> dict:
    sessions = state.ensure_loaded()
    return {"sessions": [_summary(s).model_dump() for s in sessions]}


def cmd_get_session(state: State, args: dict) -> dict:
    sid = args["session_id"]
    return {"session": state.get_session(sid).model_dump()}


def cmd_toggle_turn(state: State, args: dict) -> dict:
    sid = args["session_id"]
    tid = args["turn_id"]
    visible = bool(args["visible"])
    session = state.get_session(sid)
    found = False
    for t in session.turns:
        if t.turn_id == tid:
            t.visibility_flag = visible
            found = True
            break
    if not found:
        raise KeyError(f"turn {tid} not found in session {sid}")
    state.write_session(session)
    return {"session_id": sid, "turn_id": tid, "visible": visible}


def cmd_export(state: State, args: dict) -> dict:
    only = args.get("session_ids")
    template_cfg = load_template_config(state.template_path)
    sessions = state.ensure_loaded()
    written = export_archive(sessions, template_cfg, state.exports_dir, state.turns_md_dir, only_ids=only)
    return {"files": [str(p) for p in written]}


def cmd_reload(state: State, _args: dict) -> dict:
    sessions = state.reload()
    return {"count": len(sessions)}


def cmd_shutdown(_state: State, _args: dict) -> dict:
    return {"bye": True}


COMMANDS: Dict[str, Callable[[State, dict], dict]] = {
    "list_sessions": cmd_list_sessions,
    "get_session": cmd_get_session,
    "toggle_turn": cmd_toggle_turn,
    "export": cmd_export,
    "reload": cmd_reload,
    "shutdown": cmd_shutdown,
}


def serve(state: State) -> None:
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        msg_id = None
        try:
            msg = json.loads(line)
            msg_id = msg.get("id")
            cmd = msg.get("cmd")
            args = msg.get("args") or {}
            handler = COMMANDS.get(cmd)
            if handler is None:
                _emit({"id": msg_id, "ok": False, "error": {"type": "unknown_command", "msg": cmd or ""}})
                continue
            data = handler(state, args)
            _emit({"id": msg_id, "ok": True, "data": data})
            if cmd == "shutdown":
                return
        except Exception as e:
            _emit({
                "id": msg_id,
                "ok": False,
                "error": {"type": e.__class__.__name__, "msg": str(e), "trace": traceback.format_exc()},
            })


def _emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.write("\n")
    sys.stdout.flush()
