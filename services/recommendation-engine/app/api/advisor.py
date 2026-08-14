from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.advisor.integrations import rag_provider, vision_provider
from app.advisor.models import (
    AdvisorSession, AnswerRequest, CreateSessionRequest, ExplainRequest, ExplanationResponse,
    ImageAnalysisRequest, ImageAnalysisResponse, ModifyRequest,
)
from app.advisor.profile import apply_answer, apply_changes
from app.advisor.quiz import next_step
from app.advisor.recommender import recommend
from app.advisor.store import InMemorySessionStore, SessionNotFound

router = APIRouter(prefix="/advisor", tags=["advisor"])
store = InMemorySessionStore()


def _get(session_id: UUID) -> AdvisorSession:
    try:
        return store.get(session_id)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="Advisor session not found") from exc


@router.post("/session", response_model=AdvisorSession)
def create_session(request: CreateSessionRequest) -> AdvisorSession:
    session = AdvisorSession()
    if request.goal:
        apply_answer(session, "goal", request.goal.value)
    session.current_step = next_step(session)
    return store.create(session)


@router.get("/session/{session_id}", response_model=AdvisorSession)
def get_session(session_id: UUID) -> AdvisorSession:
    return _get(session_id)


@router.post("/session/{session_id}/answer", response_model=AdvisorSession)
def answer(session_id: UUID, request: AnswerRequest) -> AdvisorSession:
    session = _get(session_id)
    if session.current_step and request.question_id != session.current_step.id and request.question_id not in {"known_shade", "concealer_mode", "corrector_concern"}:
        raise HTTPException(status_code=409, detail=f"Expected answer for {session.current_step.id}")
    try:
        apply_answer(session, request.question_id, request.answer)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid advisor answer: {exc}") from exc
    session.current_step = next_step(session)
    return store.save(session)


@router.post("/session/{session_id}/recommend", response_model=AdvisorSession)
def make_recommendations(session_id: UUID) -> AdvisorSession:
    session = _get(session_id)
    session.recommendations = recommend(session.profile)
    return store.save(session)


@router.post("/session/{session_id}/modify", response_model=AdvisorSession)
def modify(session_id: UUID, request: ModifyRequest) -> AdvisorSession:
    session = _get(session_id)
    try:
        apply_changes(session, request.changes)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid modification: {exc}") from exc
    session.recommendations = recommend(session.profile)
    session.current_step = next_step(session)
    return store.save(session)


@router.post("/session/{session_id}/image-analysis", response_model=ImageAnalysisResponse)
async def image_analysis(session_id: UUID, request: ImageAnalysisRequest) -> ImageAnalysisResponse:
    _get(session_id)
    if not request.image_url and not request.image_base64:
        raise HTTPException(status_code=422, detail="image_url or image_base64 is required")
    # The provider must return confidence and never infer sensitive traits.
    return await vision_provider().analyze(request)


@router.post("/session/{session_id}/explain", response_model=ExplanationResponse)
async def explain(session_id: UUID, request: ExplainRequest) -> ExplanationResponse:
    session = _get(session_id)
    recommendation = next((r for r in session.recommendations if r.product_id == request.product_id and (not request.variant_id or r.variant_id == request.variant_id)), None)
    if not recommendation:
        raise HTTPException(status_code=404, detail="Recommendation not found in this session")
    return await rag_provider().explain(request, session.profile, recommendation)
