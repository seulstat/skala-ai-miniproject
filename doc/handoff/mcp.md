# mcp 인수인계 — 2026-10-21 (CP1 대상)

## 한 일
MCP 서버 "coach"(fastmcp, stdio), RAG, 클라이언트(`MCPPort` 구현)를 fake 임베딩·네트워크 없이 완성했다.
`tests/test_mcp_*.py` 52개가 통과하고 `bash check.sh`는 FAIL 0이다.

- `mcp_server.py`: Tool `search_my_experience`·`search_expression_bank`, Resource `posting://{section}`, Prompt `persona_review_prompt`.
  이름·인자는 `contracts.mcp_spec` 상수만 쓴다. Prompt는 `DataPaths.persona_rules`를 읽어 `agent.prompts.reviewer_prompt(rules)`로 **완성된 system 프롬프트**를 돌려준다
  (A1 요청 (d) — Reviewer는 받은 문자열을 그대로 쓴다). 공고·규칙은 요청마다 읽고, 경험 문서·표현집은 `rag.Retriever`가 mtime을 보고 필요할 때만 다시 색인한다.
- `rag.py`: 10/13 `rag.py`의 `.config` 의존을 `DataPaths`·`EMBEDDING_MODEL`로 교체. 제목 단위 분할 → 임베딩 → 코사인 검색, 파일 (경로·mtime·크기) 지문이 바뀌면 다음 검색에서 재색인,
  결과는 `LABEL_EXPERIENCE`·`LABEL_BANK` 형식 출처 라벨로 시작한다. `EMBEDDING_MODEL=fake`는 글자 n-gram 해시 임베딩(네트워크 없음, 겹치는 글자가 많을수록 유사). 그 외는 `init_embeddings("provider:model")`.
  모듈 전역 `lru_cache` 싱글턴은 없애고 `Retriever` 인스턴스가 색인을 들고 있다 (DI).
- `agent/mcp_client.py`: coach 서버용으로 조정. `find_tool`(신규)·`find_resource_template`·`find_resource_server`(신규)·`find_prompt` 탐색 유지(찾은 서버 이름만 기억하고 Resource 내용은 캐시하지 않음).
  `call_tool(name, arguments) -> str`, `read_resource(uri)`, `get_prompt(name, arguments)`는 `server` 인자 없이 동작한다. 의도적 flaky 데모는 제거했고 `flaky_first_tool_call`은 받아서 무시한다
  (`agent/deps.py::_build_mcp`의 호출 형태 그대로). Base의 `asyncio.Lock`은 없애 동시 호출을 허용했다 (design §7 동시 2요청).
- 오류 계약(ADR-0012): 응답 지연 → `asyncio.TimeoutError` 그대로(호출당 `call_timeout`, 기본 30초) / 연결 불가·서버 종료 → `ToolError("MCP_UNAVAILABLE")` /
  서버 쪽 Tool·Resource 예외·입력 검증 실패·없는 이름 → `ToolError("TOOL_EXECUTION_ERROR")`.
- 표현집이 없으면 `DataPaths.expression_bank`가 `templates/expression_bank.template.json`으로 폴백한다 (`templates/`는 수정하지 않았다).

## 파일·함수 위치
| 파일 | 함수/클래스 | 역할 |
|---|---|---|
| `mcp_server.py` | `create_server(paths, retriever)`, `posting_section`, `main` | 서버 팩토리(테스트는 tmp 경로 주입), 공고 섹션 추출, stdio 실행 |
| `rag.py` | `Retriever.search_experience`·`search_bank` | 검색 + 출처 라벨 포맷. 색인은 `_index`(락, mtime 지문 비교) |
| | `split_by_heading`·`split_fixed`·`load_documents` | 제목 단위 분할(10/13 로직) |
| | `VectorIndex` | 임베딩 + 코사인, (모델, 텍스트) 단위 디스크 캐시(`paths.embed_cache`, fake는 캐시 안 함) |
| | `FakeEmbeddings`, `make_embeddings` | fake / `init_embeddings` 선택 |
| `agent/mcp_client.py` | `MCPClient` (`start`·`stop`·`async with`), `_run` | 연결·종료, 오류 계약 변환(타임아웃·MCPError) |
| | `call_tool`·`read_resource`·`get_prompt` | `MCPPort` |
| | `find_tool`·`find_resource_template`·`find_resource_server`·`find_prompt` | 서버 탐색 |
| `tests/test_mcp_rag.py` | | 분할·라벨·관련도 순위·k·표현집(verified 우선, 템플릿 폴백, 빈 표현집) |
| `tests/test_mcp_rag_index.py` | | mtime 재색인(추가·수정·삭제), 재사용, 임베딩 캐시, 깨진 캐시 |
| `tests/test_mcp_server.py` | | 이름·`SearchArgs` 스키마 일치, docstring, 출처 라벨, Resource 섹션 6종+전체+없는 섹션, 캐시 없음, Prompt 렌더링 |
| `tests/test_mcp_client.py` | | `MCPPort` 충족, A1 호출 형태(`_build_mcp`·`build_agent_tools`·`with_retry(get_prompt)`), find_*, 동시 호출, 프로세스 너머 재색인 |
| `tests/test_mcp_errors.py` | | `TOOL_EXECUTION_ERROR`·`MCP_UNAVAILABLE`(없는 서버·미시작·종료 후·도중 사망)·`TimeoutError` |

