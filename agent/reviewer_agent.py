# 출처: skala-ai-agent/practice/dapdap/graph.py의 reviewer 노드 (Phase 0 복사 후 컴파일된 서브그래프로 재작성, ADR-0004)
"""Reviewer — LLM 의미 검사 + banned_hits 확정 규칙 검사. LLM이 통과라고 해도 규칙 위반이면 위반이다.

LLM 호출이 실패하면 규칙 검사만으로 진행한다(REVIEWER_DEGRADED, 치명 아님 — ADR-0012).
Coach와 마찬가지로 컴파일된 서브그래프로 분리해 생성 맥락과 독립적으로 검수한다 (ADR-0004).
"""

import asyncio
import functools
import json
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agent.prompts import banned_hits, reviewer_prompt
from contracts.deps import Deps
from contracts.errors import error_info
from contracts.schemas import ReviewResult, Violation


class ReviewerState(TypedDict, total=False):
    card: dict
    review: dict
    error: dict  # ErrorInfo.model_dump(), REVIEWER_DEGRADED일 때만


def card_text(card: dict) -> str:
    parts = [card.get("formal_expression", ""), card.get("casual_expression", ""), card.get("answer_draft") or ""]
    parts += [c["phrase"] for c in card.get("chunks", [])]
    return "\n".join(parts)


async def _review_node(state: ReviewerState, deps: Deps) -> ReviewerState:
    card = state["card"]
    hits = banned_hits(card_text(card))
    error: dict | None = None
    try:
        persona_rules = await asyncio.to_thread(deps.paths.persona_rules.read_text, encoding="utf-8")
        review = await deps.quality_llm.with_structured_output(ReviewResult).ainvoke(
            [("system", reviewer_prompt(persona_rules)), ("human", _card_json(card))]
        )
    except Exception:  # LLM 실패는 분류하지 않고 규칙 검사만으로 강등해 진행한다 (ADR-0012)
        review = ReviewResult(passed=True, violations=[], feedback="")
        error = error_info("REVIEWER_DEGRADED").model_dump()
    for rid, quote in hits:
        if not any(v.quote.lower() == quote.lower() for v in review.violations):
            review.violations.append(Violation(rule_id=rid, quote=quote, fix="persona_rules.md의 대체 표현 사용"))
    review.passed = review.passed and not review.violations
    return {"review": review.model_dump(), "error": error}


def _card_json(card: dict) -> str:
    return json.dumps(card, ensure_ascii=False)


def build_reviewer_agent(deps: Deps) -> CompiledStateGraph:
    g = StateGraph(ReviewerState)
    g.add_node("review", functools.partial(_review_node, deps=deps))
    g.add_edge(START, "review")
    g.add_edge("review", END)
    return g.compile()
