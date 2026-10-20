"""[계약] fake 데이터. A1(fake MCP·테스트), A4(MOCK=1 응답·SSE 재생)가 같은 파일을 쓴다. Lead만 수정한다.

sse_*.json은 이벤트 dict 목록이고 마지막 원소가 문자열 "[DONE]"이다. 모든 파일은 tests/test_contracts.py가 스키마로 검증한다.
"""

import json
from pathlib import Path
from typing import Any

from contracts import api, schemas

FIXTURE_DIR = Path(__file__).parent

# 파일 → (모델, 목록 여부). sse_*는 contracts.events로 따로 검증한다
FIXTURE_SCHEMAS: dict[str, tuple[type, bool]] = {
    "card_express.json": (schemas.ExpressionCard, False),
    "card_answer.json": (schemas.ExpressionCard, False),
    "review_failed.json": (schemas.ReviewResult, False),
    "review_passed.json": (schemas.ReviewResult, False),
    "approval_request.json": (schemas.ApprovalRequest, False),
    "approval_request_warning.json": (schemas.ApprovalRequest, False),
    "saved_cards.json": (schemas.SavedCard, True),
    "profile.json": (schemas.UserProfile, False),
    "posting_draft.json": (schemas.PostingDraft, False),
    "docs.json": (api.DocInfo, True),
    "readiness.json": (api.ReadinessResponse, False),
    "pending.json": (api.PendingResponse, False),
    "pending_none.json": (api.PendingResponse, False),
    "resume_saved.json": (api.ResumeResponse, False),
    "resume_rejected.json": (api.ResumeResponse, False),
    "error_response.json": (api.ErrorResponse, False),
}
SSE_FIXTURES: tuple[str, ...] = (
    "sse_express_approve.json", "sse_express_warning.json", "sse_answer_approve.json",
    "sse_review.json", "sse_out_of_scope.json",
    "sse_evidence_degraded.json", "sse_error_recoverable.json", "sse_error_not_ready.json",
)


def load(name: str) -> Any:
    """JSON 그대로 (dict 또는 list)."""
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def load_model(name: str):
    """FIXTURE_SCHEMAS에 등록된 모델 인스턴스(목록이면 list)로."""
    model, many = FIXTURE_SCHEMAS[name]
    data = load(name)
    return [model.model_validate(d) for d in data] if many else model.model_validate(data)