## 관련 ADR
[0002](../adr/0002-mcp-wrapper-tools.md)(래퍼 Tool) · [0003](../adr/0003-rag-inside-mcp-server.md)(RAG 위치) · [0004](../adr/0004-coach-reviewer-multi-agent.md)(Reviewer가 Prompt로 규칙 수신) ·
[0005](../adr/0005-async-nodes.md)(async, 블로킹은 `to_thread`) · [0011](../adr/0011-deps-in-contracts.md)(`DataPaths`, `call_tool` str 반환) · [0012](../adr/0012-error-handling-4layer.md)(오류 계약).
Proposed ADR은 쓰지 않았다 — 계약 변경·라이브러리 추가·design과 다른 구현이 없었다. 아래 "한계" 2·3·4는 Lead 판단이 필요하면 ADR로 올릴 수 있다.

## 사용한 계약 (contracts/)
`mcp_spec.py`(`SERVER_NAME`, `TOOL_ARGS`·`SearchArgs`, `RESOURCE_POSTING`·`posting_uri`, `PROMPT_*`, `LABEL_*`), `deps.py`(`DataPaths`, `MCPPort`), `errors.py`(`ToolError`·`RETRY_*`),
`schemas.py`(`POSTING_SECTIONS` — 테스트). 계약은 고치지 않았다.

## 테스트 결과 (check.sh, 자기 테스트)
```
bash check.sh
① ruff                PASS
② pytest(계약 제외)    72 passed (core 20 + mcp 52)
③ 계약 테스트          43 passed
④ 금지 파일·패턴       PASS
⑤ 소유권              PASS (변경 9개 모두 허용 경로)
⑥ 파일 길이            PASS
⑦ 커밋 메시지          PASS
⑧ ADR                 PASS
결과: FAIL 0 · WARN 0
```
`.venv/bin/python -m pytest tests/test_mcp_*.py`: 52 passed (약 10초, 서버 subprocess 13회 기동). 핵심 동작 7곳(mtime 지문, 출처 라벨, Resource 캐시, Prompt 렌더링, verified 우선, 타임아웃 분기, 연결 종료 분류)을 일부러 망가뜨려 테스트가 실패하는 것을 확인했다.
테스트가 잡은 실제 버그: Python 3.11에서 `asyncio.TimeoutError`는 `OSError`의 하위 클래스라, `except OSError`가 타임아웃을 `MCP_UNAVAILABLE`로 바꿔 버렸다 → `_run`에서 타임아웃을 먼저 다시 던진다.

## 알려진 한계·미완료
1. **실제 임베딩 미검증.** 이 환경에서 ollama가 실행 중이 아니어서 `ollama:nomic-embed-text`·`openai:*` 경로는 `init_embeddings` 생성까지만 확인했다(호출 안 함). fake 임베딩은 한↔영 의미 검색이 안 되므로 검색 품질은 CP2에서 실제 모델로 확인해야 한다.
2. **자동 재연결 없음.** 서버 프로세스가 죽으면 이후 호출은 계속 `MCP_UNAVAILABLE`이다. 복구하려면 새 `MCPClient`를 만들어야 한다 (`start()`가 실패해도 같은 오류를 던진다).
3. **`k` 범위.** 서버는 계약(`SearchArgs`: 1~5)대로 범위 밖 `k`를 입력 검증으로 거부한다 → `TOOL_EXECUTION_ERROR`로 그 검색만 "근거 없음" 처리된다. 10/13은 `k`를 1~5로 조용히 보정했다. A1 래퍼(`agent/tools.py`)는 보정하지 않는다.
4. **출처 라벨의 제목.** `#` 제목(없으면 `##`)만 쓴다 (예: `[experience.md > 물류 스타트업 데이터 분석 인턴 (2개월)]`). 10/13은 `# > ##`로 이어 붙여 `... > 활동내용`까지 붙었으나, 계약 예시와 모든 fixture가 `#` 제목만 쓰므로 맞췄다.
   분할은 여전히 `#`·`##` 단위이고, `split_by_heading`의 한 줄(`(h1 or h2)[:40]`)로 되돌릴 수 있다. 제목 문구는 임베딩 대상이 아니다(10/13과 동일).
