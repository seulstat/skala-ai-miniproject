"""MCP 서버 "coach"(fastmcp, stdio) — Tool 2 · Resource 1 · Prompt 1. 이름·인자는 contracts.mcp_spec 상수만 쓴다 (ADR-0002·0003)

데이터는 DataPaths(COACH_DATA_DIR)에서 요청마다 읽는다. 공고(posting://)와 페르소나 규칙은 캐시하지 않고,
경험 문서·표현집은 rag.Retriever가 파일 mtime을 보고 바뀌었을 때만 다시 색인한다.
Tool·Resource·Prompt의 docstring은 LLM이 Tool을 고르는 근거이므로 언제 쓰는지와 인자 예시를 구체적으로 쓴다.
stdout은 MCP 프로토콜 전용이다 — print()를 쓰지 않는다 (로그는 stderr).
"""

import asyncio
import re
from typing import Annotated, Optional

from dotenv import find_dotenv, load_dotenv
from fastmcp import FastMCP
from pydantic import Field

from agent.prompts import reviewer_prompt
from contracts import mcp_spec
from contracts.deps import DataPaths
from rag import Retriever

# mcp_spec.SearchArgs와 같은 제약 (query 1자 이상, k 1~5, 기본 3). 일치는 tests/test_mcp_server.py가 검사한다
Query = Annotated[str, Field(min_length=1)]
TopK = Annotated[int, Field(ge=1, le=5)]


def posting_section(text: str, section: str) -> str:
    """`## 섹션` 형식 공고에서 섹션 본문을 `[job_posting > 섹션]` 라벨과 함께 꺼낸다. "전체"는 문서 전체."""
    label = mcp_spec.LABEL_POSTING.format(section=section)
    if section == "전체":
        return f"{label}\n{text}"
    m = re.search(rf"^## {re.escape(section)}[ \t]*\r?\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return f"{label}\n{m.group(1).strip()}" if m else f"'{section}' 섹션이 없습니다."


def create_server(paths: Optional[DataPaths] = None, retriever: Optional[Retriever] = None) -> FastMCP:
    """서버를 만든다. 테스트는 tmp 경로의 DataPaths와 fake Retriever를 넘기고, 실행 때는 환경변수(COACH_DATA_DIR)를 쓴다."""
    paths = paths or DataPaths.from_env()
    retriever = retriever or Retriever(paths)
    server = FastMCP(mcp_spec.SERVER_NAME)

    @server.tool(name=mcp_spec.TOOL_SEARCH_MY_EXPERIENCE)
    async def search_my_experience(query: Query, k: TopK = 3) -> str:
        """지원자 본인의 연구·프로젝트·활동·자기소개서 내용에서 질문과 가장 비슷한 문단을 찾아 줍니다.
        사용자가 말하려는 문장이 자기 경험(연구, 수치, 협업, 지원동기 등)에 관한 것일 때 사용하세요.
        결과는 문단마다 `[파일 > 제목]` 출처 라벨로 시작하며, 이 라벨을 카드의 evidence에 그대로 적습니다.

        Args:
            query: 찾고 싶은 경험을 한국어로 서술한 검색어 (예: "프로젝트 성과 수치", "팀 갈등 해결 경험")
            k: 가져올 문단 수 (1~5, 기본 3)
        """
        return await asyncio.to_thread(retriever.search_experience, query, k)

    @server.tool(name=mcp_spec.TOOL_SEARCH_EXPRESSION_BANK)
    async def search_expression_bank(query: Query, k: TopK = 3) -> str:
        """면접 영어 표현집에서 비슷한 상황의 검증된 문장 틀을 찾아 줍니다.
        비슷한 상황의 문장 틀이 필요할 때 사용하세요. verified=true 표현을 먼저 돌려주며, 그대로 베끼지 말고 사용자 문장에 맞게 바꿔 쓰세요.
        결과는 줄마다 `[표현ID, verified=true|false]`로 시작합니다.

        Args:
            query: 상황 설명 (예: "한계를 정직하게 말하기", "의견이 다를 때 협업")
            k: 가져올 표현 수 (1~5, 기본 3)
        """
        return await asyncio.to_thread(retriever.search_bank, query, k)

    @server.resource(mcp_spec.RESOURCE_POSTING, mime_type="text/markdown")
    async def posting(section: str) -> str:
        """지원 공고의 한 섹션을 `[job_posting > 섹션]` 라벨과 함께 돌려줍니다.
        회사가 중시하는 역량, 주요 업무, 영어 면접 평가 포인트에 맞춰 표현을 다듬어야 할 때 읽으세요.
        {section} 자리에는 "회사 소개" · "주요 업무" · "자격 요건" · "우대 사항" · "전형 절차" · "영어 면접 안내" 중 하나를 넣고,
        모르면 "전체"를 넣습니다 (예: posting://주요 업무, posting://전체). 사용자가 공고를 고치면 바뀌므로 매번 새로 읽습니다.
        """
        text = await asyncio.to_thread(paths.job_posting.read_text, encoding="utf-8")
        return posting_section(text, section)

    @server.prompt(name=mcp_spec.PROMPT_PERSONA_REVIEW)
    async def persona_review_prompt() -> str:
        """생성된 면접 표현 카드를 검수할 때 쓰는 system 프롬프트를 돌려줍니다 (인자 없음).
        사용자의 페르소나 규칙(persona_rules.md, 없으면 기본 규칙)을 읽어 검수 지시문으로 완성한 텍스트이므로,
        Reviewer는 받은 문자열을 그대로 system 메시지로 쓰면 됩니다. 검수를 시작할 때마다 호출하세요.
        """
        rules = await asyncio.to_thread(paths.persona_rules.read_text, encoding="utf-8")
        return reviewer_prompt(rules)

    return server


def main() -> None:
    load_dotenv(find_dotenv(usecwd=True))        # 직접 실행할 때용. 이미 설정된 환경변수는 덮어쓰지 않는다
    create_server().run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
