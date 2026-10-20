# 출처: skala-ai-agent/practice/dapdap/tools.py의 검색 3종 (Phase 0 복사 후 MCP 래퍼로 재작성, ADR-0002)
"""Coach(create_agent)에 노출하는 얇은 @tool 래퍼 3개. deps.mcp(MCPPort)만 호출한다.

호출마다 EvidenceSearched를 writer로 보낸다 (ADR-0002). 오류 처리는 ADR-0012:
asyncio.TimeoutError만 agent/retry.with_retry로 재시도하고, 소진·영구 오류는 ToolError로 격리해
그 검색만 실패 처리(EvidenceSearched.error + notices)하고 "근거 없음"을 모델에 돌려준다.
MCPPort가 fatal=True인 ToolError(MCP_UNAVAILABLE)를 던지면 그대로 올려 그래프를 끝낸다.
"""

import asyncio
from typing import Callable

from langchain_core.tools import BaseTool, tool

from agent.retry import with_retry
from contracts import mcp_spec
from contracts.deps import Deps
from contracts.errors import RETRY_INITIAL_DELAY, RETRY_MAX, ErrorInfo, ToolError, error_info
from contracts.events import EvidenceSearched
from contracts.schemas import PostingSection

StreamWriter = Callable[[dict], None]


async def _call_with_retry(
    writer: StreamWriter, notices: list[ErrorInfo], used: list[dict],
    tool_name: str, query: str, fn, *args,
) -> str:
    used.append({"tool": tool_name, "query": query})
    try:
        text, _ = await with_retry(fn, *args, retries=RETRY_MAX + 1, base_delay=RETRY_INITIAL_DELAY)
    except asyncio.TimeoutError:
        err = error_info("TOOL_TIMEOUT_AFTER_RETRY")
        writer(EvidenceSearched(tool=tool_name, query=query, error=err).model_dump())
        notices.append(err)
        return "근거 없음"
    except ToolError as e:
        if e.info.fatal:
            raise
        writer(EvidenceSearched(tool=tool_name, query=query, error=e.info).model_dump())
        notices.append(e.info)
        return "근거 없음"
    writer(EvidenceSearched(tool=tool_name, query=query).model_dump())
    return text


def build_agent_tools(
    deps: Deps, writer: StreamWriter, notices: list[ErrorInfo], used: list[dict],
) -> list[BaseTool]:
    """요청마다 새로 만든다 (writer·notices·used는 그 요청 한 번의 수집 상자, ref 10/13의 모듈 전역 Tool과 달리 DI)."""

    @tool
    async def search_my_experience(query: str, k: int = 3) -> str:
        """지원자 본인의 연구·프로젝트·활동·자기소개서 내용을 검색합니다.
        사용자가 말하려는 문장이 자기 경험(연구, 수치, 협업, 지원동기 등)에 관한 것일 때 사용하세요.

        Args:
            query: 찾고 싶은 경험을 한국어로 서술한 검색어 (예: "프로젝트 성과 수치", "팀 갈등 해결 경험")
            k: 가져올 문단 수 (1~5)
        """
        return await _call_with_retry(
            writer, notices, used, mcp_spec.AGENT_TOOL_SEARCH_MY_EXPERIENCE, query,
            deps.mcp.call_tool, mcp_spec.TOOL_SEARCH_MY_EXPERIENCE, {"query": query, "k": k},
        )

    @tool
    async def get_job_posting(section: PostingSection = "전체") -> str:
        """지원 공고의 특정 섹션을 가져옵니다.
        회사가 중시하는 역량, 주요 업무, 영어 면접 평가 포인트에 맞춰 표현을 다듬어야 할 때 사용하세요.

        Args:
            section: 가져올 섹션 이름. 모르면 "전체"
        """
        return await _call_with_retry(
            writer, notices, used, mcp_spec.AGENT_TOOL_GET_JOB_POSTING, section,
            deps.mcp.read_resource, mcp_spec.posting_uri(section),
        )

    @tool
    async def search_expression_bank(query: str, k: int = 3) -> str:
        """면접 영어 표현집에서 비슷한 상황의 검증된 문장 틀을 찾습니다.
        verified=true 표현을 우선 참고하고, 그대로 베끼지 말고 사용자 문장에 맞게 바꿔 쓰세요.

        Args:
            query: 상황 설명 (예: "한계를 정직하게 말하기", "의견이 다를 때 협업")
            k: 가져올 표현 수 (1~5)
        """
        return await _call_with_retry(
            writer, notices, used, mcp_spec.AGENT_TOOL_SEARCH_EXPRESSION_BANK, query,
            deps.mcp.call_tool, mcp_spec.TOOL_SEARCH_EXPRESSION_BANK, {"query": query, "k": k},
        )

    return [search_my_experience, get_job_posting, search_expression_bank]