5. 첫 검색은 색인(임베딩) 때문에 느리다. 클라이언트 `call_timeout` 기본 30초(생성자 인자)가 이를 흡수하지만, ollama 모델 로딩이 더 길면 `TimeoutError` → A1 재시도 → 같은 색인을 서버 락이 이어받는다(중복 임베딩은 없음).
6. `fastmcp.Client.read_resource`는 한글 URI(`posting://주요 업무`)를 거부한다(`AnyUrl` 검증). 우리 `MCPClient`는 저수준 `ClientSession`을 쓰므로 문제없지만, 다른 코드가 `fastmcp.Client`로 공고를 읽으면 실패한다.
7. stdio 왕복 지연(design §7 한계 1)은 측정하지 않았다. 참고로 fake 임베딩 기준 서버 기동 약 0.5초, 첫 검색 약 0.15초(1회 측정).
8. 서버 subprocess는 `COACH_DATA_DIR`·`EMBEDDING_MODEL`을 **부모 환경변수에서 상속**한다. 상대 경로(`./data`)는 부모와 같은 cwd에서 풀리므로 부모가 cwd를 바꾸지 않는다고 가정한다. `.env` 로드는 부모(서버) 몫이고, `python mcp_server.py`로 직접 실행할 때만 `main()`이 `.env`를 읽는다(기존 환경변수는 덮어쓰지 않음).

## Lead·다른 역할에 대한 요청
1. **Lead**: `pyproject.toml`의 `"rag.py" = ["E702"]` per-file-ignore는 이제 필요 없다(한 줄 다중 문장을 풀었다). 제거해도 된다.
2. **Lead / A1**: 한계 3 — `k` 범위 밖일 때 (a) A1 래퍼가 `min(max(k, 1), 5)`로 보정하거나 (b) 계약을 완화할지 정해 주세요. 지금은 LLM이 `k=10`을 주면 그 검색이 격리된다.
3. **A3**: `MCPClient.start()`는 서버를 못 띄우면 `ToolError("MCP_UNAVAILABLE")`를 던진다(`build_deps()`가 그대로 전파). lifespan에서 `start`와 `stop`은 **같은 task**에서 불러야 한다(anyio cancel scope) — FastAPI lifespan 한 함수 안이면 충족된다.
4. **Lead**: CP2 전에 `ollama pull nomic-embed-text` 후 `EMBEDDING_MODEL=ollama:nomic-embed-text`로 실제 검색 스모크(관련 문단 순위, 첫 검색 시간)를 한 번 확인해 주세요. 이 세션에서는 못 했다.
5. **A1 확인 사항(core.md 요청 1·2)**: (a)~(d) 모두 반영했다. `get_prompt`는 `reviewer_prompt(rules)`로 완성된 평문 system 프롬프트(첫 줄 "당신은 영어 면접 코치이자…")를 돌려주며,
   `tests/test_mcp_client.py::test_reviewer_style_get_prompt_with_retry_returns_ready_system_prompt`가 Reviewer와 같은 호출(`with_retry(get_prompt, 이름, {})`)로 지시문이 이중으로 들어가지 않음을 확인한다.

## 발표 때 설명할 포인트 (3줄)
- MCP: Tool 2·Resource 1·Prompt 1을 fastmcp 서버 하나로 노출하고, 이름·인자는 `contracts.mcp_spec` 한 곳에서만 가져와 서버 시그니처가 계약과 어긋나면 테스트가 깨진다. Agent는 래퍼 Tool만 보고, Resource는 매번 읽는다.
- RAG: 서버 프로세스 안에서 제목 단위 분할 → 임베딩 → 코사인, 파일 mtime 지문이 바뀌면 재색인하고 (모델, 텍스트) 캐시로 바뀐 문단만 다시 임베딩한다. 결과는 `[파일 > 제목]` 라벨로 시작해 카드의 evidence가 된다.
- 오류 계약: 지연은 `TimeoutError`(재시도), 연결 불가는 `MCP_UNAVAILABLE`(치명), 서버 예외는 `TOOL_EXECUTION_ERROR`(그 검색만 격리). 3.11에서 `TimeoutError`가 `OSError`라 분기 순서가 틀리면 타임아웃이 연결 오류로 둔갑하는 버그를 테스트가 잡았다.
