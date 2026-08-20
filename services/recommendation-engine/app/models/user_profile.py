from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LabColour(BaseModel):
    L: float
    a: float
    b: float


class SkinProfile(BaseModel):
    shade_code: str | None = None
    depth_family: str | None = None
    undertone: str | None = None
    lab: LabColour | None = None
    ita: float | None = None
    skin_types: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    shade_confidence: float | None = None
    shade_source: Literal["manual", "stored", "computer_vision", "quiz"] | None = None
    user_confirmed: bool = False


class FaceProfile(BaseModel):
    eye_colour: str | None = None
    hair_colour: str | None = None


class MakeupPreferences(BaseModel):
    coverage: str | None = None
    finish: str | None = None
    intensity: str | None = None


class UserBeautyProfile(BaseModel):
    user_id: str | None = None
    skin: SkinProfile = Field(default_factory=SkinProfile)
    face: FaceProfile = Field(default_factory=FaceProfile)
    makeup_preferences: MakeupPreferences = Field(default_factory=MakeupPreferences)
    context: dict = Field(default_factory=dict)
