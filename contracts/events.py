"""[계약] /chat/stream SSE 이벤트 (design §5). Lead만 수정한다.

순서:
    RouteDecided → (EvidenceSearched* → CardDrafted → ReviewDone)+ → ApprovalRequired → [DONE]
    RouteDecided → FinalAnswer → [DONE]                      (review / out_of_scope)
    [RouteDecided → ...] → ErrorRaised → [DONE]              (치명 오류, ADR-0012)

- 그래프 노드는 `get_stream_writer()(event.model_dump())`로 보낸다 (A1).
- 라우터는 `to_sse(event)`로 직렬화하고 마지막에 `SSE_DONE`을 보낸다. 응답 헤더는 `SSE_HEADERS` (A3).
- 화면은 `type`으로 분기한다 (A4). 카드는 토큰 스트리밍하지 않는다.
- 치명 아닌 오류(Tool 실패, 검수 저하)는 해당 이벤트의 `error` 필드로 알리고 흐름을 계속한다 (contracts.errors).
"""

import json
import re
from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Field, TypeAdapter

from contracts.errors import ErrorInfo
from contracts.schemas import ExpressionCard, Intent, Violation


class RouteDecided(BaseModel):
    type: Literal["RouteDecided"] = "RouteDecided"
    intent: Intent


class EvidenceSearched(BaseModel):
    """Coach가 래퍼 Tool을 호출할 때마다 1개. tool은 contracts.mcp_spec.AGENT_TOOL_NAMES 중 하나."""
    type: Literal["EvidenceSearched"] = "EvidenceSearched"
    tool: str
    query: str = Field(description="검색어. get_job_posting은 섹션 이름")
    error: Optional[ErrorInfo] = Field(default=None, description="이 검색만 실패했을 때 (fatal=False, 진행 계속)")


class CardDrafted(BaseModel):
    type: Literal["CardDrafted"] = "CardDrafted"
    attempt: int = Field(ge=1, description="1 = 첫 초안, 2~ = 재작성")


class ReviewDone(BaseModel):
    type: Literal["ReviewDone"] = "ReviewDone"
    round: int = Field(ge=1)
    passed: bool
    violations: List[Violation] = Field(default_factory=list)
    error: Optional[ErrorInfo] = Field(default=None, description="REVIEWER_DEGRADED — LLM 검수 실패로 규칙 검사만 적용")


class ApprovalRequired(BaseModel):
    """그래프가 approve에서 interrupt된 상태. 이후 승인·거절은 POST /chat/resume (JSON)."""
    type: Literal["ApprovalRequired"] = "ApprovalRequired"
    card: ExpressionCard
    warning: Optional[str] = None
    notices: List[ErrorInfo] = Field(default_factory=list, description="이 요청에서 생긴 치명 아닌 오류 모음 (배너 표시용)")


class FinalAnswer(BaseModel):
    type: Literal["FinalAnswer"] = "FinalAnswer"
    reply: str


class ErrorRaised(BaseModel):
    """치명 오류로 처리를 끝낸다. 화면은 error.user_message를 보여 주고 recoverable이면 다시 시도 버튼을 둔다."""
    type: Literal["ErrorRaised"] = "ErrorRaised"
    error: ErrorInfo


CoachEvent = Annotated[
    Union[RouteDecided, EvidenceSearched, CardDrafted, ReviewDone, ApprovalRequired, FinalAnswer, ErrorRaised],
    Field(discriminator="type"),
]
EVENT_ADAPTER: TypeAdapter = TypeAdapter(CoachEvent)

SSE_DONE = "data: [DONE]\n\n"
# 프록시 버퍼링 방지 (강의 p.114). web_server.py 프록시도 버퍼링 없이 그대로 흘려보내야 한다
SSE_HEADERS: dict[str, str] = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


def to_sse(event: BaseModel) -> str:
    """`data: <json>\\n\\n` 한 덩어리. event: 필드는 쓰지 않는다 (Base web_chat.html 파싱 방식 유지)."""
    return f"data: {json.dumps(event.model_dump(mode='json'), ensure_ascii=False)}\n\n"


def parse_event(data: dict) -> BaseModel:
    return EVENT_ADAPTER.validate_python(data)


# 이벤트 type 시퀀스 검사. 한 글자 코드로 바꿔 정규식으로 순서를 확인한다.
_CODE = {"RouteDecided": "R", "EvidenceSearched": "E", "CardDrafted": "C", "ReviewDone": "V",
         "ApprovalRequired": "A", "FinalAnswer": "F", "ErrorRaised": "X", "[DONE]": "D"}
_NORMAL = re.compile(r"R((E*CV)+A|F)D")
_FATAL = re.compile(r"(R[ECV]*)?XD")      # 라우팅 전(NOT_READY 등)이나 처리 중 어디서든 끝날 수 있다


def is_valid_sequence(types: list[str]) -> bool:
    """design §5 순서를 만족하는지."""
    codes = "".join(_CODE.get(t, "?") for t in types)
    return bool(_NORMAL.fullmatch(codes) or _FATAL.fullmatch(codes))
