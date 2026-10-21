# 출처: skala-ai-agent/practice/dapdap/graph.py의 reviewer 노드 (Phase 0 복사 후 컴파일된 서브그래프로 재작성, ADR-0004)
"""Reviewer — MCP Prompt persona_review_prompt로 이미 렌더링된 system 프롬프트를 받아 그대로 쓰고,
LLM 의미 검사 + banned_hits 확정 규칙 검사를 한다. LLM이 통과라고 해도 규칙 위반이면 위반이다 (ADR-0004).

get_prompt가 돌려주는 텍스트는 MCP 서버가 agent/prompts.py::reviewer_prompt(rules)로 이미 렌더링을
마친 최종 system 프롬프트다(contracts.deps.MCPPort.get_prompt docstring). Agent 쪽에서 다시
reviewer_prompt()로 감싸면 지시문이 이중으로 들어가므로, 받은 문자열을 그대로 system 메시지로 쓴다.

오류 처리(ADR-0012): get_prompt의 asyncio.TimeoutError는 with_retry로 재시도한다. 재시도 소진·치명
아닌 ToolError(TOOL_EXECUTION_ERROR 등)는 REVIEWER_DEGRADED로 강등해 규칙 검사만으로 진행한다.
MCP_UNAVAILABLE처럼 치명(fatal)인 ToolError는 그대로 올려 그래프를 끝낸다. deps.paths로의 폴백은 없다.
"""

import asyncio
import functools
import json
import logging
from typing import Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agent.prompts import banned_hits
from agent.retry import with_retry
from contracts import mcp_spec
from contracts.deps import Deps
from contracts.errors import RETRY_INITIAL_DELAY, RETRY_MAX, ToolError, error_info
from contracts.schemas import ReviewResult, Violation


class ReviewerState(TypedDict, total=False):
    card: dict
    review: dict
    error: dict  # ErrorInfo.model_dump(), REVIEWER_DEGRADED일 때만


def card_text(card: dict) -> str:
    parts = [card.get("formal_expression", ""), card.get("casual_expression", ""), card.get("answer_draft") or ""]
    parts += [c["phrase"] for c in card.get("chunks", [])]
    return "\n".join(parts)


def _card_json(card: dict) -> str:
    return json.dumps(card, ensure_ascii=False)


async def _llm_review(deps: Deps, card: dict) -> tuple[ReviewResult, Optional[dict]]:
    degraded = ReviewResult(passed=True, violations=[], feedback="")
    try:
        system_prompt, _ = await with_retry(
            deps.mcp.get_prompt, mcp_spec.PROMPT_PERSONA_REVIEW, {},
            retries=RETRY_MAX + 1, base_delay=RETRY_INITIAL_DELAY,
        )
    except asyncio.TimeoutError:
        return degraded, error_info("REVIEWER_DEGRADED").model_dump()
    except ToolError as e:
        if e.info.fatal:
            raise
        return degraded, error_info("REVIEWER_DEGRADED").model_dump()

    try:
        review = await deps.quality_llm.with_structured_output(ReviewResult).ainvoke(
            [("system", system_prompt), ("human", _card_json(card))]
        )
    except Exception as e:  # LLM 호출 자체가 실패해도 규칙 검사만으로 강등해 진행한다
        logging.getLogger("coach.agent").warning("node=reviewer error_code=REVIEWER_DEGRADED detail=%s: %s",
                                                  type(e).__name__, str(e)[:200])
        return degraded, error_info("REVIEWER_DEGRADED").model_dump()
    return review, None


async def _review_node(state: ReviewerState, deps: Deps) -> ReviewerState:
    card = state["card"]
    hits = banned_hits(card_text(card))
    review, error = await _llm_review(deps, card)
    for rid, quote in hits:
        if not any(v.quote.lower() == quote.lower() for v in review.violations):
            review.violations.append(Violation(rule_id=rid, quote=quote, fix="persona_rules.md의 대체 표현 사용"))
    review.passed = review.passed and not review.violations
    return {"review": review.model_dump(), "error": error}


def build_reviewer_agent(deps: Deps) -> CompiledStateGraph:
    g = StateGraph(ReviewerState)
    g.add_node("review", functools.partial(_review_node, deps=deps))
    g.add_edge(START, "review")
    g.add_edge("review", END)
    return g.compile()
