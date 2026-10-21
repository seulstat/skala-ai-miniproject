"""공고 원문을 규칙으로 6개 섹션에 나눈다 — LLM이 실패하거나 필수 섹션을 빠뜨렸을 때의 대안 (CP3 브라우저 E2E에서 발견).

실제 공고는 "[담당하시게 될 업무를 소개합니다]", "이런 분을 찾습니다"처럼 제목이 제각각이라,
제목처럼 보이는 짧은 줄에서 키워드를 찾아 계약의 섹션 이름(POSTING_SECTIONS)으로 바꾼다.
"""

import re

# 위에서부터 먼저 맞는 섹션을 고른다 ("자격 우대"처럼 겹치면 우대가 먼저)
SECTION_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("영어 면접 안내", ("영어 면접", "영어면접", "english interview", "영어 인터뷰")),
    ("우대 사항", ("우대", "더 좋아요", "더 좋습니다", "플러스", "preferred", "nice to have")),
    ("전형 절차", ("전형", "채용 절차", "채용 과정", "채용 프로세스", "지원 방법", "hiring process")),
    ("자격 요건", ("자격", "필수", "이런 분을 찾", "요구 사항", "요구사항", "requirements", "qualifications")),
    ("주요 업무", ("업무", "하는 일", "하시게 될", "직무 내용", "responsibilities", "what you")),
    ("회사 소개", ("회사 소개", "회사소개", "기업 소개", "팀 소개", "about us", "우리는")),
]
_BULLET = re.compile(r"^[\s•·\-\*■□▶▷◆◇○●#]+")
_WRAP = re.compile(r"^[\[\(【<](.*)[\]\)】>]$")


def _heading_name(line: str) -> str | None:
    """제목처럼 보이는 짧은 줄이면 섹션 이름, 아니면 None."""
    text = _BULLET.sub("", line).strip().rstrip(":：").strip()
    text = _WRAP.sub(r"\1", text).strip()
    if not text or len(text) > 30:
        return None
    low = text.lower()
    for name, words in SECTION_KEYWORDS:
        if any(w in low for w in words):
            return name
    return None


def split_by_rules(raw: str) -> str:
    """`## 섹션` 마크다운. 첫 제목 전의 줄은 회사 소개로, 같은 섹션이 여러 번 나오면 이어 붙인다."""
    sections: dict[str, list[str]] = {}
    current = "회사 소개"
    for line in raw.splitlines():
        name = _heading_name(line)
        if name:
            current = name
            sections.setdefault(current, [])
            continue
        if line.strip():
            sections.setdefault(current, []).append(line.rstrip())
    return "\n\n".join(f"## {name}\n" + "\n".join(body) for name, body in sections.items() if body)
