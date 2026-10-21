# ADR-0016: 프론트 구현 중 발견한 계약 빈틈 4건의 확정 요청

- 상태: Accepted (Lead, 2026-10-21 — 4건 모두 계약 반영, 프록시는 BACKEND_UNAVAILABLE로 전환)
- 날짜: 2026-10-21
- 작성: web
- 관련: design.md §5, contracts/api.py·errors.py·fixtures, ADR-0006·0012. 번호는 CP 병합 때 Lead가 다시 매긴다

## 배경
A4(web)가 MOCK 서버와 화면을 만들면서 `contracts/`만으로는 정할 수 없는 부분 4곳을 만났다. 계약은 고치지 않았고, 화면은 아래 "현재 구현"대로 방어적으로 동작한다. A3(api) 구현과 어긋나지 않도록 Lead가 확정해 주기를 요청한다.

| # | 빈틈 | 현재 구현 (web) |
|---|---|---|
| 1 | `PUT /api/profile`, `POST /api/docs`, `DELETE /api/docs/{name}`, `PUT /api/posting`의 **성공 응답 본문**이 계약에 없다 (`OkResponse`·`DocInfo` 모델은 있으나 어느 경로에 쓰는지 불명) | 본문을 읽지 않고 HTTP 상태만 본다. MOCK은 `OkResponse`/`DocInfo`로 답한다 |
| 2 | 프로필이 아직 없을 때 `GET /api/profile`이 무엇을 돌려주는지 없다 (`UserProfile`은 `goal`·`target_role`이 필수라 빈 객체를 돌려줄 수 없다) | `404 NOT_FOUND`(`ErrorResponse`)이면 빈 폼, 그 밖의 오류는 오류 상자로 표시한다 |
| 3 | `web_server.py`가 백엔드(:8100)에 연결하지 못할 때 쓸 **오류 코드**가 없다 | `STREAM_DISCONNECTED`(presentation, recoverable)를 재사용해 `502 + ErrorResponse`로 응답하고 `user_message`만 상황에 맞게 바꾼다 |
| 4 | `sse_review.json`·`sse_out_of_scope.json`의 `FinalAnswer`에 `"error": false`가 있다. ADR-0012로 `FinalAnswer.error`는 사라졌다 | 계약 모델은 추가 필드를 무시하므로 통과하지만, 화면은 이 필드를 쓰지 않는다 |

## 결정
Lead가 아래 안으로 확정해 주기를 제안한다.
1. 위 4개 경로의 성공 응답은 `PUT /api/profile`·`DELETE /api/docs/{name}`·`PUT /api/posting` → `OkResponse`, `POST /api/docs` → `DocInfo`로 `api.py` 주석에 명시한다. 화면은 본문에 의존하지 않으므로 다른 선택도 무방하다.
2. 프로필이 없으면 `GET /api/profile`은 `404 NOT_FOUND`로 답한다. 화면은 이미 이 계약으로 구현되어 있다.
3. `ErrorCode`에 `BACKEND_UNAVAILABLE`(layer=presentation, recoverable=True, fatal=True, HTTP 502, 메시지 "서버에 연결할 수 없어요. 서버가 실행 중인지 확인한 뒤 다시 시도해 주세요.")을 추가한다. 추가하면 프록시·화면이 이 코드로 옮겨 간다. 추가하지 않기로 하면 현재의 `STREAM_DISCONNECTED` 재사용을 확정한다.
4. fixture에서 `FinalAnswer`의 `"error": false`를 지운다.

## 대안 비교
| 대안 | 장점 | 단점 | 기각 이유 |
|---|---|---|---|
| 프론트가 응답 본문을 가정해 사용 (예: 저장 후 반환된 프로필로 폼 갱신) | 서버 왕복 1회 절약 | 계약에 없는 필드에 의존, A3 구현과 어긋나면 깨짐 | agent.md §3 "계약에 없는 필드 사용 금지" |
| 프로필 없음 → 빈 `UserProfile` 반환 | 프론트 분기 없음 | 필수 필드가 빈 값이라 모델 검증(`min_length` 등)과 충돌하고, "아직 없음"과 "빈 값"을 구분하지 못함 | 의미가 모호함 |
| 연결 불가를 `UNEXPECTED_ERROR`로 응답 | 코드 추가 없음 | `recoverable=False`라 다시 시도 버튼이 안 나옴. 서버를 켠 뒤 재시도하는 흐름과 맞지 않음 | 사용성 |
| 연결 불가를 `MCP_UNAVAILABLE`로 응답 | recoverable=True | "근거 서버(MCP)" 문구가 틀려 사용자를 오도함 | 사실과 다름 |
| 연결 불가용 코드를 계약에 두지 않고 화면 문구만 쓴다 | 계약 변경 없음 | 프록시가 만드는 `ErrorResponse`가 `ErrorCode` 밖의 값을 갖게 됨 | 계약 위반 |

## 결과
- 긍정: A3·A4가 같은 응답 모양을 쓴다. 백엔드가 꺼져 있을 때 문구가 정확해진다. fixture가 현행 모델과 일치한다.
- 부정(트레이드오프): 3번을 채택하면 `ErrorCode`가 17개로 늘고 `ERROR_CATALOG`·계약 테스트·PPT 오류 표를 같이 고쳐야 한다.
- 후속 조치: Lead가 확정한 뒤 A3에 1·2번을, A4에 3번 코드 이름을 알린다. 3번이 채택되면 `web_server.py`의 한 줄(`error_info(...)` 호출)과 화면의 `STREAM_LOST` 문구만 바뀐다.
- 검증 방법: `tests/test_contracts.py`(fixture 검증), CP2 `sh/smoke_chat.sh`, CP3 브라우저에서 백엔드를 끈 채 오류 화면 확인 (`web/captures/14-error-backend-down.png`).
