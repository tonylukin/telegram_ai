from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError
from typing import Any, Literal, List, Dict


MemoryType = Literal["fact", "preference", "episode", "project"]


class ExtractedMemory(BaseModel):
    type: MemoryType
    text: str = Field(min_length=1, max_length=600)
    importance: float = Field(ge=0.0, le=1.0)


class ExtractPayload(BaseModel):
    memories: List[ExtractedMemory] = Field(default_factory=list)
    profile_patch: Dict[str, Any] = Field(default_factory=dict)


def parse_extract_payload(raw: str) -> ExtractPayload:
    try:
        return ExtractPayload.model_validate_json(raw)
    except ValidationError:
        return ExtractPayload(memories=[], profile_patch={})
    except Exception:
        return ExtractPayload(memories=[], profile_patch={})
