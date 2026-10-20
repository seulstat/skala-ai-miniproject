"""[계약] MCP 서버 "coach"의 Tool·Resource·Prompt 이름과 인자, Agent 래퍼 Tool 이름. Lead만 수정한다.

- 서버(A2, mcp_server.py)는 아래 이름·인자로 등록하고, 클라이언트(A2, agent/mcp_client.py)는 find_*로 찾는다.
- Agent(A1, agent/tools.py)는 래퍼 @tool 3개만 LLM에 노출하고, 내부에서 deps.mcp를 호출한다 (ADR-0002).
- Tool 결과는 문자열이며 근거마다 `[출처 라벨]`로 시작한다. 라벨이 ExpressionCard.evidence에 그대로 들어간다.
"""

from pydantic import BaseModel, Field

from contracts.schemas import PostingSection

SERVER_NAME = "coach"

# ---------- MCP Tool ----------
TOOL_SEARCH_MY_EXPERIENCE = "search_my_experience"
TOOL_SEARCH_EXPRESSION_BANK = "search_expression_bank"


class SearchArgs(BaseModel):
    """두 검색 Tool 공통 인자 (10/13 tools.py와 같음)."""
    query: str = Field(min_length=1)
    k: int = Field(default=3, ge=1, le=5)


TOOL_ARGS: dict[str, type[BaseModel]] = {
    TOOL_SEARCH_MY_EXPERIENCE: SearchArgs,
    TOOL_SEARCH_EXPRESSION_BANK: SearchArgs,
}

# ---------- MCP Resource ----------
RESOURCE_POSTING = "posting://{section}"      # section: PostingSection ("전체" 포함)


def posting_uri(section: PostingSection = "전체") -> str:
    return RESOURCE_POSTING.format(section=section)


# ---------- MCP Prompt ----------
PROMPT_PERSONA_REVIEW = "persona_review_prompt"
PROMPT_ARGS: dict[str, tuple[str, ...]] = {PROMPT_PERSONA_REVIEW: ()}   # 인자 없음. persona_rules를 읽어 렌더링

# ---------- 출처 라벨 형식 (10/13과 같음) ----------
LABEL_EXPERIENCE = "[{file} > {heading}]"     # 예: [experience.md > 고객 이탈 예측 졸업 프로젝트]
LABEL_POSTING = "[job_posting > {section}]"
LABEL_BANK = "[{id}, verified={verified}]"   # 예: [E14, verified=true]

# ---------- Agent 래퍼 Tool (LLM에 노출되는 이름, EvidenceSearched.tool 값) ----------
AGENT_TOOL_SEARCH_MY_EXPERIENCE = TOOL_SEARCH_MY_EXPERIENCE       # → call_tool
AGENT_TOOL_SEARCH_EXPRESSION_BANK = TOOL_SEARCH_EXPRESSION_BANK   # → call_tool
AGENT_TOOL_GET_JOB_POSTING = "get_job_posting"                    # → read_resource(posting_uri(section))
AGENT_TOOL_NAMES: tuple[str, ...] = (
    AGENT_TOOL_SEARCH_MY_EXPERIENCE, AGENT_TOOL_GET_JOB_POSTING, AGENT_TOOL_SEARCH_EXPRESSION_BANK,
)
