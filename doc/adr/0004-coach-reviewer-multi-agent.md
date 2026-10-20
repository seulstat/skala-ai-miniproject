# ADR-0004: Coach·Reviewer 멀티에이전트로 전환

- 상태: Accepted
- 날짜: 2026-10-20
- 작성: Lead
- 관련: design.md §2·§3, supersedes 10/13 02_architecture.md "단일 Agent + Reviewer 노드"

## 배경
10/13 버전은 흐름이 하나라 Supervisor가 과하다고 보고 단일 Agent에 Reviewer 노드만 두었다.
이번 과제는 평가 기준에 Multi-Agent가 명시돼 있고, 검수가 생성 맥락에 끌려가는 문제
(GPT Reviewer 진동, 의미 왜곡 — 10/13 평가 §5.3 #5)가 이미 관찰됐다.

## 결정
Coach(ReAct, Tool 선택)와 Reviewer(LLM + 규칙 검사)를 각각 컴파일된 서브그래프로 분리하고,
메인 그래프가 Supervisor로서 라우팅·재시도 상한(`MAX_REWRITES=2`)·승인을 통제한다.
Reviewer는 MCP Prompt `persona_review_prompt`로 검수 규칙을 받고, `banned_hits` regex 결과는 LLM 판정과 관계없이 위반으로 확정한다.

## 대안 비교
| 대안 | 장점 | 단점 | 기각 이유 |
|---|---|---|---|
| 단일 Agent + Reviewer 노드 (10/13) | 단순, 호출 수 적음 | 검수가 같은 그래프 상태를 공유, Multi-Agent 근거 약함 | 평가 기준 미충족 |
| Supervisor + Writer·Researcher·Reviewer 3개 이상 | 역할 세분화 | 호출 수·지연·디버깅 부담, 2.5일 일정 초과 | MVP 범위 초과 |

## 결과
- 긍정: 검수가 생성 맥락과 분리되어 독립적으로 판단한다. 서브그래프 단위로 단위테스트할 수 있다.
- 부정(트레이드오프): 서브그래프 경계에서 상태 변환 코드가 늘고, 호출 오버헤드가 생긴다.
- 후속 조치: Before/After에서 재작성 횟수·지연을 비교한다.
- 검증 방법: design §6 테스트 2·3, design §7 재작성 횟수 지표.
