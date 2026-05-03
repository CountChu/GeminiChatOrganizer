from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Callable, Dict, List, Optional

from jinja2 import Environment, StrictUndefined

from . import topic_mgr
from .exporter import export_archive, load_session, load_template_config
from .models import Session, SessionSummary, Topic, TopicSummary
from .parser import merge_visibility, parse_archive, write_sessions
from .render_md import render_all, render_turn


class State:
    def __init__(
        self,
        raw_dir: Path,
        sessions_dir: Path,
        turns_md_dir: Path,
        topics_dir: Path,
        exports_dir: Path,
        gap_seconds: int,
        template_path: Path,
    ) -> None:
        self.raw_dir = raw_dir
        self.sessions_dir = sessions_dir
        self.turns_md_dir = turns_md_dir
        self.topics_dir = topics_dir
        self.exports_dir = exports_dir
        self.gap_seconds = gap_seconds
        self.template_path = template_path
        self._sessions_cache: Optional[List[Session]] = None

    def ensure_loaded(self) -> List[Session]:
        if self._sessions_cache is not None:
            return self._sessions_cache
        archive = parse_archive(self.raw_dir, self.gap_seconds)
        merge_visibility(archive, self.sessions_dir)
        write_sessions(archive, self.sessions_dir)
        render_all(self.sessions_dir, self.turns_md_dir, self.template_path)
        self._sessions_cache = archive.sessions
        return archive.sessions

    def reload(self) -> List[Session]:
        self._sessions_cache = None
        return self.ensure_loaded()

    def get_session(self, sid: str) -> Session:
        for s in self.ensure_loaded():
            if s.session_id == sid:
                return s
        return load_session(self.sessions_dir, sid)

    def write_session(self, session: Session) -> None:
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        path = self.sessions_dir / f"session_{session.session_id}.json"
        path.write_text(session.model_dump_json(indent=2, by_alias=True), encoding="utf-8")
        if self._sessions_cache is not None:
            for i, s in enumerate(self._sessions_cache):
                if s.session_id == session.session_id:
                    self._sessions_cache[i] = session
                    break


def _summary(s: Session, topic_id: Optional[str]) -> SessionSummary:
    visible = sum(1 for t in s.turns if t.visibility_flag)
    return SessionSummary(
        session_id=s.session_id,
        title=s.title,
        start_time=s.start_time,
        last_active_time=s.last_active_time,
        turn_count=s.turn_count,
        visible_count=visible,
        topic_id=topic_id,
    )


def _topic_summary(t: Topic) -> TopicSummary:
    return TopicSummary(topic_id=t.topic_id, name=t.name, session_count=len(t.session_ids), created_at=t.created_at)


# ---------- session commands ----------

def cmd_list_sessions(state: State, _args: dict) -> dict:
    sessions = state.ensure_loaded()
    membership = topic_mgr.session_to_topic_map(topic_mgr.load_topics(state.topics_dir))
    return {"sessions": [_summary(s, membership.get(s.session_id)).model_dump(by_alias=True) for s in sessions]}


def cmd_get_session(state: State, args: dict) -> dict:
    sid = args["sessionId"]
    return {"session": state.get_session(sid).model_dump(by_alias=True)}


def cmd_update_turn_prompt(state: State, args: dict) -> dict:
    sid = args["sessionId"]
    tid = args["turnId"]
    prompt2 = str(args.get("prompt2", "")).strip()
    session = state.get_session(sid)
    target = next((t for t in session.turns if t.turn_id == tid), None)
    if target is None:
        raise KeyError(f"turn {tid} not found in session {sid}")
    target.prompt2 = prompt2
    state.write_session(session)
    template_cfg = load_template_config(state.template_path)
    env = Environment(undefined=StrictUndefined, autoescape=False)
    md_path = state.turns_md_dir / f"{tid}.md"
    md_path.write_text(render_turn(target, template_cfg, env), encoding="utf-8")
    return {"sessionId": sid, "turnId": tid, "prompt2": prompt2}


