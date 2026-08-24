"""Internal Yafa endpoints (Phase 2 §35 / Phase 3 §41).

All routes are protected by the shared internal service token. The Go backend
is the only intended caller; responses never include embeddings, credentials,
stack traces or provider details.
"""
from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.vision.outfit import analyse_outfit_image
from app.yafa.orchestrator import handle_chat, handle_recommend
from app.yafa.schemas import YafaChatRequest, YafaChatResponse

router = APIRouter(prefix="/internal/yafa", tags=["internal-yafa-chat"])

MAX_AUDIO_BYTES = 25 * 1024 * 1024


def _require_service_token(token: str | None) -> None:
    expected = os.getenv("YAFA_INTERNAL_SERVICE_TOKEN", "")
    if len(expected) < 32 or token is None or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="unauthorized")


@router.post("/chat", response_model=YafaChatResponse)
async def yafa_chat(
    request: YafaChatRequest,
    x_yafa_service_token: str | None = Header(default=None),
) -> YafaChatResponse:
    _require_service_token(x_yafa_service_token)
    return await handle_chat(request)


@router.post("/recommend")
async def yafa_recommend(
    payload: dict,
    x_yafa_service_token: str | None = Header(default=None),
) -> dict:
    _require_service_token(x_yafa_service_token)
    return handle_recommend(payload)


# --- Phase 3: multimodal tools -------------------------------------------------


@router.post("/vision/outfit")
async def yafa_outfit_vision(
    image: UploadFile = File(...),
    x_yafa_service_token: str | None = Header(default=None),
) -> dict:
    """Outfit photo -> structured styling attributes ONLY.

    Never selects products; the attributes feed the recommendation engines.
    The raw upload is processed in memory and discarded.
    """
    _require_service_token(x_yafa_service_token)
    data = await image.read()
    if not data or len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="invalid_image")
    try:
        return await run_in_threadpool(analyse_outfit_image, data)
    except ValueError as error:
        raise HTTPException(status_code=422, detail="invalid_image") from error


@router.post("/speech/transcribe")
async def yafa_speech_transcribe(
    audio: UploadFile = File(...),
    x_yafa_service_token: str | None = Header(default=None),
) -> dict:
    """Faster-Whisper speech -> text ONLY (spec Phase 3 §22).

    Raw audio lives only for the duration of this request; nothing is written
    to disk and no transcript log retains audio.
    """
    _require_service_token(x_yafa_service_token)
    content_type = (audio.content_type or "").lower()
    if content_type and not (
        content_type.startswith("audio/") or content_type == "application/octet-stream"
    ):
        raise HTTPException(status_code=415, detail="unsupported_media_type")
    data = await audio.read()
    if not data or len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=422, detail="invalid_audio")

    from app.speech.transcriber import TranscriptionUnavailable, get_transcriber

    try:
        transcriber = get_transcriber()
    except TranscriptionUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    text, language, duration_ms = await run_in_threadpool(transcriber.transcribe, data)
    # `data` goes out of scope here — the recording is never persisted.
    return {"text": text, "language": language, "duration_ms": duration_ms}
