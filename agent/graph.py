# 출처: skala-ai-agent/practice/dapdap/graph.py (Phase 0 복사 후 Supervisor + 서브그래프 구조로 재작성, ADR-0004)
"""Supervisor 메인 그래프. router → coach → reviewer ⟲(MAX_REWRITES) → approve(interrupt) → save/rejected,
review_cards, out_of_scope (design §2). 노드는 모두 async, 이벤트는 contracts.events로 get_stream_writer() 전송.

오류 처리(ADR-0012): 노드는 치명 오류를 CoachError로 raise만 한다. SSE ErrorRaised·REST ErrorResponse로
바꾸는 건 Application 계층(A3)의 책임이다. Tool 실패 중 치명 아닌 것은 agent/tools.py가 이미 격리한다.
"""

import asyncio
import functools
import json
from datetime import date

from langchain_core.messages import HumanMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from agent import llm as llm_module
from agent.coach_agent import build_coach_agent
from agent.reviewer_agent import build_reviewer_agent
from agent.routing import NODE_BUMP_RETRY, route_approval, route_intent, route_review
from contracts import events, schemas
from contracts.deps import Deps
from contracts.errors import CoachError, ErrorInfo
from contracts.state import (
    MAX_REWRITES,
    NODE_APPROVE,
    NODE_COACH,
    NODE_OUT_OF_SCOPE,
    NODE_REJECTED,
    NODE_REVIEW_CARDS,
    NODE_REVIEWER,
    NODE_ROUTER,
    NODE_SAVE,
    AgentState,
)

ROUTER_PROMPT = """당신은 영어 면접 준비 도우미의 요청 분류기입니다. 사용자 입력을 하나로 분류하세요.
- express: 한국어(또는 섞인) 문장을 면접·업무에서 영어로 어떻게 말할지 묻는 경우. "~영어로 뭐야" 없이 문장만 줘도 express.
- answer: 면접 질문(영어 또는 한국어)을 주고 그에 대한 답변을 원하는 경우. "면접 질문:", 의문형 면접 질문.
- review: 저장한 카드·표현을 복습/퀴즈하고 싶은 경우.
- out_of_scope: 영어 면접 표현·답변·복습과 무관한 요청 (일상 잡담, 코드 작성 요청 등)."""


async def _router(state: AgentState, deps: Deps) -> AgentState:
    writer = get_stream_writer()
    try:
        route = await deps.fast_llm.with_structured_output(schemas.Route).ainvoke(
            [("system", ROUTER_PROMPT), ("human", state["user_input"])]
        )
    except Exception as e:
        raise llm_module.classify_llm_error(e) from e
    if route is None:   # 모델이 구조화 출력을 비워 보냄 (ADR-0018)
        raise CoachError("LLM_OUTPUT_INVALID", detail="router: 빈 구조화 출력")
    writer(events.RouteDecided(intent=route.intent).model_dump())
    # 새 턴: 이전 턴의 검수·경고·저장 결과를 비운다 (ADR-0017 1번을 그래프 쪽에서도 보장)
    return {"intent": route.intent, "retry_count": 0, "tools_used": [], "review_log": [], "notices": [],
            "review": None, "warning": None, "saved_card_id": None, "next_review": None}


async def _coach(state: AgentState, deps: Deps) -> AgentState:
    writer = get_stream_writer()
    profile_text = await asyncio.to_thread(deps.paths.profile.read_text, encoding="utf-8")
    profile = schemas.UserProfile.model_validate_json(profile_text)
    known = await deps.store.known_chunks()
    notices: list[ErrorInfo] = []
    used: list[dict] = []
    agent = build_coach_agent(deps, profile, known, state["intent"], writer, notices, used)

    request = state["user_input"]
    if state.get("review") and not state["review"]["passed"]:
        request += (
            "\n\n[이전 카드]\n" + json.dumps(state["card"], ensure_ascii=False)
            + "\n\n[검수 피드백 — 반드시 반영해 다시 작성]\n" + json.dumps(state["review"], ensure_ascii=False)
        )
    try:
        result = await agent.ainvoke({"messages": [HumanMessage(request)]})
    except CoachError:
        raise
    except Exception as e:
        raise llm_module.classify_llm_error(e) from e

    if result.get("structured_response") is None:   # ADR-0018
        raise CoachError("LLM_OUTPUT_INVALID", detail="coach: 빈 구조화 출력")
    card = result["structured_response"].model_dump()
    card["mode"] = state["intent"]
    attempt = state.get("retry_count", 0) + 1
    writer(events.CardDrafted(attempt=attempt).model_dump())
    return {
        "card": card,
        "tools_used": state.get("tools_used", []) + used,
        "notices": state.get("notices", []) + [n.model_dump() for n in notices],
    }


