"""Supervisor 그래프의 조건부 엣지 라우팅 함수. agent/graph.py에서 분리했다 (파일당 약 200줄, agent.md §4)."""

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
