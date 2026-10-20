# ADR-0011: Deps 정의를 contracts/deps.py로, 조립은 agent/deps.py build_deps()

- 상태: Accepted
- 날짜: 2026-10-20
- 작성: Lead
- 관련: design.md §2 구조도·"DI 위치", §3 DI 행, contracts/deps.py·schemas.py

## 배경
design.md 초안은 `Deps` 클래스를 `agent/deps.py`에 두었다. 그런데 `agent/`는 A1 소유이고, `Deps`는 A3(server.py lifespan)·A2(MCPPort 구현)·모든 테스트가 import한다.
정의가 A1 파일에 있으면 다른 역할이 필드 하나를 바꾸려 해도 A1 파일을 고쳐야 하고, 병렬 작업 중 인터페이스가 흔들린다.
또 COACH_DATA_DIR 아래 파일 경로(profile·docs·posting·coach.db·checkpoints.db·캐시)를 A1·A2·A3가 각자 정하면 어긋난다.

## 결정
`Deps` dataclass와 포트(`MCPPort`·`CardStore` Protocol, 모두 async)는 `contracts/deps.py`에 두고 Lead만 수정한다. `agent/deps.py`에는 조립 함수 `build_deps()`만 둔다.
`Deps`에 `paths: DataPaths` 필드를 추가해 데이터 파일 배치를 한 곳에서 정한다.
같은 이유로 공용 모델(SavedCard·ApprovalRequest·PostingDraft 등)도 `contracts/schemas.py`에 추가하고, 10/13 `schemas.py`의 evidence 예시는 실제 경력 대신 sample_user 라벨로 바꾼다.

## 대안 비교
| 대안 | 장점 | 단점 | 기각 이유 |
|---|---|---|---|
| `agent/deps.py`에 정의와 조립 모두(design 초안) | 파일 하나 | A3·A2·테스트가 A1 소유 파일에 의존, 소유권 충돌 | 병렬 작업 중 인터페이스 불안정 |
| 10/13 `config.py`식 모듈 전역 상수·싱글턴 | 코드 적음 | 숨은 의존성, 테스트에서 교체 어려움, import 시점 부작용 | DI 요구사항과 충돌 |
| 경로를 환경변수로 각자 계산 | 계약 필드 불필요 | 역할마다 파일 이름이 어긋날 위험 | 통합 위험 |

## 결과
- 긍정: 모든 역할이 같은 인터페이스를 import한다. fake MCP·fake store로 그래프를 테스트할 수 있다. 경로가 한 곳에 있다.
- 부정(트레이드오프): design 초안의 `Deps(fast_llm, quality_llm, mcp, store, checkpointer)`에 `paths`가 늘었다. 계약 변경은 Lead를 거친다.
- 후속 조치: A1 `build_deps()`, A2 MCPPort 구현(Base `call_tool`의 dict 반환을 str로 조정), A1 CardStore 구현.
- 검증 방법: `tests/test_contracts.py::test_deps_assembles_with_fakes`, CP1 실제 MCP로 build_deps 조립.
