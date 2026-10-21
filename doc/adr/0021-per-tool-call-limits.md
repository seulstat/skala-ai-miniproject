# ADR-0021: Coach의 Tool 호출 상한을 검색 Tool별로 건다

- 상태: Accepted
- 날짜: 2026-10-21
- 작성: Lead
- 관련: design.md §2 Multi-Agent, 강의 p.169 Loop Guard, agent/coach_agent.py, ADR-0004

## 배경
CP4 측정 준비 중 `QUALITY_MODEL=openai:gpt-4o-mini`로 v2를 돌리자 카드 생성 요청이 10분 넘게 끝나지 않았다.
`ToolCallLimitMiddleware(run_limit=4)`를 Tool 이름 없이 걸어 두어, `ToolStrategy`가 카드를 내보내는 `ExpressionCard` 호출까지 상한에 포함됐다.
검색을 여러 번 하는 모델은 상한을 다 쓴 뒤 카드 출력이 계속 차단돼 무한 반복했다. ollama 소형 모델은 검색을 적게 해서 우연히 드러나지 않았다.

## 결정
검색 Tool별로 상한을 둔다: `search_my_experience` 2회, `get_job_posting` 1회, `search_expression_bank` 1회(합계 4회, 기존과 같음). 카드 출력 호출은 상한 대상이 아니다.

## 대안 비교
| 대안 | 장점 | 단점 | 기각 이유 |
|---|---|---|---|
| 이름 없는 전체 상한 유지 (10/13) | 설정 하나 | 카드 출력까지 막혀 무한 반복 | 버그 |
| `exit_behavior="end"`로 상한 도달 시 종료 | 무한 반복은 막음 | 카드 없이 끝나 `LLM_OUTPUT_INVALID` | 근거는 충분한데 결과를 버림 |
| 상한 제거 | 단순 | Loop Guard 없음 (강의 p.169) | 비용·지연 상한이 사라짐 |

## 결과
- 긍정: gpt-4o-mini 카드 생성 6.3초로 정상 종료. Loop Guard는 유지.
- 부정(트레이드오프): Tool별 상한이 고정이라 같은 Tool을 더 쓰고 싶은 질문에는 근거가 부족할 수 있다.
- 후속 조치: Before/After의 Tool 호출 수 지표로 상한 도달 빈도를 본다.
- 검증 방법: CP4 v2 측정 완주, check.sh.
