"""/api/cards · /api/cards/due · /api/cards/{id}/review (contracts.api). 저장 실패·없는 id는 CardStore가 CoachError로 올린다."""

from fastapi import APIRouter, Depends

from contracts.api import CardReviewRequest
from contracts.deps import Deps
from contracts.schemas import SavedCard
from routers.dependencies import get_deps

router = APIRouter(prefix="/api/cards", tags=["cards"])


@router.get("", response_model=list[SavedCard])
async def list_cards(deps: Deps = Depends(get_deps)):
    return await deps.store.list_cards()


@router.get("/due", response_model=list[SavedCard])
async def due_cards(deps: Deps = Depends(get_deps)):
    return await deps.store.due_cards()


@router.post("/{card_id}/review", response_model=SavedCard)
async def review_card(card_id: str, req: CardReviewRequest, deps: Deps = Depends(get_deps)):
    """P1: 안다(known)면 단계+1, 다시(again)면 단계 0 (design §4)."""
    return await deps.store.review(card_id, req.result)
