from __future__ import annotations

from pydantic import BaseModel, Field

from .user_profile import LabColour


class ShadeCandidate(BaseModel):
    shade_code: str
    shade_name: str
    role: str
    colour_distance: float
    confidence: float = Field(ge=0, le=1)


class SkinAnalysis(BaseModel):
    lab: LabColour
    ita: float
    depth_family: str
    undertone: str


class SkinAnalysisResult(BaseModel):
    quality_pass: bool
    face_detected: bool = False
    issues: list[str] = Field(default_factory=list)
    retake_required: bool = False
    analysis: SkinAnalysis | None = None
    shade_candidates: list[ShadeCandidate] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
