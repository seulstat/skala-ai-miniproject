# ADR-0013: 테스트용 fake 모델에 bind_tools를 추가한 서브클래스를 쓴다

- 상태: Accepted (Lead, 2026-10-21 CP1 1단계)
- 날짜: 2026-10-20
- 작성: core
- 관련: design.md §2 "LLM 계층", ADR-0001(GenericFakeChatModel 채택), agent/llm.py

## 배경
ADR-0001은 테스트에 `GenericFakeChatModel`을 쓰기로 했다. 그런데 Coach는 `create_agent`(ReAct)로
Tool을 고르고, Router·Reviewer는 `with_structured_output`을 쓴다 — 둘 다 내부적으로 `model.bind_tools(...)`를
호출한다. `GenericFakeChatModel`은 `BaseChatModel.bind_tools`를 오버라이드하지 않아 기본 구현이
`NotImplementedError`를 던진다. 실제로 `create_agent(model=GenericFakeChatModel(...), ...).ainvoke(...)`를
실행하면 `bind_tools` 단계에서 바로 예외가 난다 (agent/coach_agent.py·agent/graph.py 단위테스트 작성 중 확인).

## 결정
`agent/llm.py`에 `ToolCallingFakeChatModel(GenericFakeChatModel)`을 두고 `bind_tools`만
`return self`로 오버라이드한다. 테스트는 메시지 큐에 `tool_calls`가 채워진 `AIMessage`를 미리 넣어 두므로
실제 도구 스키마 바인딩은 필요 없다. `make_llm("fake")`도 이 클래스를 쓴다.

## 대안 비교
| 대안 | 장점 | 단점 | 기각 이유 |
|---|---|---|---|
| `GenericFakeChatModel` 그대로 사용 | 계약 변경 없음 | create_agent·with_structured_output에서 즉시 NotImplementedError | design §6 테스트 1~7·10을 fake로 작성할 수 없음 |
| Coach·Router·Reviewer 전부 `.bind_tools` 없이 raw 프롬프트 파싱으로 재작성 | fake 모델 제약 회피 | 실제 LLM(OpenAI·ollama) 경로와 다른 코드가 됨, 10/13 Agent 로직 재사용 불가 | ADR-0001·0002의 전제(create_agent 재사용)와 충돌 |
| LangChain이 제공하는 다른 fake 모델(`FakeListChatModel` 등) | 표준 제공 | 역시 `bind_tools` 미구현 | 동일한 문제 |

## 결과
- 긍정: design §6 테스트 1~7·10을 네트워크 없이 작성·통과시킬 수 있었다 (실제로 확인함).
- 부정(트레이드오프): fake 모델이 도구 스키마 자체는 검증하지 않는다 — 테스트가 틀린 인자 이름을 넣어도
  fake 단계에서는 걸러지지 않는다(실제 모델·ollama/OpenAI 스모크에서는 정상적으로 걸러짐).
- 후속 조치: 없음. 다른 역할이 fake 모델로 create_agent 계열 코드를 테스트할 때도 이 클래스를 재사용할 수 있다.
- 검증 방법: tests/test_core_router.py·test_core_reviewer.py·test_core_graph.py 전부 이 클래스로 통과.
