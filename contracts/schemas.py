# 출처: skala-ai-agent/practice/dapdap/schemas.py (Phase 0 복사, 로직 미변경)
"""구조화 출력 스키마. 친구 버전의 카드 스키마를 유지하고 Agent용 필드를 덧붙였다."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Certification(BaseModel):
    name: str = Field(description="예: TOEIC Speaking, OPIc")
    score_or_level: str = Field(description='예: "AL(160)", "IM2"')


class UserProfile(BaseModel):
    goal: str
    target_role: str
    speaking_with: List[str] = Field(default_factory=list)
    tone_preference: Literal["직설적인느낌", "부드럽고 정중한 느낌", "중립/상관없음"] = "중립/상관없음"
    english_variety: Literal["미국식", "영국식", "호주식", "상관없음"] = "상관없음"
    certifications: List[Certification] = Field(default_factory=list)
    background: str = ""
    persona_summary: str = Field(default="", description="면접에서 어떤 사람으로 보이고 싶은지 한 줄 (선택)")
    known_chunks: List[str] = Field(default_factory=list, description="이미 익숙해서 복습 완료한 표현들")


class Chunk(BaseModel):
    phrase: str = Field(description="외워 둘 핵심 영어 덩어리 표현")
    note: str = Field(description="뜻과 쓰임 (한국어)")


class ExpressionCard(BaseModel):
    """복습 카드. korean_prompt~chunks는 친구 버전과 동일한 필드."""
    korean_prompt: str = Field(description="사용자가 입력한 원문")
    mode: Literal["express", "answer"] = Field(default="express", description="express=문장 표현, answer=면접 답변 초안")
    formal_expression: str = Field(description="면접관에게 쓰는 격식 있는 표현 (answer 모드는 답변의 핵심 첫 문장)")
    casual_expression: str = Field(description="동료에게 쓰는 부드러운 표현")
    answer_draft: Optional[str] = Field(default=None, description="answer 모드: 30~45초(80~110단어) 영어 답변. express 모드는 null")
    chunks: List[Chunk] = Field(description="외워 둘 핵심 표현 1~3개")
    note: str = Field(description="왜 이 표현이 이 지원자에게 맞는지 (근거 경험·공고 포인트를 한국어로)")
    evidence: List[str] = Field(description="참고한 근거의 출처 라벨 목록. 예: 'experience.md > 물류 스타트업 데이터 분석 인턴 (2개월)', 'job_posting > 영어 면접 안내', 'E14'")


class Route(BaseModel):
    intent: Literal["express", "answer", "review", "out_of_scope"] = Field(
        description="express: 한국어 문장을 영어로 말하고 싶음 / answer: 면접 질문에 대한 답변을 원함 / "
                    "review: 저장한 카드 복습 / out_of_scope: 영어 면접 준비와 무관"
    )
    reason: str = Field(description="분류 이유 한 문장")


class Violation(BaseModel):
    rule_id: str = Field(description="R1~R9, 'FACT'(서류에 없는 수치·사실), 'GRAMMAR'(문법), 'MEANING'(원래 의미·시제 변경)")
    quote: str = Field(description="위반한 영어 구절 그대로")
    fix: str = Field(description="어떻게 고쳐야 하는지")


class ReviewResult(BaseModel):
    passed: bool = Field(description="위반이 하나도 없으면 true")
    violations: List[Violation] = Field(default_factory=list)
    feedback: str = Field(description="재작성 지시 (통과 시 한 줄 칭찬)")
