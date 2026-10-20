# 출처: skala-ai-agent/practice/dapdap/tools.py (Phase 0 복사, 로직 미변경)
"""Tool 5종. 검색 3종은 생성 Agent가 스스로 고르고, 쓰기 2종은 노드가 호출한다."""

import json
import re
from datetime import date, timedelta
from typing import Literal

from langchain_core.tools import tool

from .config import CARDS_PATH, JOB_POSTING_PATH
from .rag import bank_store, experience_store, load_bank

REVIEW_INTERVALS = [1, 3, 7]   # D+1 → D+3 → D+7. 현재는 첫 간격(1일)만 쓰고, stage를 올리는 간격 반복은 미구현

PostingSection = Literal["회사 소개", "주요 업무", "자격 요건", "우대 사항", "전형 절차", "영어 면접 안내", "전체"]


# ---------- 읽기 (LLM이 선택) ----------

@tool
def search_my_experience(query: str, k: int = 3) -> str:
    """지원자 본인의 연구·프로젝트·활동·자기소개서 내용을 검색합니다.
    사용자가 말하려는 문장이 자기 경험(연구, 수치, 협업, 지원동기 등)에 관한 것일 때 사용하세요.

    Args:
        query: 찾고 싶은 경험을 한국어로 서술한 검색어 (예: "프로젝트 성과 수치", "팀 갈등 해결 경험")
        k: 가져올 문단 수 (1~5)
    """
    hits = experience_store().similarity_search(query, k=max(1, min(k, 5)))
    return "\n\n".join(f"[{d.metadata['source']}]\n{d.page_content}" for d in hits)


@tool
def get_job_posting(section: PostingSection = "전체") -> str:
    """지원 공고의 특정 섹션을 가져옵니다.
    회사가 중시하는 역량, 주요 업무, 영어 면접 평가 포인트에 맞춰 표현을 다듬어야 할 때 사용하세요.

    Args:
        section: 가져올 섹션 이름. 모르면 "전체"
    """
    text = JOB_POSTING_PATH.read_text(encoding="utf-8")
    if section == "전체":
        return f"[job_posting > 전체]\n{text}"
    m = re.search(rf"## {re.escape(section)}\n(.*?)(?=\n## |\Z)", text, re.S)
    return f"[job_posting > {section}]\n{m.group(1).strip()}" if m else f"'{section}' 섹션이 없습니다."


@tool
def search_expression_bank(query: str, k: int = 3) -> str:
    """면접 영어 표현집에서 비슷한 상황의 검증된 문장 틀을 찾습니다.
    verified=true 표현을 우선 참고하고, 그대로 베끼지 말고 사용자 문장에 맞게 바꿔 쓰세요.

    Args:
        query: 상황 설명 (예: "한계를 정직하게 말하기", "의견이 다를 때 협업")
        k: 가져올 표현 수 (1~5)
    """
    if not load_bank():
        return "표현집이 비어 있습니다. search_my_experience와 get_job_posting의 근거로 작성하세요."
    hits = bank_store().similarity_search(query, k=max(1, min(k, 5)) + 2)
    hits.sort(key=lambda d: not d.metadata["verified"])          # verified 먼저
    lines = [
        f"[{d.metadata['id']}, verified={str(d.metadata['verified']).lower()}] "
        f"{d.metadata['situation']} — {d.metadata['phrase']}"
        for d in hits[:k]
    ]
    return "\n".join(lines)


SEARCH_TOOLS = [search_my_experience, get_job_posting, search_expression_bank]


# ---------- 쓰기 (HITL 승인 후 노드가 호출) ----------

def _load_db() -> dict:
    if CARDS_PATH.exists():
        return json.loads(CARDS_PATH.read_text(encoding="utf-8"))
    return {"cards": [], "known_chunks": []}


def _write_db(db: dict) -> None:
    CARDS_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")


def known_chunks() -> list[str]:
    return _load_db()["known_chunks"]


@tool
def save_card(card: dict, today: str = "") -> str:
    """승인된 복습 카드를 카드 DB에 저장하고 첫 복습일(D+1)을 정합니다. 핵심 chunk는 known_chunks에 추가합니다.

    Args:
        card: ExpressionCard 딕셔너리
        today: 저장 기준일 YYYY-MM-DD (비우면 오늘)
    """
    db = _load_db()
    base = date.fromisoformat(today) if today else date.today()
    card_id = f"C{len(db['cards']) + 1:04d}"
    db["cards"].append({
        "id": card_id,
        "created": base.isoformat(),
        "next_review": (base + timedelta(days=REVIEW_INTERVALS[0])).isoformat(),
        "stage": 0,
        **card,
    })
    for c in card.get("chunks", []):
        if c["phrase"] not in db["known_chunks"]:
            db["known_chunks"].append(c["phrase"])
    _write_db(db)
    return f"{card_id} 저장 완료 · 다음 복습일 {db['cards'][-1]['next_review']}"


@tool
def get_due_cards(today: str = "") -> list[dict]:
    """복습일이 된 카드 목록을 돌려줍니다.

    Args:
        today: 기준일 YYYY-MM-DD (비우면 오늘)
    """
    base = today or date.today().isoformat()
    return [c for c in _load_db()["cards"] if c["next_review"] <= base]
