from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

TurnKind = Literal["prompted", "created", "gave", "selected", "other"]


class Turn(BaseModel):
    id: str
    timestamp: str  # YYYY-MM-DD HH:mm:ss
    timestamp_utc: str  # original ISO-8601 from Takeout
    kind: TurnKind = "prompted"
    prompt: str = ""
    response_md: str = ""
    response_html: str = ""
    attachments: List[str] = Field(default_factory=list)
    visibility_flag: bool = True


class Session(BaseModel):
    id: str
    title: str
    start: str  # YYYY-MM-DD HH:mm:ss of first turn
    end: str  # YYYY-MM-DD HH:mm:ss of last turn
    turns: List[Turn]

    @property
    def turn_count(self) -> int:
        return len(self.turns)


class Archive(BaseModel):
    source: str  # path to the raw folder
    sessions: List[Session]


class SessionSummary(BaseModel):
    id: str
    title: str
    start: str
    end: str
    turn_count: int
    visible_count: int
