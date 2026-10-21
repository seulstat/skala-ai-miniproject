# 발표 구성안 — Interview Coach Agent

> 평가: 기능 30 · Before/After 10(보너스) · 기술요소 30 · 한계·트레이드오프 20 · PPT 20. 순서는 design G5 "문제 → 개선 → Before/After → 한계".
> 슬라이드 14장(본편 13 + 부록). 각 장: **핵심 메시지 한 줄** / 내용 / 쓸 자료 / 발표 멘트. 숫자는 `eval/results/`·`eval/before_after.ipynb` 출처.

---

## 1. 표지
- 제목: **Interview Coach Agent** — 내 서류를 근거로, 승인한 것만 쌓는 영어 면접 코치
- 부제: 10/13 CLI 에이전트 → 멀티에이전트·MCP·HITL 웹 서비스
- 자료: 코치 탭 캡처 1장(`doc/images/e2e-1-express.png`)

## 2. 문제 — 10/13 버전의 한계
- 핵심: **"쓸 수는 있지만, 믿고 매일 쓰기는 어려웠다"**
- 내용
  - CLI라서 매번 터미널, 승인 대기는 프로세스가 꺼지면 사라짐(InMemorySaver)
  - 단일 Agent + Reviewer 노드 → 검수가 생성 맥락에 끌려감(GPT 검수 진동·의미 왜곡 관찰)
  - 동기 실행 → 요청이 겹치면 대기
  - 오류는 한 덩어리 — 무엇이 왜 실패했는지 사용자가 모름
- 멘트: 이번 과제의 목표는 기능 추가가 아니라 "서비스로 쓸 수 있게" 만드는 것.

## 3. 해결 개요 — 사용자 흐름
- 핵심: **준비 → 생성 → 검수 → (사람) 승인 → 저장 → 복습**
- 내용: 탭 3개(①준비 ②코치 ③카드), 카드 구성(Formal/Casual·핵심 표현·근거·답변 초안), 승인한 것만 저장
- 자료: 탭 ①②③ 캡처(`web/captures/01a`, `02`, `10`)

## 4. 아키텍처
- 핵심: **역할을 나누고, 경계마다 계약을 둔다**
- 내용: README "구조" 그림 — 브라우저 → 프록시(:8600) → FastAPI(:8100) → Supervisor 그래프 → MCP 서버 → SQLite 2개
- 자료: 구조도(README), 기술요소 ↔ 코드 위치 표(README)
- 멘트: 평가 기술 요소 7개 + HITL이 모두 코드 위치로 짚어진다.

## 5. Multi-Agent — Coach·Reviewer 분리
- 핵심: **만드는 쪽과 검사하는 쪽을 분리해, 검수가 생성 맥락에 끌려가지 않게**
- 내용
  - Supervisor: 라우팅·재작성 상한(2회)·승인 통제 / Coach: ReAct로 근거 Tool 선택 / Reviewer: LLM 판단 + 금지 표현 규칙
  - **권위 게이트**(강의 p.147): 규칙 위반은 LLM이 "통과"라 해도 위반, "복습" 문장은 코드가 분류 정정
  - **Loop Guard**(강의 p.169): 검색 4회에 닿으면 검색 Tool을 숨겨 카드만 낼 수 있게(ADR-0021)
- 자료: `eval/demo.ipynb` 출력 — "검수 1라운드 통과=False → 근거 재검색 → 초안 2회차 → 통과" (ADR-0004)

## 6. MCP + RAG
- 핵심: **데이터 접근은 MCP 경계 뒤로 — Tool·Resource·Prompt를 모두 쓴다**
- 내용
  - Tool: `search_my_experience`(RAG), `search_expression_bank` / Resource: `posting://{섹션}`(캐시 금지, 강의 p.47) / Prompt: `persona_review_prompt`(Reviewer가 검수 규칙을 받음)
  - Agent에는 래퍼 Tool 3개만 노출 → 호출마다 진행 이벤트·재시도·오류 변환(ADR-0002)
  - RAG는 MCP 서버 안: 제목 단위 분할 → 임베딩 → 코사인, 파일 수정 시각으로 재색인(ADR-0003)
- 숫자: MCP stdio 오버헤드 **호출당 약 1ms**

## 7. HITL + 영속화
- 핵심: **승인 전에는 저장하지 않고, 승인 대기는 서버가 꺼져도 남는다**
- 내용: `interrupt()`로 멈춤 → `checkpoints.db`에 상태 → 새로고침은 `GET /chat/pending`, 승인은 `POST /chat/resume`, 승인된 카드는 `coach.db`
- 숫자: 재시작 후 복원 **0/3 → 3/3**
- 자료: `web/captures/08-pending-restore.png`, flow-guide §4-B 그림

