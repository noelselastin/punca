"""JSON schemas for every LLM call (README section 9: structured outputs only)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class MapResult(BaseModel):
    conceptId: str = Field(description="Exactly one concept id from the list")
    justification: str = Field(description="One sentence, under 25 words")
    confidence: float = Field(description="0 to 1")


class Remediation(BaseModel):
    explanation: str = Field(description="120-180 words, plain language, built only from the course material")
    keyPoints: list[str] = Field(description="Exactly three short points")
    sourceIds: list[str] = Field(description="sourceIds of the passages used")
    foundInCourseMaterial: bool
