from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional


class Status(str, Enum):
    RESEARCHED = "RESEARCHED"
    SCRIPT_READY = "SCRIPT_READY"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    RENDERING = "RENDERING"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    COMPLETED = "COMPLETED"


class TopicStatus(str, Enum):
    NEW = "NEW"
    SELECTED = "SELECTED"
    REJECTED = "REJECTED"


class Topic(BaseModel):
    id: str
    category: str
    title: str
    hook_fa: str
    description: str
    score: int = Field(ge=0, le=100)
    source_type: str = "evergreen"
    sources: list[str] = Field(default_factory=list)
    status: TopicStatus = TopicStatus.NEW
    approval_token: str


class StoryIn(BaseModel):
    subject: str
    proposed_title: str
    script_fa: str
    estimated_seconds: int = Field(ge=10, le=90)
    sources: list[str] = Field(default_factory=list)
    editorial_notes: Optional[str] = None


class Story(StoryIn):
    id: str
    status: Status = Status.SCRIPT_READY
    approval_token: str
    revision_notes: Optional[str] = None
    render_key: Optional[str] = None
