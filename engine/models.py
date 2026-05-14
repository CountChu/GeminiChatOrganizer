from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field

TurnKind = Literal["prompted", "created", "gave", "selected", "other"]

TITLE_MAX_CHARS = 20


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class Turn(_CamelModel):
    turn_id: str = Field(alias="turnId")
    timestamp: str  # YYYY-MM-DD HH:mm:ss (local)
    timestamp_utc: str = Field(alias="timestampUtc")  # original ISO-8601 from Takeout
    kind: TurnKind = "prompted"
    prompt: str = ""
    prompt2: str = ""
    response: str = ""  # raw HTML from Gemini; the Renderer turns this into MD
    attachments: List[str] = Field(default_factory=list)
    visibility_flag: bool = Field(default=True, alias="visibilityFlag")
    collapse_flag: bool = Field(default=False, alias="collapseFlag")
    missing: bool = False

    @property
    def display_prompt(self) -> str:
        return self.prompt2 or self.prompt


class Session(_CamelModel):
    session_id: str = Field(alias="sessionId")
    start_time: str = Field(alias="beginTime")
    last_active_time: str = Field(alias="endTime")
    turns: List[Turn]

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    @computed_field
    @property
    def title(self) -> str:
        # First visible Turn's prompt2/prompt wins.
        for t in self.turns:
            if not t.visibility_flag:
                continue
            if t.prompt2:
                return t.prompt2
            if t.prompt:
                line = " ".join(t.prompt.strip().splitlines())
                if line:
                    return line[:TITLE_MAX_CHARS]
        # Fully-hidden Session: fall back to first Turn (any visibility) so it
        # still has a recognizable name in tooling and exports.
        if self.turns:
            t = self.turns[0]
            if t.prompt2:
                return t.prompt2
            if t.prompt:
                line = " ".join(t.prompt.strip().splitlines())
                if line:
                    return line[:TITLE_MAX_CHARS]
        return "(untitled)"


class Archive(_CamelModel):
    source: str
    sessions: List[Session]


class SessionSummary(_CamelModel):
    session_id: str = Field(alias="sessionId")
    title: str
    start_time: str = Field(alias="beginTime")
    last_active_time: str = Field(alias="endTime")
    turn_count: int = Field(alias="turnCount")
    visible_count: int = Field(alias="visibleCount")
    missing_count: int = Field(default=0, alias="missingCount")
    topic_id: Optional[str] = Field(default=None, alias="topicId")


class Topic(_CamelModel):
    topic_id: str = Field(alias="topicId")
    name: str
    description: str = ""
    session_ids: List[str] = Field(default_factory=list, alias="sessionIds")
    tags: List[str] = Field(default_factory=list)
    created_at: str = Field(alias="created")  # YYYY-MM-DD HH:mm:ss
    updated_at: Optional[str] = Field(default=None, alias="updated")
    begin_time: Optional[str] = Field(default=None, alias="beginTime")  # min(beginTime) over members
    end_time: Optional[str] = Field(default=None, alias="endTime")      # max(endTime) over members


class TopicSummary(_CamelModel):
    topic_id: str = Field(alias="topicId")
    name: str
    session_count: int = Field(alias="sessionCount")
    created_at: str = Field(alias="created")
    begin_time: Optional[str] = Field(default=None, alias="beginTime")
    end_time: Optional[str] = Field(default=None, alias="endTime")