async def _reviewer(state: AgentState, deps: Deps) -> AgentState:
    writer = get_stream_writer()
    sub = build_reviewer_agent(deps)
    result = await sub.ainvoke({"card": state["card"]})
    review = result["review"]
    error = result.get("error")
    round_ = state.get("retry_count", 0) + 1
    violations = [schemas.Violation.model_validate(v) for v in review["violations"]]
    writer(events.ReviewDone(round=round_, passed=review["passed"], violations=violations, error=error).model_dump())

    update: AgentState = {
        "review": review,
        "review_log": state.get("review_log", []) + [{"round": round_, "passed": review["passed"],
                                                        "violations": review["violations"]}],
    }
    if error:
        update["notices"] = state.get("notices", []) + [error]
    if not review["passed"] and state.get("retry_count", 0) >= MAX_REWRITES:
        update["warning"] = f"재작성 {MAX_REWRITES}회 후에도 검수 미통과: " + "; ".join(
            f"{v['rule_id']} '{v['quote']}'" for v in review["violations"]
        )
    return update


async def _bump_retry(state: AgentState, deps: Deps) -> AgentState:
    return {"retry_count": state.get("retry_count", 0) + 1}


async def _approve(state: AgentState, deps: Deps) -> AgentState:
    writer = get_stream_writer()
    req = schemas.ApprovalRequest(
        card=schemas.ExpressionCard.model_validate(state["card"]),
        warning=state.get("warning"),
        review=schemas.ReviewResult.model_validate(state["review"]) if state.get("review") else None,
        notices=[ErrorInfo.model_validate(n) for n in state.get("notices", [])],
    )
    writer(events.ApprovalRequired(card=req.card, warning=req.warning, notices=req.notices).model_dump())
    decision = interrupt(req.model_dump())
    return {"approved": bool(decision.get("approve"))}


async def _save(state: AgentState, deps: Deps) -> AgentState:
    card = schemas.ExpressionCard.model_validate(state["card"])
    today = date.fromisoformat(state["today"]) if state.get("today") else None
    saved = await deps.store.save_card(card, today)
    return {
        "saved_card_id": saved.id,
        "next_review": saved.next_review,
        "final_message": f"{saved.id} 저장 완료 · 다음 복습일 {saved.next_review}",
    }


async def _rejected(state: AgentState, deps: Deps) -> AgentState:
    return {"final_message": "저장하지 않았습니다. 다른 표현이 필요하면 문장을 바꿔 다시 입력해 주세요."}


async def _review_cards(state: AgentState, deps: Deps) -> AgentState:
    writer = get_stream_writer()
    today = date.fromisoformat(state["today"]) if state.get("today") else None
    cards = await deps.store.due_cards(today)
    if cards:
        head, show = f"오늘 복습할 카드 {len(cards)}장 — 한국어를 보고 영어로 먼저 말해 보세요.", cards
    else:   # 오늘 복습할 카드가 없어도 최근 저장한 카드는 보여 준다 (CP3 사용자 피드백)
        show = sorted(await deps.store.list_cards(), key=lambda c: c.id, reverse=True)[:5]
        head = (f"오늘 복습할 카드는 없어요. 최근 저장한 카드 {len(show)}장을 보여 드릴게요." if show
                else "저장된 카드가 아직 없어요. 먼저 표현을 만들어 승인해 보세요.")
    reply = "\n".join([head] + [f"\n[{c.id}] {c.korean_prompt}\n  ↳ 정답: {c.answer_draft or c.formal_expression}"
                                 f" (다음 복습 {c.next_review})" for c in show])
    writer(events.FinalAnswer(reply=reply).model_dump())
    return {"final_message": reply}


async def _out_of_scope(state: AgentState, deps: Deps) -> AgentState:
    writer = get_stream_writer()
    reply = ("저는 영어 면접 표현·답변 준비와 복습만 도와드려요. "
             "면접에서 하고 싶은 말이나 면접 질문을 입력해 주세요.")
    writer(events.FinalAnswer(reply=reply).model_dump())
    return {"final_message": reply}


def build_graph(deps: Deps) -> CompiledStateGraph:
    g = StateGraph(AgentState)
    nodes = {
        NODE_ROUTER: _router, NODE_COACH: _coach, NODE_REVIEWER: _reviewer,
        NODE_BUMP_RETRY: _bump_retry, NODE_APPROVE: _approve, NODE_SAVE: _save,
        NODE_REJECTED: _rejected, NODE_REVIEW_CARDS: _review_cards, NODE_OUT_OF_SCOPE: _out_of_scope,
    }
    for name, fn in nodes.items():
        g.add_node(name, functools.partial(fn, deps=deps))

    g.add_edge(START, NODE_ROUTER)
    g.add_conditional_edges(NODE_ROUTER, route_intent, [NODE_COACH, NODE_REVIEW_CARDS, NODE_OUT_OF_SCOPE])
    g.add_edge(NODE_COACH, NODE_REVIEWER)
    g.add_conditional_edges(NODE_REVIEWER, route_review, [NODE_APPROVE, NODE_BUMP_RETRY])
    g.add_edge(NODE_BUMP_RETRY, NODE_COACH)
    g.add_conditional_edges(NODE_APPROVE, route_approval, [NODE_SAVE, NODE_REJECTED])
    for n in (NODE_SAVE, NODE_REJECTED, NODE_REVIEW_CARDS, NODE_OUT_OF_SCOPE):
        g.add_edge(n, END)
    return g.compile(checkpointer=deps.checkpointer)
