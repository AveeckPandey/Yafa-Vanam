import base64
import binascii
import hmac
import os
from typing import Any

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.vision.analyzer import analyse_skin_image
from app.vision.calibration import confidence_threshold

router = APIRouter(prefix="/ai", tags=["internal-yafa"])
MAX_IMAGE_BYTES = 5 * 1024 * 1024


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: dict[str, str] = Field(default_factory=dict)
    selfie_url: HttpUrl | None = None


class AnalyzeImageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    image_base64: str = Field(min_length=4, max_length=7_000_000)


def _require_service_token(token: str | None) -> None:
    expected = os.getenv("YAFA_INTERNAL_SERVICE_TOKEN", "")
    if len(expected) < 32 or token is None or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="unauthorized")


def _response_payload(image: bytes) -> dict[str, Any]:
    result = analyse_skin_image(image)
    threshold = confidence_threshold()
    determined = bool(result.quality_pass and result.shade_candidates and result.confidence is not None and result.confidence >= threshold)
    return {
        "candidates": [{"shade_code": candidate.shade_code, "confidence": candidate.confidence, "reason": "Prepared from your Yafa selfie analysis and quiz preferences."} for candidate in result.shade_candidates[:3]] if determined else [],
        "confidence": result.confidence,
        "confidence_threshold": threshold,
        "cv_used": determined,
        "shade_determined": determined,
        "analysis": result.analysis.model_dump(mode="json") if determined and result.analysis else None,
        "face_detected": result.face_detected,
        "skin_region_ratio": result.skin_region_ratio,
        "issues": result.issues,
    }


async def _download_private_image(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=8.0, follow_redirects=False) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            content_length = response.headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > MAX_IMAGE_BYTES:
                        raise HTTPException(status_code=422, detail="invalid_image")
                except ValueError:
                    raise HTTPException(status_code=422, detail="invalid_image") from None
            chunks: list[bytes] = []
            size = 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > MAX_IMAGE_BYTES:
                    raise HTTPException(status_code=422, detail="invalid_image")
                chunks.append(chunk)
    return b"".join(chunks)


@router.post("/analyze")
async def analyze(request: AnalyzeRequest, x_yafa_service_token: str | None = Header(default=None)) -> dict[str, Any]:
    _require_service_token(x_yafa_service_token)
    if request.selfie_url is None:
        raise HTTPException(status_code=422, detail="selfie_required_for_shade_analysis")
    if request.selfie_url.scheme != "https":
        raise HTTPException(status_code=422, detail="invalid_selfie_url")
    try:
        image = await _download_private_image(str(request.selfie_url))
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=422, detail="selfie_download_failed") from exc
    if len(image) == 0 or len(image) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=422, detail="invalid_image")
    return _response_payload(image)


@router.post("/analyze-image")
async def analyze_image(request: AnalyzeImageRequest, x_yafa_service_token: str | None = Header(default=None)) -> dict[str, Any]:
    """Internal validation endpoint for the consented CV test harness only."""
    _require_service_token(x_yafa_service_token)
    try:
        image = base64.b64decode(request.image_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="invalid_image") from exc
    if len(image) == 0 or len(image) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=422, detail="invalid_image")
    return _response_payload(image)
