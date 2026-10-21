# 출처: skala-ai-agent/practice/dapdap/graph.py의 build_generate_agent (Phase 0 복사 후 deps 기반으로 재작성)
"""Coach — create_agent(ReAct)로 검색 Tool을 스스로 고르고 ExpressionCard를 구조화 출력한다 (ADR-0004)."""

from typing import Callable

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langgraph.graph.state import CompiledStateGraph

from agent.prompts import generator_prompt
from agent.search_budget import SearchBudgetMiddleware
from agent.tools import build_agent_tools
from contracts import mcp_spec
from contracts.deps import Deps
from contracts.errors import ErrorInfo
from contracts.schemas import ExpressionCard, UserProfile

StreamWriter = Callable[[dict], None]

# 한 번 생성에 검색 최대 4회. 넘으면 검색 Tool을 숨겨 있는 근거로 카드를 쓰게 한다 (ADR-0021)
TOOL_CALL_RUN_LIMIT = 4


def build_coach_agent(
    deps: Deps, profile: UserProfile, known_chunks: list[str], mode: str,
    writer: StreamWriter, notices: list[ErrorInfo], used: list[dict],
) -> CompiledStateGraph:
    """요청마다 새로 만든다 — 프로필·이미 익힌 표현이 매 요청 바뀔 수 있어 system_prompt를 고정할 수 없다."""
    tools = build_agent_tools(deps, writer, notices, used)
    return create_agent(
        model=deps.quality_llm,
        tools=tools,
        system_prompt=generator_prompt(profile, known_chunks, mode),
        response_format=ToolStrategy(ExpressionCard, handle_errors=True),
        middleware=[SearchBudgetMiddleware(set(mcp_spec.AGENT_TOOL_NAMES), TOOL_CALL_RUN_LIMIT)],
    )
