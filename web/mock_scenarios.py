"""MOCK 시나리오 표 (담당 A4). /chat/stream이 메시지의 #태그로 재생할 sse_*.json을 고른다."""

import re

# 태그 → fixture. 태그가 없으면 pick이 메시지로 추정한다
SCENARIOS = {
    "#approve": "sse_express_approve.json", "#answer": "sse_answer_approve.json",
    "#review": "sse_review.json", "#oos": "sse_out_of_scope.json",
    "#warning": "sse_express_warning.json", "#degraded": "sse_evidence_degraded.json",
    "#error": "sse_error_recoverable.json", "#notready": "sse_error_not_ready.json",
    "#disconnect": "sse_express_approve.json", "#drop": "sse_express_approve.json",
}
# 화면의 MOCK 칩 (실제 백엔드에는 이 칩이 없다). #error·#drop은 첫 시도만 실패하고 다시 시도하면 성공한다
MOCK_CHIPS = [
    ("검수 미통과 경고", "배송 지연을 내가 혼자 다 해결했다고 말하고 싶어 #warning"),
    ("근거 검색 일부 실패", "배송 지연 원인을 데이터로 찾아서 민원을 줄였다고 말하고 싶어 #degraded"),
    ("복구 가능 오류", "피드백으로 접근 방식을 바꾼 경험을 답변하고 싶어 #error"),
    ("준비 미완료", "영어 자기소개를 하고 싶어 #notready"),
    ("범위 밖", "오늘 점심 뭐 먹지? #oos"),
    ("연결 끊김 (승인 대기 있음)", "납기를 지킨 경험을 말하고 싶어 #disconnect"),
    ("연결 끊김 (대기 없음)", "협업 경험을 말하고 싶어 #drop"),
]


def pick(message: str) -> str:
    for tag, name in SCENARIOS.items():
        if tag in message:
            return name
    if "복습" in message:
        return "sse_review.json"
    return "sse_express_approve.json" if re.search(r"[가-힣]", message) else "sse_answer_approve.json"
