from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field

TurnKind = Literal["prompted", "created", "gave", "selected", "other"]


class Turn(BaseModel):
    turn_id: str
    timestamp: str  # YYYY-MM-DD HH:mm:ss (local)
    timestamp_utc: str  # original ISO-8601 from Takeout
    kind: TurnKind = "prompted"
    prompt: str = ""
    response: str = ""  # raw HTML from Gemini; the Renderer turns this into MD
    attachments: List[str] = Field(default_factory=list)
    visibility_flag: bool = True


class Session(BaseModel):
    session_id: str
    title: str
    start_time: str
    last_active_time: str
    turns: List[Turn]

    @property
    def turn_count(self) -> int:
        return len(self.turns)


class Archive(BaseModel):
    source: str
    sessions: List[Session]


class SessionSummary(BaseModel):
    session_id: str
    title: str
    start_time: str
    last_active_time: str
    turn_count: int
    visible_count: int
