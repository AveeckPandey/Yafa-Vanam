"""Protected Yafa chat endpoint backed only by product-knowledge RAG."""
from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Header, HTTPException

from app.yafa.orchestrator import handle_chat
from app.yafa.schemas import YafaChatRequest, YafaChatResponse

router = APIRouter(prefix="/internal/yafa", tags=["internal-yafa-rag"])


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
