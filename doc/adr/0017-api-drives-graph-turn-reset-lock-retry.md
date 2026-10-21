# ADR-0017: API가 그래프를 구동하는 규칙 — 새 턴 입력 초기화, 승인 직렬화, 저장 실패 재시도

- 상태: Accepted (Lead, 2026-10-21 CP2) — 1번(새 턴 초기화)은 그래프 router에서도 보장하도록 보강
- 날짜: 2026-10-21
- 작성: api
- 관련: design.md §5 (`/chat/stream`·`/chat/resume`·`/chat/pending`), ADR-0006(HITL), ADR-0012(`STORE_ERROR`), agent/graph.py (A1 소유, 수정하지 않음)

## 배경
브라우저는 `thread_id`를 하나만 쓴다(localStorage). 그래서 같은 thread에서 메시지를 여러 번 보내고, 상태 채널은 체크포인터에 계속 남는다.
A3 통합 테스트로 실측한 문제가 셋이다.

1. **이전 턴의 값이 새 턴에 묻어온다.** `_router`는 `retry_count`·`tools_used`·`review_log`·`notices`만 비우고 `review`·`warning`은 비우지 않는다.
   재작성 상한을 넘겨 경고가 달린 카드를 처리한 다음 턴에서, 검수를 한 번에 통과한 새 카드의 `ApprovalRequired.warning`에 지난 경고가 그대로 나왔다.
   `_coach`는 `review`가 남아 있으면 지난 카드와 피드백을 새 요청에 붙인다.
2. **승인 버튼 연타.** 같은 `/chat/resume`이 겹쳐 들어오면 둘 다 승인 대기를 보고 `Command(resume=...)`를 실행한다. 이미 끝난 thread에 두 번째 재개가 가는 동작은 정의되어 있지 않다.
3. **저장 실패 뒤 재시도가 막힌다.** `save` 노드가 `STORE_ERROR`로 실패하면 `approve`는 이미 끝나 있다. 이 상태의 `aget_state()`는 `interrupts`가 비고 `next == ("save",)`다.
   `STORE_ERROR`의 사용자 문구는 "승인 버튼을 다시 눌러 주세요"인데, `interrupts`만 보면 두 번째 요청은 `409 NO_PENDING`이 된다.

## 결정
세 가지 모두 `routers/chat.py` 안에서 처리하고 그래프는 건드리지 않는다.

1. `/chat/stream`은 입력에 `FRESH_TURN = {review, warning, saved_card_id, next_review: None}`을 함께 넣어, 새 턴이 이전 값을 읽지 못하게 한다.
2. `/chat/resume`은 `thread_id`별 `asyncio.Lock`(앱 상태 `thread_locks`)으로 직렬화한다. 락 안에서 승인 대기를 다시 조회하므로 두 번째 요청은 `409 NO_PENDING`을 받는다.
3. `/chat/resume`은 `interrupts`가 비어 있어도 `approve=true`이고 `next == ("save",)`이면 `graph.ainvoke(None, config)`로 저장 노드만 다시 실행한다. `approve=false`는 이미 승인된 카드를 거절할 수 없어 `409 NO_PENDING`이다.

## 대안 비교
| 대안 | 장점 | 단점 | 기각 이유 |
|---|---|---|---|
| (1) A1의 `_router`가 `review`·`warning`을 초기화 | 근본 원인이 있는 곳에서 해결, 다른 호출자도 안전 | `agent/`는 A3가 수정할 수 없고 A1 재작업이 필요 | 지금은 불가. **A1이 고치면 `FRESH_TURN`은 지운다** (후속 조치) |
| (1) 턴마다 새 `thread_id` | 상태가 섞이지 않음 | `/chat/pending`이 찾을 키가 바뀌어 새로고침 복원이 깨짐 | HITL 복원(ADR-0006)과 충돌 |
| (1) 그대로 둠 | 코드 없음 | 지난 경고가 새 카드 승인 화면에 나옴(실측) | 사용자에게 틀린 정보를 보여 줌 |
| (2) 락 없이 처리 | 코드 없음 | 연타 시 동작 불명 | 이미 끝난 thread에 재개를 보내게 됨 |
| (2) DB 수준 락 | 다중 인스턴스에서도 유효 | SQLite 체크포인터에는 해당 기능이 없고 과함 | 단일 프로세스 전제(ADR-0008) |
| (3) 재시도 불허(`interrupts`만 확인) | 구현 단순 | `STORE_ERROR` 문구와 모순, 승인한 카드를 영영 저장하지 못함 | 사용자가 막다른 길에 놓임 |
| (3) `save` 노드 안에서 자체 재시도 | API가 단순 | `agent/` 수정 필요 | 소유권 |

## 결과
- 긍정: 같은 thread에서 대화를 이어도 승인 화면이 정확하다. 연타해도 카드가 한 번만 저장된다. `STORE_ERROR` 뒤 "다시 시도"가 실제로 동작한다.
- 부정(트레이드오프): `FRESH_TURN`이 그래프 상태 키 이름(`review`·`warning`…)에 의존한다. `thread_locks`는 thread 수만큼 메모리에 남는다(단일 사용자라 무시 가능).
  저장 실패 상태에서는 `/chat/pending`이 `null`이라, 그 사이 새로고침하면 승인 화면이 사라진다(저장 재시도 요청 자체는 계속 가능).
- 후속 조치: Lead가 (1)을 A1 요청으로 올릴지 결정한다. A1이 `_router`에서 초기화하면 `routers/chat.py`의 `FRESH_TURN`을 삭제한다.
- 검증 방법: `tests/test_api_chat_state.py` — `test_new_message_on_same_thread_does_not_inherit_previous_warning`, `test_concurrent_resume_saves_only_once`, `test_store_error_on_approve_can_be_retried`. 각 규칙을 일부러 빼면 해당 테스트가 실패하는 것을 확인했다.
