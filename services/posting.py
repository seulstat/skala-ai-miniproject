# 출처: skala-ai-agent/practice/scripts/ingest_posting.py (Phase 0 복사 후 프롬프트·정리 규칙을 async 서비스로 이식)
"""공고 6개 섹션 정리 (design §5 POST /api/posting/normalize). URL·PDF 읽기는 제외 범위(design §8)라 텍스트만 받는다.

LLM 재정리는 틀릴 수 있어서 결과는 초안(PostingDraft)으로만 돌려주고, 사용자가 확인·수정한 뒤 PUT /api/posting으로 저장한다.
"""

import re

from langchain_core.language_models import BaseChatModel

from agent.llm import classify_llm_error
from contracts.errors import CoachError
from contracts.schemas import POSTING_SECTIONS, REQUIRED_POSTING_SECTIONS, PostingDraft
from services.posting_rules import split_by_rules

MAX_CHARS = 15000

PROMPT = """아래는 채용공고 원문입니다. 다음 형식의 마크다운으로 정리하세요.

# [채용공고] <회사명> — <직무명>

## 회사 소개
## 주요 업무
## 자격 요건
## 우대 사항
## 전형 절차
## 영어 면접 안내

규칙:
- 섹션 제목은 위 이름 그대로 `## ` 로 쓰세요.
- 원문에 있는 내용만 옮기세요. 없는 섹션은 "(공고에 명시 없음)" 한 줄만 쓰세요. 절대 지어내지 마세요.
- 영어 사용·해외 협업·어학 기준 관련 문장은 빠뜨리지 말고, 영어 면접이 언급되면 '영어 면접 안내'에 넣으세요.
- 마크다운 외 설명 문장은 출력하지 마세요.

[공고 원문]
"""

_HEADING = re.compile(r"^## (.+?)\s*$", re.M)
_NO_CONTENT = re.compile(r"\(?\s*공고에 명시 없음\s*\)?")


def parse_sections(markdown: str) -> dict[str, str]:
    """`## 섹션` 본문을 섹션별로 나눈다. 본문이 비었거나 "(공고에 명시 없음)"뿐인 섹션은 넣지 않는다."""
    heads = list(_HEADING.finditer(markdown))
    sections: dict[str, str] = {}
    for i, head in enumerate(heads):
        name = head.group(1)
        if name not in POSTING_SECTIONS:
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(markdown)
        body = markdown[head.end():end].strip()
        if body and not _NO_CONTENT.fullmatch(body):
            sections[name] = body
    return sections


def missing_required(sections: dict[str, str]) -> list[str]:
    return [s for s in REQUIRED_POSTING_SECTIONS if s not in sections]


def _clean(output: str) -> str:
    """모델이 붙이는 <think> 블록과 ```markdown 울타리를 걷어낸다."""
    output = re.sub(r"<think>.*?</think>", "", output, flags=re.S).strip()
    return re.sub(r"^```(?:markdown)?\n|\n```$", "", output).strip()


def draft_of(markdown: str) -> PostingDraft:
    sections = parse_sections(markdown)
    return PostingDraft(markdown=markdown, sections=sections, missing_required=missing_required(sections))


async def normalize_posting(llm: BaseChatModel, text: str) -> PostingDraft:
    """이미 `## 주요 업무`·`## 자격 요건` 형식이면 그대로, 아니면 LLM이 6개 섹션으로 재정리한다."""
    raw = text.strip()
    if not missing_required(parse_sections(raw)):
        return draft_of(raw)
    try:
        reply = await llm.ainvoke(PROMPT + raw[:MAX_CHARS])
        llm_draft = draft_of(_clean(str(reply.text)))
    except Exception as e:
        llm_error = classify_llm_error(e)
        llm_draft = None
    else:
        llm_error = None
    if llm_draft and llm_draft.sections and not llm_draft.missing_required:
        return llm_draft
    # LLM이 비었거나 필수 섹션을 빠뜨리면 규칙 기반 분할로 대신한다 (제목 키워드 → 섹션)
    rule_draft = draft_of(split_by_rules(raw))
    if rule_draft.sections and (not llm_draft or len(rule_draft.missing_required) <= len(llm_draft.missing_required)):
        return rule_draft          # 필수 섹션이 빠져 있어도 초안으로 돌려주고 화면에서 사용자가 고친다
    if llm_draft and llm_draft.sections:
        return llm_draft
    if llm_error is not None:
        raise llm_error
    raise CoachError("LLM_OUTPUT_INVALID", detail="공고 정리 결과가 비어 있음",
                     user_message="공고를 섹션으로 나누지 못했어요. 원문에 '주요 업무'·'자격 요건' 같은 제목을 붙여 다시 시도해 주세요.")
