"""MOCK=1 백엔드 (담당 A4). 백엔드 없이 contracts/fixtures로 ROUTES 전체에 응답한다.

- 상태(프로필·문서·카드·승인 대기)는 프로세스 메모리에만 둔다. 재시작하면 fixture 상태로 돌아간다.
- /chat/stream은 sse_*.json을 이벤트 사이 MOCK_DELAY초 간격으로 재생한다. 시나리오는 메시지의 #태그로 고른다(SCENARIOS).
- 응답 본문이 계약에 없는 PUT·POST·DELETE는 OkResponse/DocInfo 모양으로 답한다. 화면은 본문을 쓰지 않는다.
"""

import asyncio
import functools
import json
import os
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

from contracts.api import (
    ROUTES,
    CardReviewRequest,
    DocInfo,
    DocUpload,
    ErrorResponse,
    OkResponse,
    PostingNormalizeRequest,
    PostingSaveRequest,
    ResumeRequest,
)
from contracts.errors import ERROR_CATALOG, CoachError, ErrorInfo
from contracts.events import SSE_DONE, SSE_HEADERS
from contracts.fixtures import load
from contracts.schemas import REVIEW_INTERVALS_DAYS, ApprovalRequest, ReviewResult, SavedCard, UserProfile
from web.mock_scenarios import MOCK_CHIPS, pick


def _error(info: ErrorInfo) -> JSONResponse:
    body = ErrorResponse(error=info).model_dump(mode="json")
    return JSONResponse(body, status_code=ERROR_CATALOG[info.code].http_status or 500)


def _guard(fn):
    """CoachError를 계약의 ErrorResponse + 코드별 HTTP 상태로 바꾼다 (ADR-0012)."""
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except CoachError as e:
            return _error(e.info)
    return wrapper


async def _parse(request: Request, model):
    try:
        return model.model_validate(await request.json())
    except (ValidationError, ValueError) as e:
        raise CoachError("INPUT_INVALID", str(e)) from e


def create_mock_router(delay: float | None = None) -> APIRouter:
    delay = float(os.environ.get("MOCK_DELAY", "0.5")) if delay is None else delay
    profile, docs, cards = load("profile.json"), load("docs.json"), load("saved_cards.json")
    pending = {"demo-thread-1": load("pending.json")["pending"]}     # ?thread_id=demo-thread-1로 복원 시연
    seen: set[tuple[str, str]] = set()
    router = APIRouter()

    def approval_request(event: dict, review: dict | None) -> dict:
        result = ReviewResult(passed=review["passed"], violations=review["violations"], feedback="") if review else None
        return ApprovalRequest(card=event["card"], warning=event.get("warning"), review=result,
                               notices=event.get("notices", [])).model_dump(mode="json")

    async def replay(seq: list, thread_id: str, cut: int | None):
        review = None
        for i, event in enumerate(seq):
            await asyncio.sleep(delay)
            if event == "[DONE]":
                yield SSE_DONE
                continue
            review = event if event["type"] == "ReviewDone" else review
            if event["type"] == "ApprovalRequired":
                pending[thread_id] = approval_request(event, review)
            if cut is not None and i >= cut:
                return                                  # 연결만 끊는다 ([DONE] 없이 종료)
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    async def chat_stream(request: Request):
        message, thread_id = request.query_params.get("message", ""), request.query_params.get("thread_id", "")
        if not message or not thread_id:
            raise CoachError("INPUT_INVALID")
        first = (thread_id, message) not in seen
        seen.add((thread_id, message))
        name = "sse_answer_approve.json" if "#error" in message and not first else pick(message)
        seq, cut = load(name), None
        if "#disconnect" in message:        # 승인 대기는 만들어 두고 ApprovalRequired 앞에서 연결을 끊는다
            cut = next(i for i, e in enumerate(seq) if e != "[DONE]" and e["type"] == "ApprovalRequired")
        elif "#drop" in message and first:  # 대기 없이 중간에 끊긴다
            cut = 2
        return StreamingResponse(replay(seq, thread_id, cut), media_type="text/event-stream", headers=SSE_HEADERS)

    async def chat_resume(request: Request):
        body = await _parse(request, ResumeRequest)
        req = pending.pop(body.thread_id, None)
        if req is None:
            return JSONResponse(load("error_response.json"), status_code=409)
        if not body.approve:
            return load("resume_rejected.json")
        today = date.today()
        saved = SavedCard(**req["card"], id=f"C{len(cards) + 1:04d}", created=str(today),
                          next_review=str(today + timedelta(days=REVIEW_INTERVALS_DAYS[0])))
        cards.append(saved.model_dump(mode="json"))
        return load("resume_saved.json") | {"card_id": saved.id, "next_review": saved.next_review}

    async def chat_pending(request: Request):
        thread_id = request.query_params.get("thread_id")
        if not thread_id:
            raise CoachError("INPUT_INVALID")
        return {"thread_id": thread_id, "pending": pending.get(thread_id)}

    async def put_profile(request: Request):
        profile.update((await _parse(request, UserProfile)).model_dump(mode="json"))
        return OkResponse()

    async def add_doc(request: Request):
        body = await _parse(request, DocUpload)
        docs[:] = [d for d in docs if d["name"] != body.name]
        info = DocInfo(name=body.name, chars=len(body.content), updated=datetime.now().astimezone().isoformat())
        docs.append(info.model_dump())
        return info

    async def delete_doc(name: str):
        if not any(d["name"] == name for d in docs):
            raise CoachError("NOT_FOUND")
        docs[:] = [d for d in docs if d["name"] != name]
        return OkResponse()

    async def save_posting(request: Request):
        await _parse(request, PostingSaveRequest)
        return OkResponse()

    async def normalize_posting(request: Request):
        await _parse(request, PostingNormalizeRequest)
        return load("posting_draft.json")

    async def get_profile():
        return profile

    async def list_docs():
        return docs

    async def readiness():
        return load("readiness.json")

    async def list_cards():
        return cards

    async def due_cards():
        return [c for c in cards if c["next_review"] <= str(date.today())]

    async def review_card(card_id: str, request: Request):
        body = await _parse(request, CardReviewRequest)
        card = next((c for c in cards if c["id"] == card_id), None)
        if card is None:
            raise CoachError("NOT_FOUND")
        card["stage"] = min(card["stage"] + 1, len(REVIEW_INTERVALS_DAYS) - 1) if body.result == "known" else 0
        card["next_review"] = str(date.today() + timedelta(days=REVIEW_INTERVALS_DAYS[card["stage"]]))
        return card

    handlers = {
        "get_profile": get_profile, "put_profile": put_profile,
        "list_docs": list_docs, "add_doc": add_doc, "delete_doc": delete_doc,
        "normalize_posting": normalize_posting, "save_posting": save_posting, "readiness": readiness,
        "chat_stream": chat_stream, "chat_resume": chat_resume, "chat_pending": chat_pending,
        "list_cards": list_cards, "due_cards": due_cards, "review_card": review_card,
    }
    assert set(handlers) == set(ROUTES), "ROUTES와 mock 핸들러가 어긋남"
    for name, fn in handlers.items():
        method, path = ROUTES[name]
        router.add_api_route(path, _guard(fn), methods=[method])

    async def mock_info():
        return {"mock": True, "chips": [{"label": label, "message": msg} for label, msg in MOCK_CHIPS]}

    router.add_api_route("/mock-info", mock_info, methods=["GET"])
    return router

