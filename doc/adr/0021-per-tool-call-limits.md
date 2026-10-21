# ADR-0021: Coach의 검색 상한은 '검색 Tool 숨기기'로 건다

- 상태: Accepted
- 날짜: 2026-10-21
- 작성: Lead
- 관련: design.md §2 Multi-Agent, 강의 p.169 Loop Guard, agent/coach_agent.py, ADR-0004

## 배경
CP4 측정 준비 중 `QUALITY_MODEL=openai:gpt-4o-mini`로 v2를 돌리자 카드 생성 요청이 10분 넘게 끝나지 않았다.
`ToolCallLimitMiddleware(run_limit=4)`를 Tool 이름 없이 걸어 두어, `ToolStrategy`가 카드를 내보내는 `ExpressionCard` 호출까지 상한에 포함됐다.
검색을 여러 번 하는 모델은 상한을 다 쓴 뒤 카드 출력이 계속 차단돼 무한 반복했다. ollama 소형 모델은 검색을 적게 해서 우연히 드러나지 않았다.

## 결정
검색 예산 미들웨어(`agent/search_budget.py::SearchBudgetMiddleware`)를 쓴다. 이번 생성에서 검색 Tool 호출이 4회에 닿으면, 다음 모델 호출부터 **검색 Tool을 모델에게 보여 주지 않는다.** 남은 선택지는 카드 출력(ExpressionCard)뿐이라 반드시 끝난다.

1차 수정(검색 Tool별 `ToolCallLimitMiddleware`, 2·1·1회)은 카드 출력 차단은 풀었지만, 상한을 넘은 검색이 오류 메시지로 막힐 뿐이라 gpt-4o-mini가 막힌 검색을 계속 다시 불러 같은 문장(S01)에서 2회 중 2회 120초 초과가 났다. 검색 Tool 숨기기로 바꾼 뒤 같은 문장 3회 모두 7초 안팎으로 끝났다.

## 대안 비교
| 대안 | 장점 | 단점 | 기각 이유 |
|---|---|---|---|
| 이름 없는 전체 상한 유지 (10/13) | 설정 하나 | 카드 출력까지 막혀 무한 반복 | 버그 |
| `exit_behavior="end"`로 상한 도달 시 종료 | 무한 반복은 막음 | 카드 없이 끝나 `LLM_OUTPUT_INVALID` | 근거는 충분한데 결과를 버림 |
| 상한 제거 | 단순 | Loop Guard 없음 (강의 p.169) | 비용·지연 상한이 사라짐 |
| 검색 Tool별 ToolCallLimitMiddleware(1차 수정) | 카드 출력 차단은 해결 | 막힌 검색을 모델이 계속 다시 불러 반복 | 실측 S01 2/2 시간 초과 |

## 결과
- 긍정: gpt-4o-mini 카드 생성 6~8초로 정상 종료(S01 3/3). Loop Guard는 유지. v1(10/13)에는 같은 결함이 남아 있어 Before/After에서 시간 초과로 드러난다.
- 부정(트레이드오프): 상한 4회가 고정이라 근거가 더 필요한 질문에서는 부족할 수 있다. LangChain 미들웨어 내부 API(ModelRequest.override)에 기대고 있다.
- 후속 조치: Before/After의 Tool 호출 수 지표로 상한 도달 빈도를 본다.
- 검증 방법: CP4 v2 측정 완주, check.sh.