def cmd_toggle_turn(state: State, args: dict) -> dict:
    sid = args["sessionId"]
    tid = args["turnId"]
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
    return {"sessionId": sid, "turnId": tid, "visible": visible}


# ---------- topic commands ----------

def cmd_list_topics(state: State, _args: dict) -> dict:
    topics = topic_mgr.load_topics(state.topics_dir)
    return {"topics": [_topic_summary(t).model_dump(by_alias=True) for t in topics]}


def cmd_get_topic(state: State, args: dict) -> dict:
    tid = args["topicId"]
    topic = topic_mgr.load_topic(state.topics_dir, tid)
    sessions = {s.session_id: s for s in state.ensure_loaded()}
    membership = topic_mgr.session_to_topic_map(topic_mgr.load_topics(state.topics_dir))
    members = []
    for sid in topic.session_ids:
        s = sessions.get(sid)
        if s is None:
            continue
        members.append(_summary(s, membership.get(sid)).model_dump(by_alias=True))
    return {"topic": topic.model_dump(by_alias=True), "sessions": members}


def cmd_create_topic(state: State, args: dict) -> dict:
    name = args.get("name", "")
    sids = list(args.get("sessionIds") or [])
    description = args.get("description", "") or ""
    tags = list(args.get("tags") or [])
    topic = topic_mgr.create_topic(state.topics_dir, name=name, session_ids=sids, description=description, tags=tags)
    return {"topic": topic.model_dump(by_alias=True)}


def cmd_update_topic(state: State, args: dict) -> dict:
    tid = args["topicId"]
    patch = args.get("patch") or {}
    topic = topic_mgr.update_topic(
        state.topics_dir,
        tid,
        name=patch.get("name"),
        description=patch.get("description"),
        tags=patch.get("tags"),
    )
    return {"topic": topic.model_dump(by_alias=True)}


def cmd_delete_topic(state: State, args: dict) -> dict:
    tid = args["topicId"]
    topic_mgr.delete_topic(tid, state.topics_dir)
    return {"topicId": tid, "deleted": True}


def cmd_add_sessions_to_topic(state: State, args: dict) -> dict:
    tid = args["topicId"]
    sids = list(args.get("sessionIds") or [])
    topic = topic_mgr.add_sessions(state.topics_dir, tid, sids)
    return {"topic": topic.model_dump(by_alias=True)}


def cmd_remove_sessions_from_topic(state: State, args: dict) -> dict:
    tid = args["topicId"]
    sids = list(args.get("sessionIds") or [])
    topic = topic_mgr.remove_sessions(state.topics_dir, tid, sids)
    return {"topic": topic.model_dump(by_alias=True)}


def cmd_reorder_topic_sessions(state: State, args: dict) -> dict:
    tid = args["topicId"]
    sids = list(args.get("sessionIds") or [])
    topic = topic_mgr.reorder_sessions(state.topics_dir, tid, sids)
    return {"topic": topic.model_dump(by_alias=True)}


# ---------- export ----------

def cmd_export(state: State, args: dict) -> dict:
    only_session_ids = args.get("sessionIds")
    only_topic_ids = args.get("topicIds")
    template_cfg = load_template_config(state.template_path)
    sessions = state.ensure_loaded()
    topics = topic_mgr.load_topics(state.topics_dir)
    written = export_archive(
        sessions,
        template_cfg,
        state.exports_dir,
        state.turns_md_dir,
        only_session_ids=only_session_ids,
        topics=topics,
        only_topic_ids=only_topic_ids,
    )
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
    "update_turn_prompt": cmd_update_turn_prompt,
    "list_topics": cmd_list_topics,
    "get_topic": cmd_get_topic,
    "create_topic": cmd_create_topic,
    "update_topic": cmd_update_topic,
    "delete_topic": cmd_delete_topic,
    "add_sessions_to_topic": cmd_add_sessions_to_topic,
    "remove_sessions_from_topic": cmd_remove_sessions_from_topic,
    "reorder_topic_sessions": cmd_reorder_topic_sessions,
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
