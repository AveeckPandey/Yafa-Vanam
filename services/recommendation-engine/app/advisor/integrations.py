from __future__ import annotations

import os
from typing import Protocol

from .models import BeautyProfile, ExplainRequest, ExplanationResponse, ImageAnalysisRequest, ImageAnalysisResponse, Recommendation


class VisionProvider(Protocol):
    async def analyze(self, request: ImageAnalysisRequest) -> ImageAnalysisResponse: ...


class RagProvider(Protocol):
    async def explain(self, request: ExplainRequest, profile: BeautyProfile, recommendation: Recommendation) -> ExplanationResponse: ...


class DisabledVisionProvider:
    async def analyze(self, request: ImageAnalysisRequest) -> ImageAnalysisResponse:
        return ImageAnalysisResponse(
            status="not_configured", kind=request.kind, analysis=None, confirmation_required=True,
            message="Vision provider is not configured. Configure YAFA_VISION_PROVIDER before enabling selfie/outfit analysis.",
        )


class DisabledRagProvider:
    async def explain(self, request: ExplainRequest, profile: BeautyProfile, recommendation: Recommendation) -> ExplanationResponse:
        positive = [r.detail for r in recommendation.reasons if r.score > 0 and r.detail]
        reason = "; ".join(positive[:3]) if positive else "It ranked highest under the deterministic advisor rules."
        shade = f" in {recommendation.shade.code} {recommendation.shade.name}" if recommendation.shade and recommendation.shade.name else ""
        return ExplanationResponse(
            answer=f"{recommendation.product_name}{shade} was selected because {reason}",
            source="deterministic", citations=[recommendation.product_id] + ([recommendation.variant_id] if recommendation.variant_id else []),
        )


def vision_provider() -> VisionProvider:
    # Provider adapter intentionally explicit: no fake image analysis.
    return DisabledVisionProvider()


def rag_provider() -> RagProvider:
    # The interface is ready for services/rag-assistant; deterministic catalogue-grounded fallback remains safe.
    return DisabledRagProvider()
