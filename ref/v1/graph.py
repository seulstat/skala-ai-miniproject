# 출처: skala-ai-agent/practice/dapdap/graph.py (Phase 0 복사, 로직 미변경)
"""v2~v5 — LangGraph Agent.

router ─┬─ express/answer → generate(ReAct) → reviewer ⟲(최대 2회) → approve(HITL) → save
        ├─ review → review_cards
        └─ out_of_scope
"""

import json
from typing import TypedDict

from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from .config import MAX_RETRY, PROFILE_PATH, get_model
from .prompts import ROUTER_PROMPT, banned_hits, generator_prompt, reviewer_prompt
from .schemas import ExpressionCard, ReviewResult, Route, UserProfile, Violation
from .tools import SEARCH_TOOLS, get_due_cards, known_chunks, save_card


class AgentState(TypedDict, total=False):
    user_input: str
    today: str
    intent: str
    card: dict
    review: dict
    retry_count: int
    warning: str
    approved: bool
    tools_used: list
    review_log: list
    final_message: str


def load_profile() -> UserProfile:
    return UserProfile.model_validate_json(PROFILE_PATH.read_text(encoding="utf-8"))


def card_text(card: dict) -> str:
    parts = [card.get("formal_expression", ""), card.get("casual_expression", ""), card.get("answer_draft") or ""]
    parts += [c["phrase"] for c in card.get("chunks", [])]
    return "\n".join(parts)


# ---------------- 노드 ----------------

def router(state: AgentState) -> AgentState:
    route = get_model().with_structured_output(Route).invoke(
        [("system", ROUTER_PROMPT), ("human", state["user_input"])]
    )
    return {"intent": route.intent, "retry_count": 0}


def build_generate_agent(intent: str = "express"):
    """생성 노드 안의 ReAct Agent. 그래프 그림에서 내부 구조를 따로 보여줄 때도 쓴다."""
    return create_agent(
        model=get_model(),
        tools=SEARCH_TOOLS,
        system_prompt=generator_prompt(load_profile(), known_chunks(), intent),
        # 스키마 검증 실패 시 오류를 모델에 돌려보내 다시 쓰게 한다 (GPT가 필드를 빠뜨리는 경우 대비)
        response_format=ToolStrategy(ExpressionCard, handle_errors=True),
        # 같은 검색을 수십 번 반복하는 폭주 방지 — 한 번 생성에 검색 최대 4회, 넘으면 있는 근거로 답하게 한다
        middleware=[ToolCallLimitMiddleware(run_limit=4, exit_behavior="continue")],
    )


def generate(state: AgentState) -> AgentState:
    """근거 탐색이 필요한 유일한 구간 — create_agent(ReAct)가 어떤 Tool을 쓸지 스스로 고른다."""
    agent = build_generate_agent(state["intent"])
    request = state["user_input"]
    if state.get("review") and not state["review"]["passed"]:     # Reviewer 피드백 반영 재생성
        request += (
            "\n\n[이전 카드]\n" + json.dumps(state["card"], ensure_ascii=False)
            + "\n\n[검수 피드백 — 반드시 반영해 다시 작성]\n" + json.dumps(state["review"], ensure_ascii=False)
        )
    result = agent.invoke({"messages": [HumanMessage(request)]})
    used = [tc["name"] for m in result["messages"] if isinstance(m, AIMessage) for tc in m.tool_calls
            if tc["name"] in {t.name for t in SEARCH_TOOLS}]
    card = result["structured_response"].model_dump()
    card["mode"] = state["intent"]
    return {"card": card, "tools_used": state.get("tools_used", []) + [used]}


def reviewer(state: AgentState) -> AgentState:
    """Reflection — LLM 의미 검사 + 금지 표현 regex 확정 검사."""
    review = get_model().with_structured_output(ReviewResult).invoke(
        [("system", reviewer_prompt()), ("human", json.dumps(state["card"], ensure_ascii=False))]
    )
    hits = banned_hits(card_text(state["card"]))
    for rid, quote in hits:
        if not any(v.quote.lower() == quote.lower() for v in review.violations):
            review.violations.append(Violation(rule_id=rid, quote=quote, fix="persona_rules.md의 대체 표현 사용"))
    review.passed = review.passed and not hits and not review.violations
    log_entry = {"round": state["retry_count"] + 1, "passed": review.passed,
                 "violations": [f"{v.rule_id}: '{v.quote}' → {v.fix}" for v in review.violations]}
    update: AgentState = {"review": review.model_dump(),
                          "review_log": state.get("review_log", []) + [log_entry]}
    if not review.passed and state["retry_count"] >= MAX_RETRY:
        update["warning"] = f"재작성 {MAX_RETRY}회 후에도 검수 미통과: " + "; ".join(
            f"{v.rule_id} '{v.quote}'" for v in review.violations)
    return update


