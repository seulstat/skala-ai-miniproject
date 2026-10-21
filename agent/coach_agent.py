# 출처: skala-ai-agent/practice/dapdap/graph.py의 build_generate_agent (Phase 0 복사 후 deps 기반으로 재작성)
"""Coach — create_agent(ReAct)로 검색 Tool을 스스로 고르고 ExpressionCard를 구조화 출력한다 (ADR-0004)."""

from typing import Callable

from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain.agents.structured_output import ToolStrategy
from langgraph.graph.state import CompiledStateGraph

from agent.prompts import generator_prompt
from agent.tools import build_agent_tools
from contracts import mcp_spec
from contracts.deps import Deps
from contracts.errors import ErrorInfo
from contracts.schemas import ExpressionCard, UserProfile

StreamWriter = Callable[[dict], None]

# 한 번 생성에 검색 최대 4회(Tool별 상한의 합), 넘으면 있는 근거로 답하게 한다.
# Tool 이름 없이 상한을 걸면 카드 출력(ToolStrategy의 ExpressionCard 호출)까지 막혀 무한 반복한다 (CP4 측정 중 발견, ADR-0021)
TOOL_CALL_LIMITS = {mcp_spec.AGENT_TOOL_SEARCH_MY_EXPERIENCE: 2, mcp_spec.AGENT_TOOL_GET_JOB_POSTING: 1,
                    mcp_spec.AGENT_TOOL_SEARCH_EXPRESSION_BANK: 1}
TOOL_CALL_RUN_LIMIT = sum(TOOL_CALL_LIMITS.values())


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
        middleware=[ToolCallLimitMiddleware(tool_name=name, run_limit=n, exit_behavior="continue")
                    for name, n in TOOL_CALL_LIMITS.items()],
    )
