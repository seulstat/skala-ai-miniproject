"""[계약] REST 요청·응답 모델과 경로 (design §5). Lead만 수정한다.

- 프로필 본문은 contracts.schemas.UserProfile 그대로 (잘못된 enum → FastAPI 기본 422, 테스트 9).
- 카드 응답은 contracts.schemas.SavedCard, 승인 대기는 contracts.schemas.ApprovalRequest.
- 업로드는 multipart 없이 JSON (ADR-0007).
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from contracts.schemas import ApprovalRequest, ReviewOutcome

# (메서드, 경로). A3 라우터와 A4 api.js·MOCK 서버가 같은 경로를 쓴다
ROUTES: dict[str, tuple[str, str]] = {
    "get_profile": ("GET", "/api/profile"),
    "put_profile": ("PUT", "/api/profile"),
    "list_docs": ("GET", "/api/docs"),
    "add_doc": ("POST", "/api/docs"),
    "delete_doc": ("DELETE", "/api/docs/{name}"),
    "normalize_posting": ("POST", "/api/posting/normalize"),
    "save_posting": ("PUT", "/api/posting"),
    "readiness": ("GET", "/api/readiness"),
    "chat_stream": ("GET", "/chat/stream"),        # ?message=&thread_id= → SSE (contracts.events)
    "chat_resume": ("POST", "/chat/resume"),
    "chat_pending": ("GET", "/chat/pending"),      # ?thread_id=
    "list_cards": ("GET", "/api/cards"),
    "due_cards": ("GET", "/api/cards/due"),
    "review_card": ("POST", "/api/cards/{card_id}/review"),   # P1
}


class OkResponse(BaseModel):
    ok: bool = True


# ---------- 경험 문서 ----------

class DocUpload(BaseModel):
    """브라우저 FileReader로 읽은 .md 텍스트."""
    name: str = Field(pattern=r"^[^/\\]+\.md$", description="파일 이름만 (경로 구분자 불가)")
    content: str = Field(min_length=1)


class DocInfo(BaseModel):
    name: str
    chars: int
    updated: str = Field(description="ISO 8601 수정 시각")


# ---------- 공고 ----------

class PostingNormalizeRequest(BaseModel):
    text: str = Field(min_length=1, description="붙여넣거나 업로드한 공고 원문")
# 응답: contracts.schemas.PostingDraft


class PostingSaveRequest(BaseModel):
    markdown: str = Field(min_length=1, description="사용자가 확인·수정한 `## 섹션` 형식 공고")


# ---------- 준비 점검 ----------

class ReadinessItem(BaseModel):
    item: str = Field(description='점검 항목. 예: "프로필", "경험 문서", "공고", "개인정보"')
    status: Literal["ok", "warn", "error"]
    message: str


class ReadinessResponse(BaseModel):
    ready: bool = Field(description="error 항목이 하나도 없으면 true (warn은 허용)")
    items: List[ReadinessItem]


# ---------- 코치 (HITL) ----------

class ResumeRequest(BaseModel):
    thread_id: str
    approve: bool


class ResumeResponse(BaseModel):
    saved: bool
    card_id: Optional[str] = None
    next_review: Optional[str] = None


class PendingResponse(BaseModel):
    """GET /chat/pending 응답. 승인 대기가 없으면 pending=null."""
    thread_id: str
    pending: Optional[ApprovalRequest] = None


# ---------- 카드 ----------

class CardReviewRequest(BaseModel):
    result: ReviewOutcome
# 카드 목록·due 응답: List[contracts.schemas.SavedCard], review 응답: SavedCard
