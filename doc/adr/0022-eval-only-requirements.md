# ADR-0022: 노트북 도구는 평가 전용 requirements-eval.txt로 분리한다

- 상태: Accepted
- 날짜: 2026-10-21
- 작성: Lead
- 관련: design.md §1 G1·G3(출력 포함 노트북), ADR-0009, requirements.txt

## 배경
G1·G3은 실행 결과가 남은 노트북(`eval/demo.ipynb`, `eval/before_after.ipynb`)을 요구한다. 출력이 포함된 노트북을 재현 가능하게 만들려면 nbformat·nbclient·ipykernel과 그래프용 matplotlib가 필요하지만, 서비스 실행에는 필요 없다.

## 결정
평가 전용 `requirements-eval.txt`(`-r requirements.txt` + 4개, 버전 고정)를 두고, 노트북은 `eval/make_notebooks.py`가 nbclient로 실행해 출력까지 저장한다. `requirements.txt`는 바꾸지 않는다.

## 대안 비교
| 대안 | 장점 | 단점 | 기각 이유 |
|---|---|---|---|
| requirements.txt에 추가 | 설치 한 번 | 런타임 의존성이 커지고 서버 설치가 무거워짐 | 서비스에 불필요 |
| 결과를 손으로 노트북 출력 셀에 써 넣기 | 의존성 없음 | 실제 실행 결과라는 보장이 없음 | G1 "실행 결과 확인"의 신뢰성 |
| 10/13 venv(nbclient 있음)로 실행 | 설치 없음 | 이 프로젝트 코드·버전과 섞임 | 재현성 |

## 결과
- 긍정: 서비스 의존성은 그대로, 노트북은 실제 실행 출력이 남는다.
- 부정(트레이드오프): 설치 파일이 두 개가 된다.
- 후속 조치: README 실행법에 평가 환경 설치를 적는다.
- 검증 방법: `.venv/bin/python eval/make_notebooks.py`가 두 노트북을 오류 없이 실행·저장.
