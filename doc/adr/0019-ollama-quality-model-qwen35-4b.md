# ADR-0019: ollama 품질 모델을 qwen3:8b에서 qwen3.5:4b로 바꾼다

- 상태: Accepted
- 날짜: 2026-10-21
- 작성: Lead
- 관련: design.md §7 한계 3, ADR-0001, work-plan §9 위험, sh/smoke_chat.sh

## 배경
CP2 기준은 "ollama로 승인 → 저장까지 정상 경로"다. 그런데 `QUALITY_MODEL=ollama:qwen3:8b`의 Coach 카드 구조화 출력(`ToolStrategy(ExpressionCard)`)이 계속 실패했다.
A3 측정 1/6 성공, Lead CP2 스모크 0/3 성공(모두 `LLM_OUTPUT_INVALID`). router(qwen3:0.6b)와 실제 임베딩 기반 MCP 검색은 정상이었다.

## 결정
ollama 기본 품질 모델을 `ollama:qwen3.5:4b`로 바꾼다(`.env.example`, `sh/smoke_chat.sh` 기본값, agent.md). 최종 확인·Before/After 측정은 계획대로 `openai:gpt-4o-mini`다(ADR-0009).

## 대안 비교
| 대안 | 장점 | 단점 | 기각 이유 |
|---|---|---|---|
| qwen3:8b 유지 + 프롬프트·ToolStrategy 조정 | 모델 교체 없음 | 원인 분석·반복 실험에 시간이 들고 성공 보장 없음 | 일정(Day2 오후) |
| CP2 정상 경로를 OpenAI로만 확인 | 성공률 높음 | ollama 선택지(개인정보 완화, 한계 4)가 실제로 동작하는지 보이지 못함, 키 필요 | ollama로 통과 가능한 모델이 있음 |
| qwen3.5:4b (채택) | 설치돼 있음, 더 작은데도 CP2 스모크 1/1 성공(첫 시도) | 표본 1건, 품질 미측정 | — |

## 결과
- 긍정: CP2 정상 경로(stream → 승인 대기 → resume → 저장)가 ollama에서 통과했다.
- 부정(트레이드오프): 성공 표본이 적다. 소형 모델의 구조화 출력 실패율은 한계 3으로 남는다.
- 후속 조치: Day3 측정 때 qwen3:8b·qwen3.5:4b·gpt-4o-mini의 `LLM_OUTPUT_INVALID` 비율을 같은 입력으로 비교해 PPT 한계 자료로 쓴다.
- 검증 방법: `bash sh/smoke_chat.sh ollama` (기본값 qwen3.5:4b) 통과.
