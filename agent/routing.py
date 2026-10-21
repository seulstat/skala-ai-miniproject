"""Supervisor 그래프의 조건부 엣지 라우팅 함수. agent/graph.py에서 분리했다 (파일당 약 200줄, agent.md §4)."""

import re

from contracts.state import (
    INTENT_TO_NODE,
    MAX_REWRITES,
    NODE_APPROVE,
    NODE_OUT_OF_SCOPE,
    NODE_REJECTED,
    NODE_SAVE,
    AgentState,
)

NODE_BUMP_RETRY = "bump_retry"  # 계약(contracts.state)에 없는 내부 전용 노드 — 재작성 카운터만 올린다


def route_intent(state: AgentState) -> str:
    return INTENT_TO_NODE.get(state["intent"], NODE_OUT_OF_SCOPE)


def route_review(state: AgentState) -> str:
    if state["review"]["passed"] or state.get("retry_count", 0) >= MAX_REWRITES:
        return NODE_APPROVE
    return NODE_BUMP_RETRY


def route_approval(state: AgentState) -> str:
    return NODE_SAVE if state["approved"] else NODE_REJECTED


# 권위 게이트 (강의 p.147): 의도가 문장에 드러나는 복습 요청은 소형 router 모델의 판단보다 코드가 우선한다
_REVIEW_HINT = re.compile(r"복습|저장한\s*카드|카드\s*(보여|목록)")


def authoritative_intent(user_input: str, llm_intent: str) -> str:
    return "review" if _REVIEW_HINT.search(user_input) else llm_intent
