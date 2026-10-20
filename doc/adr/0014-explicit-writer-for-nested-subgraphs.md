# ADR-0014: 중첩 서브그래프·Tool에는 get_stream_writer()를 직접 부르지 않고 바깥 노드가 캡처해 넘긴다

- 상태: Proposed
- 날짜: 2026-10-20
- 작성: core
- 관련: design.md §2 "Multi-Agent"·§5 SSE 이벤트, ADR-0002(MCP 래퍼 Tool), ADR-0004(Coach·Reviewer 서브그래프)

## 배경
`EvidenceSearched`는 Coach가 고르는 Tool 호출마다 보내야 한다(ADR-0002). Tool은 `create_agent`가
만든 서브그래프 안에서 실행되고, 이 서브그래프는 Supervisor의 `coach` 노드가 `agent.ainvoke(...)`로
호출한다. 직접 실험해 보니, Tool 함수 안에서 `langgraph.config.get_stream_writer()`를 호출해도
**Supervisor의 `astream(..., stream_mode="custom")`로는 전달되지 않는다** — 중첩된 컴파일 그래프를
`ainvoke()`로 호출하면 그 안에서 만든 새 Pregel 실행이 자신만의 writer 컨텍스트를 쓰기 때문으로 보인다.
Reviewer 서브그래프(ADR-0004)도 같은 구조라 `ReviewDone`에 동일한 문제가 생길 수 있었다.

## 결정
이벤트를 보내야 하는 바깥 노드(`coach`, `reviewer`)가 자기 자신의 실행 컨텍스트에서
`writer = get_stream_writer()`를 한 번 받아 두고, 이를 Tool 팩토리(`agent/tools.py::build_agent_tools`)에
파라미터로 넘겨 Tool 클로저가 그 writer를 직접 호출하게 한다. Reviewer는 더 간단하게, 서브그래프 안에서는
이벤트를 보내지 않고 서브그래프가 돌려준 결과(`review`, `error`)를 바깥 `reviewer` 노드가 받아
`ReviewDone`을 직접 보낸다.

## 대안 비교
| 대안 | 장점 | 단점 | 기각 이유 |
|---|---|---|---|
| Tool·서브그래프 안에서 `get_stream_writer()`를 그대로 호출 | 코드가 단순, langgraph 문서 예시와 동일 | 실측 결과 중첩 `ainvoke()` 경로에서는 이벤트가 바깥 스트림으로 전달되지 않음 | 테스트로 재현 확인(/tmp 프로토타입, 재현 스크립트는 코드에는 없음) |
| 중첩 그래프 호출 시 같은 `config`를 넘겨 컨텍스트를 공유 시도 | 변경 범위 작음 | 실측 결과에도 전달 안 됨 (config 전달만으로는 부족) | 동일 |
| `stream_mode=["custom", "updates"]` 등으로 하위 스트림 수동 중계 | 표준 API만 사용 | Tool 내부 1회성 이벤트를 위해 전체 스트림을 중계해야 해 구조가 복잡해짐 | 클로저로 writer를 넘기는 쪽이 더 단순하고 테스트하기 쉬움(writer를 list.append로 교체해 단위테스트 가능) |

## 결과
- 긍정: `EvidenceSearched`·`CardDrafted`·`ReviewDone` 이벤트가 실제로 Supervisor의 `astream(stream_mode="custom")`에
  전부 나타남을 확인했다(tests/test_core_graph.py). Tool 단위테스트도 writer를 평범한 콜러블로 넘겨 쉽게 검증할 수 있다.
- 부정(트레이드오프): Tool 팩토리(`build_agent_tools`)·Coach 빌더(`build_coach_agent`)가 매 요청 다시 만들어진다
  (ref 10/13과 같은 패턴이라 추가 비용은 아니지만, 전역 Tool 객체를 재사용하던 10/13과 달리 매 라운드 재생성됨).
- 후속 조치: A3가 `/chat/stream`에서 `graph.astream(..., stream_mode="custom")`을 그대로 쓰면 되고, 별도 처리가 필요 없다.
- 검증 방법: tests/test_core_graph.py의 `events.is_valid_sequence` 검사, tests/test_core_tools.py(writer를 list로 교체).
