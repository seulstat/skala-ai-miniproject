"""[계약] /chat/stream SSE 이벤트 (design §5). Lead만 수정한다.

순서:
    RouteDecided → (EvidenceSearched* → CardDrafted → ReviewDone)+ → ApprovalRequired → [DONE]
    RouteDecided → FinalAnswer → [DONE]                      (review / out_of_scope)

- 그래프 노드는 `get_stream_writer()(event.model_dump())`로 보낸다 (A1).
- 라우터는 `to_sse(event)`로 직렬화하고 마지막에 `SSE_DONE`을 보낸다 (A3).
- 화면은 `type`으로 분기한다 (A4). 카드는 토큰 스트리밍하지 않는다.
- 처리 중 예외는 `FinalAnswer(reply=<안내>, error=True)` 후 `[DONE]` — 이벤트 종류를 늘리지 않는다.
"""

import json
import re
from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Field, TypeAdapter

from contracts.schemas import ExpressionCard, Intent, Violation


class RouteDecided(BaseModel):
    type: Literal["RouteDecided"] = "RouteDecided"
    intent: Intent


class EvidenceSearched(BaseModel):
    """Coach가 래퍼 Tool을 호출할 때마다 1개. tool은 contracts.mcp.AGENT_TOOL_NAMES 중 하나."""
    type: Literal["EvidenceSearched"] = "EvidenceSearched"
    tool: str
    query: str = Field(description="검색어. get_job_posting은 섹션 이름")


class CardDrafted(BaseModel):
    type: Literal["CardDrafted"] = "CardDrafted"
    attempt: int = Field(ge=1, description="1 = 첫 초안, 2~ = 재작성")


class ReviewDone(BaseModel):
    type: Literal["ReviewDone"] = "ReviewDone"
    round: int = Field(ge=1)
    passed: bool
    violations: List[Violation] = Field(default_factory=list)


class ApprovalRequired(BaseModel):
    """그래프가 approve에서 interrupt된 상태. 이후 승인·거절은 POST /chat/resume (JSON)."""
    type: Literal["ApprovalRequired"] = "ApprovalRequired"
    card: ExpressionCard
    warning: Optional[str] = None


class FinalAnswer(BaseModel):
    type: Literal["FinalAnswer"] = "FinalAnswer"
    reply: str
    error: bool = False


CoachEvent = Annotated[
    Union[RouteDecided, EvidenceSearched, CardDrafted, ReviewDone, ApprovalRequired, FinalAnswer],
    Field(discriminator="type"),
]
EVENT_ADAPTER: TypeAdapter = TypeAdapter(CoachEvent)

SSE_DONE = "data: [DONE]\n\n"


def to_sse(event: BaseModel) -> str:
    """`data: <json>\\n\\n` 한 덩어리. event: 필드는 쓰지 않는다 (Base web_chat.html 파싱 방식 유지)."""
    return f"data: {json.dumps(event.model_dump(mode='json'), ensure_ascii=False)}\n\n"


def parse_event(data: dict) -> BaseModel:
    return EVENT_ADAPTER.validate_python(data)


# 이벤트 type 시퀀스 검사. 한 글자 코드로 바꿔 정규식으로 순서를 확인한다.
_CODE = {"RouteDecided": "R", "EvidenceSearched": "E", "CardDrafted": "C", "ReviewDone": "V",
         "ApprovalRequired": "A", "FinalAnswer": "F", "[DONE]": "D"}
_ORDER = re.compile(r"R((E*CV)+A|F)D")


def is_valid_sequence(types: list[str]) -> bool:
    """design §5 순서를 만족하는지. 예외 처리용 FinalAnswer(error=True)는 R 직후 또는 E·C·V 뒤에도 허용한다."""
    codes = "".join(_CODE.get(t, "?") for t in types)
    return bool(_ORDER.fullmatch(codes) or re.fullmatch(r"R(E*C?V?)*FD", codes))
