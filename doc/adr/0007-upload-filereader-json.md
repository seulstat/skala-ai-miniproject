# ADR-0007: 문서 업로드는 FileReader → JSON

- 상태: Accepted
- 날짜: 2026-10-20
- 작성: Lead
- 관련: design.md §2 "업로드", contracts/api.py `DocUpload`

## 배경
경험 문서(.md)와 공고를 웹에서 올려야 한다. 요청은 `web_server.py` 프록시를 거쳐 FastAPI로 간다.

## 결정
브라우저 `FileReader`로 텍스트를 읽어 `{name, content}` JSON으로 보낸다. multipart는 쓰지 않는다. 파일 이름은 경로 구분자를 막고 `.md`만 허용한다.

## 대안 비교
| 대안 | 장점 | 단점 | 기각 이유 |
|---|---|---|---|
| multipart/form-data | 표준 업로드, 바이너리 가능 | `python-multipart` 의존성, 프록시가 multipart 본문을 그대로 넘겨야 함 | 텍스트만 다루는데 복잡도만 늘어남 |
| 서버 로컬 경로 입력 | 구현 최소 | 웹 서비스답지 않음, 경로 노출·보안 문제 | 사용성·보안 |

## 결과
- 긍정: 프록시가 JSON만 다룬다. 테스트가 단순하다.
- 부정(트레이드오프): 큰 파일·PDF는 다룰 수 없다(design §8 제외 목록과 일치).
- 후속 조치: A4 FileReader UI, A3 `/api/docs` 저장 시 `DataPaths.docs_dir` 사용.
- 검증 방법: A3 API 테스트, CP3 브라우저 업로드.
