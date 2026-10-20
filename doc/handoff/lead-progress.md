# Lead 진행 기록 — Phase 0

## 사용률 기록 (사용자가 알려 준 값만 기록)

| 시각 | 시점 | 5시간 창 사용률 | 비고 |
|---|---|---|---|
| 16:37 | Phase 0 시작 (기준선) | 16% | 현재 창 재설정 19:50 (사용자 확인) |
| 17:0x | M1 완료 | 19% | M1 구간 +3%p → Phase 0 전체 예상 3 ÷ 0.20 = 15%p (종료 예상 약 31%, 예산 40%p 이내) |

## 마일스톤 상태

| M | 내용 | 상태 | 커밋 |
|---|---|---|---|
| M1 | 환경·복사·design 수정 | 완료 | `[lead] Phase 0 M1 ...` |
| M2 | contracts/ | 대기 | |
| M3 | agent.md | 대기 | |
| M4 | check.sh | 대기 | |
| M5 | ADR 0001~0011 | 대기 | |
| M6 | worktree·검증·인수인계 | 대기 | |

## 사용자 지시 (상시)
- 커밋 메시지에 Claude·AI 이름을 넣지 않는다 (`Co-Authored-By` trailer 금지). M1 커밋에서 제거함(amend). work-plan §3·§4에 반영, agent.md·check.sh에도 반영 예정

## 한도 판단 기준
- 소프트 한도: 사용률 70% 또는 경과 3시간(16:37 시작 → 19:37)
- 19:50에 창이 재설정되므로, 19:37 이후 작업은 새 창 기준으로 다시 사용률을 받아 판단

## M1 완료 항목
- `git init`(main), `.gitignore`, `requirements.txt`(버전 고정, 10/13·Base venv에서 검증된 버전 + `aiosqlite` 명시), `.env.example`, `pyproject.toml`(ruff·pytest 설정)
- `sh/setup_venv.sh`(uv 우선, 없으면 venv+pip), `sh/seed_sample.sh`(examples → COACH_DATA_DIR, 덮어쓰기 안 함)
- 재사용 코드 `cp` 복사 + 출처 주석: `contracts/schemas.py`, `agent/prompts.py`, `agent/retry.py`, `agent/mcp_client.py`, `rag.py`, `templates/`, `examples/sample_user/`, `eval/v1/`
- 참고용 원본은 `ref/v1/`, `ref/base/`에 원본 그대로 (ruff 제외, 읽기 전용, `ref/README.md`)
- import 경로 조정: `agent/prompts.py`의 schemas → `contracts.schemas`. `.config` 의존은 TODO(A1)/TODO(A2) 주석만 달고 그대로 둠 (config는 각 역할이 대체)
- 역할 담당 파일은 docstring만 있는 skeleton
- design.md 수정 2건: Deps 정의 위치(§2 구조도·핵심 결정 표·§3 DI 행), 테스트 7을 CP1(Day2 오전)로(§9). 상단에 변경 이력
- work-plan.md 동기화: ADR 0011 추가, Lead 소유 경로에 `pyproject.toml`·`ref/`·`examples/` 명시, `sh/smoke_*.sh`는 A3

## 남은 항목
- M2~M6 (위 표)

## 다음 시작점
- M2: `contracts/schemas.py`(복사본)에 Card 저장형·SSE/API 모델 추가, state/deps/events/api/mcp 작성, fixtures, `tests/test_contracts.py`
