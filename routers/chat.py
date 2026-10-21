"""/chat/stream(SSE) · /chat/resume(JSON) · /chat/pending (contracts.events, contracts.api, ADR-0006·0012·0014).

스트림은 어느 지점에서 실패해도 ErrorRaised → [DONE]으로 끝난다. 이미 헤더가 나간 뒤라 HTTP 상태를 바꿀 수 없기 때문이다.
승인·거절(resume)과 승인 대기 조회(pending)는 REST라서 오류가 ErrorResponse + 코드별 상태로 나간다.
"""

import asyncio
from collections import defaultdict
from typing import AsyncIterator, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from contracts.api import PendingResponse, ResumeRequest, ResumeResponse
from contracts.deps import Deps
from contracts.errors import CoachError
from contracts.events import SSE_DONE, SSE_HEADERS, ErrorRaised, parse_event, to_sse
from contracts.schemas import ApprovalRequest
from contracts.state import NODE_SAVE, ResumeValue
from routers.dependencies import get_deps, get_graph, get_thread_locks
from services.errors import report_error
from services.readiness import check_readiness

router = APIRouter(prefix="/chat", tags=["chat"])

# 같은 thread에서 새 메시지를 보낼 때 이전 턴의 값이 남아 새 카드에 섞이지 않게 비운다 (ADR-0017)
FRESH_TURN = {"review": None, "warning": None, "saved_card_id": None, "next_review": None}


def _config(thread_id: str, **extra) -> dict:
    return {"configurable": {"thread_id": thread_id}, **extra}


async def _pending_request(graph: CompiledStateGraph, thread_id: str) -> Optional[ApprovalRequest]:
    """체크포인터에 남은 interrupt payload. 서버를 재시작해도 같은 checkpoints.db면 그대로 돌아온다."""
    state = await graph.aget_state(_config(thread_id))
    if not state.interrupts:
        return None
    return ApprovalRequest.model_validate(state.interrupts[0].value)


async def _event_stream(deps: Deps, graph: CompiledStateGraph, message: str, thread_id: str) -> AsyncIterator[str]:
    try:
        readiness = await check_readiness(deps.paths)
        if not readiness.ready:
            problems = "; ".join(f"{i.item}: {i.message}" for i in readiness.items if i.status == "error")
            raise CoachError("NOT_READY", detail=problems)
        config = _config(thread_id, run_name="chat_stream", metadata={"thread_id": thread_id})
        async for payload in graph.astream({"user_input": message, **FRESH_TURN}, config, stream_mode="custom"):
            yield to_sse(parse_event(payload))
    except Exception as e:   # 치명 오류: 스트림을 ErrorRaised로 끝낸다. 내부 원인은 report_error가 로그에만 남긴다
        yield to_sse(ErrorRaised(error=report_error(e, thread_id=thread_id)))
    yield SSE_DONE


@router.get("/stream")
async def stream(
    message: str = Query(min_length=1, description="사용자 입력 (한국어 문장 또는 면접 질문)"),
    thread_id: str = Query("default", min_length=1),
    deps: Deps = Depends(get_deps),
    graph: CompiledStateGraph = Depends(get_graph),
):
    if not message.strip():
        raise CoachError("INPUT_INVALID", detail="빈 메시지")
    return StreamingResponse(_event_stream(deps, graph, message, thread_id),
                             media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/resume", response_model=ResumeResponse)
async def resume(
    req: ResumeRequest,
    graph: CompiledStateGraph = Depends(get_graph),
    locks: defaultdict[str, asyncio.Lock] = Depends(get_thread_locks),
):
    """승인(approve=true)이면 저장하고, 거절이면 저장하지 않는다. 승인 대기가 없으면 409 NO_PENDING."""
    config = _config(req.thread_id)
    async with locks[req.thread_id]:   # 승인 버튼 연타로 같은 카드가 두 번 처리되지 않게 직렬화
        state = await graph.aget_state(config)
        if state.interrupts:
            result = await graph.ainvoke(Command(resume=ResumeValue(approve=req.approve)), config)
        elif req.approve and state.next == (NODE_SAVE,):   # 승인은 끝났는데 저장이 실패한 상태(STORE_ERROR) — 저장만 다시 시도 (ADR-0017)
            result = await graph.ainvoke(None, config)
        else:
            raise CoachError("NO_PENDING", detail=f"thread_id={req.thread_id}")
    if not req.approve:
        return ResumeResponse(saved=False)
    return ResumeResponse(saved=True, card_id=result["saved_card_id"], next_review=result["next_review"])


@router.get("/pending", response_model=PendingResponse)
async def pending(thread_id: str = Query("default", min_length=1), graph: CompiledStateGraph = Depends(get_graph)):
    return PendingResponse(thread_id=thread_id, pending=await _pending_request(graph, thread_id))
