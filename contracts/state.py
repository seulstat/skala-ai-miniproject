"""[계약] Supervisor 메인 그래프의 상태와 노드 이름. Lead만 수정한다.

10/13 dapdap/graph.py의 AgentState를 이어받았다. 체크포인터(AsyncSqliteSaver)에 저장되므로
값은 JSON으로 직렬화되는 기본형(dict·list·str·int·bool)만 쓴다. Pydantic 모델은 `.model_dump()`로 넣는다.
"""

from typing import TypedDict

# 재작성 상한. Reviewer 라운드는 최대 MAX_REWRITES + 1번 (초안 1 + 재작성 2).
# retry_count >= MAX_REWRITES인데 미통과면 warning을 달고 approve로 간다 (design §6 테스트 3)
MAX_REWRITES = 2


class AgentState(TypedDict, total=False):
    user_input: str
    today: str                 # YYYY-MM-DD. 테스트에서 날짜를 고정할 때 넣는다 (비우면 오늘)
    intent: str                # contracts.schemas.Intent
    card: dict                 # ExpressionCard.model_dump()
    review: dict               # ReviewResult.model_dump() — 마지막 라운드
    retry_count: int           # 0부터. 재작성할 때마다 +1
    warning: str               # 재작성 상한 초과 시 위반 요약
    approved: bool             # approve 노드의 resume 값
    tools_used: list           # [{"tool": str, "query": str}] — EvidenceSearched와 같은 내용
    review_log: list           # [{"round", "passed", "violations"}] — ReviewDone과 같은 내용
    saved_card_id: str         # save 노드 결과
    next_review: str           # save 노드 결과 (YYYY-MM-DD)
    final_message: str         # FinalAnswer.reply 또는 save/rejected 안내 문구
    notices: list              # ErrorInfo.model_dump() — 치명 아닌 오류 (Tool 실패, 검수 저하). ADR-0012


class ResumeValue(TypedDict):
    """`Command(resume=...)`에 넣는 값. /chat/resume의 approve를 그대로 담는다."""
    approve: bool


# 노드 이름 (design §2). 테스트 1(intent → 노드 매핑)과 trace 태그가 이 이름을 쓴다
NODE_ROUTER = "router"
NODE_COACH = "coach"
NODE_REVIEWER = "reviewer"
NODE_APPROVE = "approve"
NODE_SAVE = "save"
NODE_REJECTED = "rejected"
NODE_REVIEW_CARDS = "review_cards"
NODE_OUT_OF_SCOPE = "out_of_scope"

INTENT_TO_NODE: dict[str, str] = {
    "express": NODE_COACH,
    "answer": NODE_COACH,
    "review": NODE_REVIEW_CARDS,
    "out_of_scope": NODE_OUT_OF_SCOPE,
}
