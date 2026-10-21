"""Application 계층 오류 변환 (ADR-0012). 예외 → 화면용 ErrorInfo(trace_id 포함) + 구조화 로그.

화면·SSE·REST로 나가는 건 user_message뿐이고, 내부 원인(detail)은 LOG_FIELDS 형식으로 로그에만 남긴다.
"""

import logging
import uuid
from typing import Optional

from contracts.errors import ERROR_CATALOG, LOG_FIELDS, CoachError, ErrorInfo

logger = logging.getLogger("coach.api")


def as_coach_error(exc: BaseException) -> CoachError:
    """분류된 오류는 그대로, 그 외 예외는 UNEXPECTED_ERROR로 감싼다."""
    if isinstance(exc, CoachError):
        return exc
    return CoachError("UNEXPECTED_ERROR", detail=f"{type(exc).__name__}: {exc}")


def http_status(info: ErrorInfo) -> int:
    """REST 응답 상태. 카탈로그에 상태가 없는 코드(REST로 나가지 않는 코드)는 500."""
    return ERROR_CATALOG[info.code].http_status or 500


def report_error(exc: BaseException, *, thread_id: Optional[str] = None) -> ErrorInfo:
    """로그에 내부 원인을 남기고, trace_id를 붙인 ErrorInfo를 돌려준다."""
    err = as_coach_error(exc)
    trace_id = uuid.uuid4().hex[:12]
    fields = {"thread_id": thread_id, "node": None, "tool": getattr(err, "tool_name", None),
              "layer": err.info.layer, "error_code": err.info.code}
    line = " ".join(f"{name}={fields[name]}" for name in LOG_FIELDS)
    # 입력 오류·없는 항목처럼 호출자가 고칠 수 있는 오류(4xx)는 경고, 서버 쪽 오류만 스택까지 남긴다
    server_side = http_status(err.info) >= 500
    logger.log(logging.ERROR if server_side else logging.WARNING, "trace_id=%s %s detail=%s",
               trace_id, line, err.detail, exc_info=exc if server_side else None)
    return err.info.model_copy(update={"trace_id": trace_id})
