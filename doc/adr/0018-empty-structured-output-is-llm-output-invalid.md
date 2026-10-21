# ADR-0018: 구조화 출력이 비어 있으면 노드가 LLM_OUTPUT_INVALID로 올린다

- 상태: Proposed (A1 `agent/graph.py` 수정 요청 — A3는 수정하지 않는다)
- 날짜: 2026-10-21
- 작성: api
- 관련: design.md §6 테스트 11, ADR-0012(`LLM_OUTPUT_INVALID`), handoff/core.md, agent/graph.py `_router`·`_coach`

## 배경
ADR-0012는 "ollama 소형 모델의 구조화 출력 실패"를 `LLM_OUTPUT_INVALID`(재시도 가능, "더 큰 모델을 써 주세요")로 보여 주기로 했다.
A3가 실제 모델로 실행해 보니 이 실패가 `UNEXPECTED_ERROR`(재시도 불가, "trace id와 함께 알려 주세요")로 나간다.

- 모델이 Tool 호출 없이 끝나면 `with_structured_output(...).ainvoke()`와 `create_agent(...)["structured_response"]`가 예외 대신 `None`을 돌려준다.
- `agent/graph.py::_router`는 `route.intent`를, `_coach`는 `result["structured_response"].model_dump()`를 `None`에 대해 호출한다. 두 줄 모두 `classify_llm_error`를 거는 `try` 바깥이라 `AttributeError`가 그대로 올라가 `UNEXPECTED_ERROR`가 된다.
- 재현: fake 모델의 빈 응답(기본값 `FAST_MODEL=fake`)은 `_router`에서, Coach가 검색 뒤 텍스트로 끝나는 응답은 `_coach`에서 `AttributeError: 'NoneType' object has no attribute ...`.
  ollama `qwen3:0.6b`(router)·`qwen3:8b`(Coach)로 `sh/smoke_chat.sh ollama`를 2번(턴 시도 6번) 돌렸을 때, 6번 중 5번이 Coach 검색 뒤
  `AttributeError: 'NoneType' object has no attribute 'model_dump'`로 끝났고(서버 로그의 `detail`) 1번만 승인 대기에 도달했다. router는 6번 모두 성공했다.
- 기대와 다른 점: 작업 지시서는 "fake 모델은 빈 응답이라 `LLM_OUTPUT_INVALID`"라고 적었지만 실제 코드는 `UNEXPECTED_ERROR`를 낸다.

## 결정
`_router`와 `_coach`가 구조화 출력이 `None`이면 `CoachError("LLM_OUTPUT_INVALID", detail=...)`를 올린다 (각 한두 줄). Reviewer 서브그래프도 같은 점검이 필요한지 A1이 확인한다.
A3의 `/chat/stream`은 이미 `CoachError`를 코드 그대로 `ErrorRaised`로 바꾸므로 추가 변경이 없다. `sh/smoke_chat.sh fake`는 A1 수정 전후 모두 통과하도록 두 코드를 허용한다.

## 대안 비교
| 대안 | 장점 | 단점 | 기각 이유 |
|---|---|---|---|
| 노드가 `None`을 `LLM_OUTPUT_INVALID`로 (선택) | 원인이 있는 곳에서 분류, ADR-0012의 계층 구분과 일치 | A1 재작업 필요 | — |
| A3가 `AttributeError`를 `LLM_OUTPUT_INVALID`로 매핑 | A1 변경 없음 | 진짜 코드 버그(`AttributeError`)와 구분할 수 없고, Application 계층이 노드 내부 구현을 알게 됨 | 버그를 가려 버린다 |
| `classify_llm_error`가 `AttributeError`도 분류 | 한 곳 수정 | 문제의 두 줄은 `try` 바깥이라 이 함수에 닿지 않음 | 효과 없음 |
| 그대로 둠 | 변경 없음 | 소형 모델 실패가 재시도 버튼 없는 `UNEXPECTED_ERROR`로 표시됨, Before/After의 `LLM_OUTPUT_INVALID` 건수 측정(ADR-0012 검증 방법)이 0으로 나옴 | design §6 테스트 11·ADR-0012 의도와 어긋남 |

## 결과
- 긍정: 소형 모델의 구조화 출력 실패가 재시도 가능한 오류로 보이고, 실패율을 `LLM_OUTPUT_INVALID` 건수로 측정할 수 있다.
- 부정(트레이드오프): 없다. 오류 코드만 바뀐다.
- 후속 조치: Lead가 A1에 전달한다. 반영되면 `sh/smoke_chat.sh`의 fake 모드 허용 코드 목록을 `LLM_OUTPUT_INVALID` 하나로 좁혀도 된다.
- 검증 방법: A1 테스트에 "빈 구조화 출력 → `CoachError.info.code == 'LLM_OUTPUT_INVALID'`"를 추가한다. A3 쪽은 `sh/smoke_chat.sh fake`가 `LLM_OUTPUT_INVALID`를 보고하는지로 확인한다.
