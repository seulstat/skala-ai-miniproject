# ADR-0006: HITL 재개는 JSON resume + pending 조회

- 상태: Accepted (오류 처리 부분은 ADR-0012가 대체)
- 날짜: 2026-10-20
- 작성: Lead
- 관련: design.md §2 "HITL", §5 API·SSE, contracts/api.py·events.py

## 배경
승인 전에는 카드를 저장하지 않는 HITL이 필수다. 그래프는 approve 노드에서 `interrupt()`로 멈춘다.
브라우저 `EventSource`는 GET만 지원해 POST로 재개하면서 스트림을 받을 수 없다. 10/13 CLI는 `InMemorySaver`라 재시작하면 승인 대기가 사라졌다.

## 결정
`/chat/stream`(GET, SSE)은 `ApprovalRequired`를 보내고 `[DONE]`으로 끝난다. 승인·거절은 `POST /chat/resume {thread_id, approve}`가 JSON(`{saved, card_id, next_review}`)으로 답한다.
새로고침·재시작 후에는 `GET /chat/pending?thread_id`가 체크포인터의 interrupt payload(`ApprovalRequest`)를 돌려준다. 체크포인터는 `AsyncSqliteSaver`(checkpoints.db)다.
~~처리 중 오류도 이벤트 종류를 늘리지 않고 `FinalAnswer(error=True)` → `[DONE]`으로 끝낸다.~~ → ADR-0012(`ErrorRaised`)로 대체.
승인은 매 응답이 아니라 **저장 직전에만** 받는다. 생성·검수 과정은 그대로 스트리밍되므로, 강의자료 p.17 D안이 지적한 "사람 검수가 실시간 UX와 상충" 문제를 피한다.

## 대안 비교
| 대안 | 장점 | 단점 | 기각 이유 |
|---|---|---|---|
| resume도 SSE(fetch + ReadableStream POST) | 저장 후 메시지도 스트림 | 클라이언트 파싱 코드 2종, 프록시 처리 복잡 | resume 결과는 한 번의 응답이면 충분 |
| WebSocket 양방향 | 하나의 연결로 처리 | 서버·프록시·재연결 구현 부담 | MVP에 과함 |
| `InMemorySaver` 유지 | 설정 없음 | 재시작 시 승인 대기 소실 | 영속화가 개선 포인트 |
| `AsyncPostgresSaver` (강의자료 p.21 채택안) | 재시작 내구성 + 다중 인스턴스 공유 | DB 서버 설치·운영, 시연 환경 복잡 | 단일 사용자·단일 인스턴스 전제(ADR-0008)에서는 SQLite로 충분. 다중 인스턴스 불가는 한계로 기록 |

## 결과
- 긍정: 재시작 후에도 승인 대기가 복원된다(design §7 "0/N → N/N"). 프론트는 EventSource 하나와 fetch만 쓴다.
- 부정(트레이드오프): 체크포인트 DB가 대화 수에 따라 커진다(design §7 한계 2). 카드 생성은 토큰 스트리밍 없이 단계 이벤트로만 보인다. SQLite 파일 잠금 때문에 서버를 여러 인스턴스로 띄워 상태를 공유할 수 없다(design §7 한계 4).
- 후속 조치: A1 approve·save, A3 `/chat/resume`·`/chat/pending`, A4 pending 복원 UI.
- 검증 방법: design §6 테스트 4·5·6, CP2 서버 재시작 후 pending 복원, CP3 새로고침 복원.
