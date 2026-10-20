# ADR-0001: LLM 계층을 LangChain 모델로 통일하고 fast/quality 분리

- 상태: Accepted
- 날짜: 2026-10-20
- 작성: Lead
- 관련: design.md §2 "LLM 계층"·"모델 분리"

## 배경
Base 골격(all_total_vue_student)은 httpx로 직접 호출하는 자체 LLM 클래스(`OllamaFastLLM`·`OpenAIQualityLLM` 등)를 쓴다.
10/13 버전은 `init_chat_model`로 만든 LangChain 모델 하나(`DAPDAP_MODEL`)를 쓰고, `create_agent`·`with_structured_output`에 의존한다.
두 코드를 합치려면 LLM 계층을 하나로 정해야 한다. 또 router처럼 가벼운 호출과 카드 생성·검수처럼 품질이 중요한 호출의 비용·지연이 다르다.

## 결정
모든 LLM은 LangChain `BaseChatModel`로 통일하고 `init_chat_model("provider:model")`로 만든다.
환경변수 `FAST_MODEL`(router)과 `QUALITY_MODEL`(Coach·Reviewer)을 분리하고, 값이 `fake`면 `GenericFakeChatModel`을 쓴다.

## 대안 비교
| 대안 | 장점 | 단점 | 기각 이유 |
|---|---|---|---|
| Base의 httpx LLM 클래스 유지 | Base 코드 그대로, 의존성 적음 | `create_agent`·`ToolStrategy`·구조화 출력을 직접 구현해야 함 | 10/13 Agent 로직을 재사용할 수 없음 |
| 모델 하나(10/13 `DAPDAP_MODEL`) | 설정 단순 | router까지 큰 모델을 써서 비용·지연 증가 | Base의 fast/quality 비용 분리 개념을 잃음 |
| 노드마다 모델 환경변수 | 가장 세밀함 | 설정 폭증, 측정 조건 고정이 어려움 | MVP에 과함 |

## 결과
- 긍정: 10/13의 `create_agent`·구조화 출력 코드를 그대로 쓴다. fake 모델로 네트워크 없이 테스트할 수 있다. ollama ↔ OpenAI 전환이 환경변수 하나로 끝난다.
- 부정(트레이드오프): langchain 계열 의존성이 커진다. ollama 소형 모델은 구조화 출력 실패율이 높을 수 있다(design §7 한계 3).
- 후속 조치: A1이 `agent/llm.py`에 팩토리를 구현한다. Before/After 측정은 `openai:gpt-4o-mini`로 고정한다(ADR-0009).
- 검증 방법: design §6 테스트 전부가 `fake` 모델로 통과, CP2 ollama 스모크, CP4 OpenAI E2E.