## 8. 오류 처리 4계층
- 핵심: **실패를 '전체 중단'이 아니라 '국소 사건'으로 — 오류마다 다른 안내**
- 내용
  - Tool(timeout만 0.5→1.5초 재시도) / Orchestration(검색 하나 실패는 격리, 검수 실패는 규칙만으로 강등) / Application(코드별 HTTP·SSE) / Presentation(재시도 가능하면 "다시 시도", 아니면 조치 안내)
  - 오류 코드 17개 표(`contracts/errors.py`)
- 자료: `web/captures/05-coach-degraded.png`, `06-error-recoverable.png`, `07-error-not-ready.png` (강의 p.18·p.174)

## 9. 개발 방식 — 계약 우선 + 병렬 에이전트
- 핵심: **역할 agent 4개를 병렬로 돌리고, 규칙은 스크립트가 판정**
- 내용
  - `contracts/`(State·Deps·스키마·SSE·API·MCP·오류·fixture)를 먼저 고정 → 프론트는 MOCK으로 백엔드 없이 개발
  - 역할별 git worktree, `check.sh`가 소유권·금지 패턴·커밋 규칙·ADR 형식 검사
  - ADR 22건(기각한 대안 포함), 단위테스트 179개(fake 모델·네트워크 없음)
- 멘트: 모듈화·단위테스트·DI 평가 항목의 근거.

## 10. Before / After
- 핵심: **품질은 유지, 실패는 제거, 영속·동시성은 새로 생김**
- 표(gpt-4o-mini, sample 10건 × 3회)

| 지표 | v1 | v2 |
|---|---|---|
| 카드 생성 성공 | 17/21 (81%) | **21/21** |
| 라우팅 | 26/30 | **30/30** |
| 개인 맥락(5점) | 4.93 | 4.86 |
| 성공 카드 지연 | 13.2초 | 15.3초 |
| 재시작 복원 | 0/3 | **3/3** |
| 동시 2요청 | 순차 | 28.4 → **14.5초** |

- 자료: `eval/before_after.ipynb` 막대그래프·케이스별 표
- 측정 조건 한 줄: 같은 모델·임베딩·심판, 예열 후 3회, 질문당 120초 제한 (ADR-0009)

## 11. 측정이 찾아낸 버그
- 핵심: **v1 실패의 정체는 'Tool 상한이 카드 출력까지 막는' 결함**
- 내용: 10/13 때는 Gemini라 드러나지 않음 → gpt-4o-mini에서 무한 반복(시간 초과)·OpenAI 400 → v2에서도 같은 결함 발견 → 1차 수정(Tool별 상한) 실패 → 검색 Tool 숨기기로 해결(S01 3/3, 7초)
- 멘트: Before/After가 숫자 비교를 넘어 "결함 발견 → 수정 → 재검증" 도구로 쓰였다.

## 12. 한계와 트레이드오프
- 핵심: **개선이 만든 새 약점을 숫자로**
| 한계 | 실측 | 대응 |
|---|---|---|
| 1건 지연 증가 | 13.2 → 15.3초, 검색 1.7 → 4.2회, 재작성 0.7 → 1.0 | 독립 검수의 대가. 검색 예산 조정 여지 |
| 체크포인트 DB 증가 | 대화당 약 121KB | 오래된 thread 정리 정책 필요 |
| 로컬 모델 품질 | gpt-4o-mini 7/7, qwen3.5:4b 5/7(1건 28분), qwen3:8b 0/7 | thinking 끄기(본문 비움·261초→10초), 규칙 기반 공고 정리 대안 |
| 단일 사용자·개인정보 | SQLite 다중 인스턴스 불가, 외부 LLM 전송 | ollama 선택지, 준비 점검 경고, 강의 p.21은 PostgreSQL |
| 콜드 스타트 | 첫 요청 약 70초(색인) | 예열·백그라운드 색인 여지 |

## 13. 결론과 다음 단계
- 결론: 근거 기반 생성 + 독립 검수 + 사람 승인 + 영속화 → "믿고 매일 쓰는" 코치로
- 다음(P1): 요청 내용과 관련된 카드 검색, 복습 퀴즈 간격 반복 고도화, PostgreSQL 전환, LangSmith Dataset 평가 자동화

## 부록 A. 질의응답 대비
| 예상 질문 | 답 근거 |
|---|---|
| 왜 Multi-Agent인가, 과하지 않나? | ADR-0004 대안 비교(3개 이상은 일정 초과) |
| MultiServerMCPClient를 왜 안 썼나? | ADR-0002 — `get_tools()`는 Tool만, Resource·Prompt 별도 |
| SQLite인 이유? | ADR-0006·0008 — 단일 사용자, PostgreSQL은 한계로 기록 |
| HITL이 실시간 UX를 해치지 않나? | 저장 직전에만 승인, 생성·검수는 스트리밍 (ADR-0006) |
| 오류가 나면 사용자는? | flow-guide §4-C, 오류 코드 표 |
| 테스트셋을 왜 바꿨나? | ADR-0009 — 개인정보 원칙, 구성 비율 유지 |
