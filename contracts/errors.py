"""[계약] 오류 분류·사용자 메시지·재시도 정책 (ADR-0012). Lead만 수정한다.

강의 p.18 "4-Layer + Graceful Degradation"과 p.174~177 "Transient만 백오프 재시도"를 따른다.

    Tool          MCP 호출. timeout만 재시도(RETRY_*), 실패는 ToolError로 변환       — A1 agent/tools.py, A2
    Orchestration 그래프 노드. Tool 실패는 격리해 계속 진행(fatal=False), LLM 실패는 CoachError — A1
    Application   FastAPI. CoachError → SSE ErrorRaised / REST ErrorResponse, 그 외 예외 → UNEXPECTED_ERROR — A3
    Presentation  화면. code별 user_message 표시, recoverable이면 "다시 시도" 버튼 — A4

- 내부 원인(detail)은 로그·trace에만 남기고, 화면에는 user_message만 보낸다.
- fatal=True면 SSE를 ErrorRaised → [DONE]으로 끝내고, False면 진행하면서 알림(notice)으로만 남긴다.
"""

from dataclasses import dataclass
from typing import Literal, Optional

from pydantic import BaseModel

Layer = Literal["tool", "orchestration", "application", "presentation"]

ErrorCode = Literal[
    "TOOL_TIMEOUT_AFTER_RETRY", "TOOL_EXECUTION_ERROR", "MCP_UNAVAILABLE",
    "LLM_TIMEOUT", "LLM_RATE_LIMIT", "LLM_OUTPUT_INVALID", "REVIEWER_DEGRADED",
    "LLM_AUTH", "MODEL_NOT_FOUND", "NOT_READY", "INPUT_INVALID", "NO_PENDING", "NOT_FOUND",
    "STORE_ERROR", "UNEXPECTED_ERROR", "STREAM_DISCONNECTED",
]

# 재시도 정책 (Tool 계층, asyncio.TimeoutError만): 0.5초 → 1.5초, 최대 2회 재시도 = 3번 시도
RETRY_MAX = 2
RETRY_INITIAL_DELAY = 0.5
RETRY_BACKOFF = 3

# 구조화 로그 공통 필드 (강의 p.236 로그 표준화). 역할마다 필드 이름을 바꾸지 않는다
LOG_FIELDS: tuple[str, ...] = ("thread_id", "node", "tool", "layer", "error_code")


@dataclass(frozen=True)
class ErrorSpec:
    layer: Layer
    recoverable: bool            # 같은 요청을 다시 시도하면 성공할 가능성이 있는가
    fatal: bool                  # 이 요청의 처리를 끝내는가 (False = 알림만 남기고 계속)
    http_status: Optional[int]   # REST 응답 상태 (None = REST로 나가지 않음)
    user_message: str


ERROR_CATALOG: dict[str, ErrorSpec] = {
    "TOOL_TIMEOUT_AFTER_RETRY": ErrorSpec("tool", True, False, 504, "근거 검색이 지연돼 일부 근거 없이 작성했어요."),
    "TOOL_EXECUTION_ERROR": ErrorSpec("tool", False, False, 502, "근거 검색 중 오류가 나서 해당 근거는 빼고 작성했어요."),
    "MCP_UNAVAILABLE": ErrorSpec("tool", True, True, 503, "근거 서버(MCP)에 연결할 수 없어요. 잠시 후 다시 시도해 주세요."),
    "LLM_TIMEOUT": ErrorSpec("orchestration", True, True, 504, "모델 응답이 너무 늦어요. 다시 시도해 주세요."),
    "LLM_RATE_LIMIT": ErrorSpec("orchestration", True, True, 429, "모델 호출 한도에 걸렸어요. 잠시 후 다시 시도해 주세요."),
    "LLM_OUTPUT_INVALID": ErrorSpec(
        "orchestration", True, True, 502, "카드 형식을 만들지 못했어요. 다시 시도하거나 더 큰 모델(QUALITY_MODEL)을 써 주세요."),
    "REVIEWER_DEGRADED": ErrorSpec(
        "orchestration", True, False, None, "AI 검수를 하지 못해 규칙 검사만 적용했어요. 내용을 직접 확인해 주세요."),
    "LLM_AUTH": ErrorSpec("application", False, True, 502, "모델 API 키를 확인해 주세요 (.env)."),
    "MODEL_NOT_FOUND": ErrorSpec("application", False, True, 502, "모델 이름(FAST_MODEL·QUALITY_MODEL)을 확인해 주세요."),
    "NOT_READY": ErrorSpec("application", False, True, 409, "준비 탭에서 프로필·경험 문서·공고를 먼저 입력해 주세요."),
    "INPUT_INVALID": ErrorSpec("application", False, True, 422, "입력 값을 확인해 주세요."),
    "NO_PENDING": ErrorSpec("application", False, True, 409, "승인 대기 중인 카드가 없어요. 이미 처리됐을 수 있어요."),
    "NOT_FOUND": ErrorSpec("application", False, True, 404, "요청한 항목을 찾을 수 없어요."),
    "STORE_ERROR": ErrorSpec("application", True, True, 500, "카드를 저장하지 못했어요. 승인 버튼을 다시 눌러 주세요."),
    "UNEXPECTED_ERROR": ErrorSpec(
        "application", False, True, 500, "예상치 못한 오류가 발생했어요. 계속되면 trace id와 함께 알려 주세요."),
    "STREAM_DISCONNECTED": ErrorSpec(
        "presentation", True, True, None, "서버 연결이 끊겼어요. 승인 대기 중인 카드가 있는지 확인할게요."),
}


class ErrorInfo(BaseModel):
    """화면·SSE·REST로 나가는 오류 정보. 내부 원인은 담지 않는다."""
    code: ErrorCode
    layer: Layer
    recoverable: bool
    fatal: bool
    user_message: str
    trace_id: Optional[str] = None


def error_info(code: ErrorCode, user_message: Optional[str] = None, trace_id: Optional[str] = None) -> ErrorInfo:
    spec = ERROR_CATALOG[code]
    return ErrorInfo(code=code, layer=spec.layer, recoverable=spec.recoverable, fatal=spec.fatal,
                     user_message=user_message or spec.user_message, trace_id=trace_id)


class CoachError(Exception):
    """분류된 오류. detail은 로그용 내부 원인이고 화면에 보내지 않는다."""

    def __init__(self, code: ErrorCode, detail: str = "", user_message: Optional[str] = None):
        self.info = error_info(code, user_message)
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


class ToolError(CoachError):
    """Tool 계층 오류 (강의 p.175 ToolError). with_retry가 timeout 소진·영구 오류를 이것으로 바꾼다."""

    def __init__(self, code: ErrorCode, tool_name: str, detail: str = ""):
        self.tool_name = tool_name
        super().__init__(code, detail)
