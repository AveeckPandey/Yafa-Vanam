from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Goal(str, Enum):
    full_look = "full_look"
    complexion = "complexion"
    lips = "lips"
    eyes = "eyes"
    cheeks = "cheeks"
    outfit_match = "outfit_match"
    guide_me = "guide_me"


class Depth(str, Enum):
    fair = "fair"
    light = "light"
    light_medium = "light_medium"
    medium = "medium"
    medium_tan = "medium_tan"
    tan = "tan"
    deep = "deep"
    rich = "rich"


class Undertone(str, Enum):
    cool = "cool"
    neutral = "neutral"
    warm = "warm"
    olive = "olive"


class ComplexionProfile(BaseModel):
    source: Literal["manual", "vision", "known_shade"] | None = None
    depth: Depth | None = None
    undertone: Undertone | None = None
    shade_code: str | None = None
    shade_name: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    confirmed: bool = False


class SkinProfile(BaseModel):
    type: str | None = None


class Preferences(BaseModel):
    coverage: str | None = None
    finish: str | None = None
    style: str | None = None
    colour_family: str | None = None
    lip_finish: str | None = None
    eye_look: str | None = None
    mascara_priority: str | None = None
    concealer_mode: Literal["exact", "spot", "brightening"] | None = None
    corrector_concern: str | None = None


class OutfitProfile(BaseModel):
    dominant_colors: list[str] = Field(default_factory=list)
    secondary_colors: list[str] = Field(default_factory=list)
    temperature: Literal["warm", "cool", "neutral"] | None = None
    saturation: Literal["low", "medium", "high"] | None = None
    brightness: Literal["light", "medium", "dark"] | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class BeautyProfile(BaseModel):
    goal: Goal | None = None
    complexion: ComplexionProfile = Field(default_factory=ComplexionProfile)
    skin: SkinProfile = Field(default_factory=SkinProfile)
    preferences: Preferences = Field(default_factory=Preferences)
    occasion: str | None = None
    outfit: OutfitProfile | None = None


class QuizOption(BaseModel):
    value: str
    label: str
    helper: str | None = None


class QuizStep(BaseModel):
    id: str
    prompt: str
    options: list[QuizOption]
    skippable: bool = False


class ScoreReason(BaseModel):
    rule: str
    score: float
    detail: str | None = None


class ShadeResult(BaseModel):
    code: str | None = None
    name: str | None = None
    hex: str | None = None


class Recommendation(BaseModel):
    category: str
    product_id: str
    product_name: str
    product_slug: str
    variant_id: str | None = None
    shade: ShadeResult | None = None
    score: float
    reason_codes: list[str]
    reasons: list[ScoreReason]
    image: str | None = None
    commerce_validation_required: bool = True


class AdvisorSession(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    profile: BeautyProfile = Field(default_factory=BeautyProfile)
    answers: dict[str, Any] = Field(default_factory=dict)
    current_step: QuizStep | None = None
    recommendations: list[Recommendation] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CreateSessionRequest(BaseModel):
    goal: Goal | None = None


class AnswerRequest(BaseModel):
    question_id: str
    answer: Any


class ModifyRequest(BaseModel):
    changes: dict[str, Any]


class ImageAnalysisRequest(BaseModel):
    kind: Literal["selfie", "outfit"]
    image_url: str | None = None
    image_base64: str | None = None


class ExplainRequest(BaseModel):
    product_id: str
    variant_id: str | None = None
    question: str = "Why did you recommend this?"


class ExplanationResponse(BaseModel):
    answer: str
    source: Literal["catalogue", "rag_provider", "deterministic"]
    citations: list[str] = Field(default_factory=list)


class ImageAnalysisResponse(BaseModel):
    status: Literal["available", "not_configured"]
    kind: str
    analysis: ComplexionProfile | OutfitProfile | None = None
    confirmation_required: bool = True
    message: str