def bump_retry(state: AgentState) -> AgentState:
    return {"retry_count": state["retry_count"] + 1}


def approve(state: AgentState) -> AgentState:
    """HITL — 사용자의 학습 자산(카드 DB)에 쓰기 전에 멈추고 승인을 기다린다."""
    decision = interrupt({
        "question": "이 카드를 복습 카드로 저장할까요?",
        "card": state["card"],
        "warning": state.get("warning"),
    })
    return {"approved": bool(decision.get("approve"))}


def save(state: AgentState) -> AgentState:
    msg = save_card.invoke({"card": state["card"], "today": state.get("today", "")})
    return {"final_message": msg}


def rejected(state: AgentState) -> AgentState:
    return {"final_message": "저장하지 않았습니다. 다른 표현이 필요하면 문장을 바꿔 다시 입력해 주세요."}


def review_cards(state: AgentState) -> AgentState:
    cards = get_due_cards.invoke({"today": state.get("today", "")})
    if not cards:
        return {"final_message": "오늘 복습할 카드가 없습니다."}
    lines = [f"오늘 복습할 카드 {len(cards)}장 — 한국어를 보고 영어로 먼저 말해 보세요."]
    for c in cards:
        answer = c.get("answer_draft") or c["formal_expression"]
        lines.append(f"\n[{c['id']}] {c['korean_prompt']}\n  ↳ 정답: {answer}")
    return {"final_message": "\n".join(lines)}


def out_of_scope(state: AgentState) -> AgentState:
    return {"final_message": "저는 영어 면접 표현·답변 준비와 복습만 도와드려요. "
                             "면접에서 하고 싶은 말이나 면접 질문을 입력해 주세요."}


# ---------------- 라우팅 함수 ----------------

def route_intent(state: AgentState) -> str:
    return {"express": "generate", "answer": "generate", "review": "review_cards"}.get(state["intent"], "out_of_scope")


def route_review(state: AgentState) -> str:
    if state["review"]["passed"] or state["retry_count"] >= MAX_RETRY:
        return "approve"
    return "bump_retry"


def route_approval(state: AgentState) -> str:
    return "save" if state["approved"] else "rejected"


# ---------------- 그래프 ----------------

def build_graph(checkpointer=None):
    g = StateGraph(AgentState)
    for name, fn in [("router", router), ("generate", generate), ("reviewer", reviewer),
                     ("bump_retry", bump_retry), ("approve", approve), ("save", save),
                     ("rejected", rejected), ("review_cards", review_cards), ("out_of_scope", out_of_scope)]:
        g.add_node(name, fn)

    g.add_edge(START, "router")
    g.add_conditional_edges("router", route_intent, ["generate", "review_cards", "out_of_scope"])
    g.add_edge("generate", "reviewer")
    g.add_conditional_edges("reviewer", route_review, ["approve", "bump_retry"])
    g.add_edge("bump_retry", "generate")
    g.add_conditional_edges("approve", route_approval, ["save", "rejected"])
    for n in ["save", "rejected", "review_cards", "out_of_scope"]:
        g.add_edge(n, END)
    return g.compile(checkpointer=checkpointer or InMemorySaver())


def run(graph, user_input: str, thread_id: str, approve_fn=None, today: str = "", trace: list | None = None) -> dict:
    """한 번의 요청을 끝까지 실행. HITL에서 멈추면 approve_fn(payload)->bool 로 재개한다.

    trace에 리스트를 넘기면 실제로 지나간 노드 이름이 순서대로 쌓인다 (그래프 그림과 대조용).
    """
    config = {"configurable": {"thread_id": thread_id}}

    def drive(payload):
        if trace is None:
            return graph.invoke(payload, config)
        interrupts = None
        for chunk in graph.stream(payload, config, stream_mode="updates"):
            for node, update in chunk.items():
                if node == "__interrupt__":
                    interrupts = update
                else:
                    trace.append(node)
        state = dict(graph.get_state(config).values)
        if interrupts:
            state["__interrupt__"] = interrupts
        return state

    state = drive({"user_input": user_input, "today": today})
    while "__interrupt__" in state:
        payload = state["__interrupt__"][0].value
        ok = approve_fn(payload) if approve_fn else False
        state = drive(Command(resume={"approve": ok}))
    return state
