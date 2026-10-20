"""[계약] 의존성 주입 컨테이너 Deps와 그 안에 들어가는 포트(Protocol). Lead만 수정한다 (ADR-0011).

- 정의는 여기, 조립은 agent/deps.py의 build_deps() (A1).
- 그래프 노드는 `functools.partial(node, deps=deps)`로 Deps를 받는다. 전역 싱글턴·모듈 import 시점 생성 금지.
- 모든 I/O 메서드는 async (ADR-0005). 동기 SQLite를 쓰면 `asyncio.to_thread`로 감싼다.
"""

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Optional, Protocol, runtime_checkable

from langchain_core.language_models import BaseChatModel

from contracts.schemas import ExpressionCard, ReviewOutcome, SavedCard

_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class DataPaths:
    """COACH_DATA_DIR 아래 파일 배치. A1(store)·A2(MCP 서버)·A3(API)가 같은 경로를 쓰도록 고정한다."""
    root: Path

    @classmethod
    def from_env(cls) -> "DataPaths":
        return cls(Path(os.getenv("COACH_DATA_DIR", "./data")).expanduser().resolve())

    @property
    def profile(self) -> Path:            # UserProfile JSON (필수)
        return self.root / "profile.json"

    @property
    def docs_dir(self) -> Path:           # 경험 문서 *.md (필수, RAG 대상)
        return self.root / "docs"

    @property
    def job_posting(self) -> Path:        # `## 섹션` 형식 공고 (필수)
        return self.root / "job_posting.md"

    @property
    def persona_rules(self) -> Path:      # 사용자 규칙이 없으면 templates 기본값
        p = self.root / "persona_rules.md"
        return p if p.exists() else _ROOT / "templates" / "persona_rules.default.md"

    @property
    def expression_bank(self) -> Path:    # 선택. 없으면 templates 예시
        p = self.root / "expression_bank.json"
        return p if p.exists() else _ROOT / "templates" / "expression_bank.template.json"

    @property
    def coach_db(self) -> Path:           # 카드·복습 단계 (agent/store.py)
        return self.root / "coach.db"

    @property
    def checkpoints_db(self) -> Path:     # LangGraph AsyncSqliteSaver
        return self.root / "checkpoints.db"

    @property
    def embed_cache(self) -> Path:        # RAG 임베딩 캐시 (MCP 서버)
        return self.root / "embedding_cache.json"


@runtime_checkable
class MCPPort(Protocol):
    """MCP 서버 "coach" 호출 인터페이스. 구현은 agent/mcp_client.py (A2), 이름은 contracts.mcp 상수."""

    async def call_tool(self, name: str, arguments: dict) -> str:
        """Tool 결과 텍스트(출처 라벨 포함)를 돌려준다."""
        ...

    async def read_resource(self, uri: str) -> str:
        ...

    async def get_prompt(self, name: str, arguments: dict) -> str:
        """렌더링된 프롬프트 본문(system 메시지로 쓸 텍스트)."""
        ...


@runtime_checkable
class CardStore(Protocol):
    """카드 저장소. 구현은 agent/store.py (A1). today를 비우면 오늘 날짜를 쓴다."""

    async def save_card(self, card: ExpressionCard, today: Optional[date] = None) -> SavedCard:
        ...

    async def list_cards(self) -> list[SavedCard]:
        ...

    async def due_cards(self, today: Optional[date] = None) -> list[SavedCard]:
        ...

    async def review(self, card_id: str, outcome: ReviewOutcome, today: Optional[date] = None) -> SavedCard:
        """단계 전환: known → stage+1(최대 2), again → stage 0. next_review = today + REVIEW_INTERVALS_DAYS[stage]."""
        ...

    async def known_chunks(self) -> list[str]:
        ...


@dataclass(frozen=True)
class Deps:
    fast_llm: BaseChatModel        # FAST_MODEL — router
    quality_llm: BaseChatModel     # QUALITY_MODEL — Coach·Reviewer
    mcp: MCPPort
    store: CardStore
    checkpointer: Any              # langgraph BaseCheckpointSaver (AsyncSqliteSaver, 테스트는 InMemorySaver)
    paths: DataPaths
