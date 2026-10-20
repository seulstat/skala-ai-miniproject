# ADR-0012: 오류 처리를 4계층 분류 + 재시도 가능 여부 + ErrorRaised 이벤트로

- 상태: Accepted
- 날짜: 2026-10-20
- 작성: Lead
- 관련: design.md §2 "오류 처리"·§5·§6, contracts/errors.py·events.py·api.py, supersedes ADR-0006의 "오류는 FinalAnswer(error=True)" 부분
- 근거 자료: AI Capstone 강의자료(2026-10-16) p.18 "4-Layer + Graceful Degradation", p.174~177 Transient Error·with_retry·Exponential Backoff, p.202~204 Error 격리, p.236 로그 표준화

## 배경
CP0 초안 계약은 처리 중 오류를 `FinalAnswer(error=True)` 하나로 끝냈다. 이 방식은 오류 코드·재시도 가능 여부·사용자용 문구를 담지 못해, 화면이 오류 종류마다 다른 안내를 할 수 없었다.
강의자료는 이를 "단일 try/except로 로깅만"(p.18 C안)으로 기각하고, 실패를 국소적 이벤트로 다루며 "재시도 가능" vs "복구 불가"를 프런트엔드가 구분해 보여 줄 것을 요구한다.
이 서비스에는 실패 지점이 여러 곳 있다. MCP 검색 timeout, MCP 서버 다운, ollama 소형 모델의 구조화 출력 실패, API 키 오류, 준비 미완료, 이미 처리된 승인, 저장 실패가 그것이다.

## 결정
`contracts/errors.py`에 오류 코드 16개를 고정하고, 코드마다 계층(tool·orchestration·application·presentation), 재시도 가능 여부, 치명 여부, HTTP 상태, 사용자 메시지를 정한다.
- **Tool**: `asyncio.TimeoutError`만 0.5초 → 1.5초 백오프로 최대 2회 재시도하고, 소진·영구 오류는 `ToolError`로 바꾼다.
- **Orchestration**: 검색 하나의 실패는 격리하고 나머지 근거로 카드를 만든다(`EvidenceSearched.error`, 치명 아님). LLM 검수가 실패하면 규칙 검사만으로 진행한다(`REVIEWER_DEGRADED`). LLM 실패는 `CoachError`로 올린다.
- **Application**: `CoachError`는 SSE `ErrorRaised{error}` → `[DONE]`, REST `ErrorResponse{error}` + 코드별 상태로 바꾼다. 분류되지 않은 예외는 `UNEXPECTED_ERROR`로 처리한다.
- **Presentation**: `user_message`를 보여 주고, `recoverable`이면 다시 시도 버튼을, 아니면 조치 안내(예: 준비 탭 이동)를 둔다. SSE가 끊기면 `/chat/pending`으로 상태를 확인한다.
- 내부 원인(`detail`)은 로그·trace에만 남기고, 로그 필드 이름은 `LOG_FIELDS`로 통일한다.

## 대안 비교
| 대안 | 장점 | 단점 | 기각 이유 |
|---|---|---|---|
| `FinalAnswer(error=True)` 하나로 종료 (CP0 초안) | 이벤트 종류가 늘지 않음 | 코드·재시도 가능 여부·사용자 문구가 없음, 부분 실패를 표현 못 함 | 강의 p.18 C안과 같은 수준 |
| Fail-fast (오류 하나면 요청 전체 실패) | 구현 단순 | 검색 하나가 timeout이어도 카드 생성 실패 | 강의 p.18 A안, 사용성 저하 |
| 모든 예외를 일괄 재시도 | 코드 단순 | 영구 오류에 시간 낭비 (wave09 실측 약 1초) | 강의 p.174 |
| HTTP 상태 코드만으로 구분 | 표준 | SSE 스트림 중간 오류를 표현 못 함 | SSE 구조와 불일치 |

## 결과
- 긍정: 오류 종류마다 다른 안내와 다시 시도 버튼을 둘 수 있다. 검색 일부가 실패해도 카드가 나온다. 오류 표가 PPT "오류 처리·한계" 근거가 된다.
- 부정(트레이드오프): 계약·이벤트·fixture가 늘고, 역할마다 오류 변환 코드가 생긴다. 근거가 빠진 카드는 사실 오류(FACT) 위험이 커지므로 승인 화면에 알림을 반드시 보여야 한다.
- 후속 조치: A1 `agent/tools.py`(with_retry + ToolError, Base `retry.py`의 기본값을 `RETRY_*`로 맞춤)·LLM 오류 분류, A2 MCPPort 오류 계약, A3 예외 → ErrorRaised·ErrorResponse 변환, A4 코드별 화면.
- 검증 방법: design §6 테스트 10(A1)·11(A3), fixtures `sse_evidence_degraded`·`sse_error_recoverable`·`sse_error_not_ready` 재생(A4), Before/After에서 ollama 구조화 출력 실패율을 `LLM_OUTPUT_INVALID` 건수로 측정.
