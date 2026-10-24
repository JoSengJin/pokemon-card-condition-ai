# 구역 결함 판정 기준 진단 — 2026-10-10

## 구현과 결과

같은 검증 자료에서 임계값만 바꾸어 오탐/손상 누락의 교환 관계를 진단한다. region-compare의 기존 사진 해시·좌표·정답·분할 검사 및 혼동행렬 검산을 통과한 예측만 사용한다. 0.1~0.9 고정9개 기준에서 구역 혼동행렬, 정밀도/재현율/오탐률/누락률, 앞뒷면 및 실물 동등 가중 오류율을 저장한다. null 정답 제외, 분모0은 null, 기준과 같은 확률은 결함이다. 자동 기준 선택은 없다.

실행:
```sh
.venv/bin/card-condition region-compare artifacts/regions-labeled-20261010-round5.jsonl artifacts/region-threshold-comparison-20261010.json artifacts/region-baseline-20261010-round4-epochs20/report.json artifacts/region-baseline-20261010-round5-epochs20/report.json --reference artifacts/regions-labeled-20261010-round4.jsonl
```

기존 val38구역/7실물. round5 모델 결과(오탐/누락):

| 기준 | 모서리 | 엣지 | 표면 |
|---|---:|---:|---:|
| 0.3 | 6/0 | 7/1 | 12/0 |
| 0.5 | 2/1 | 3/4 | 9/2 |
| 0.7 | 2/4 | 2/12 | 1/14 |
| 0.9 | 0/8 | 0/15 | 0/18 |

표면 기준0.7은 오탐을 줄이지만 누락을 크게 늘린다. 기준0.9의 오탐0은 모든 손상을 놓친 결과다. 신뢰도 보정값이나 Gemini 절감 근거로 해석하지 않는다. 모델 재학습/교체·운영 정책·사람 라벨 변경 없음. 실제 Gemini 절감0건.

다음 사람 자료는 train 정상 뒷면 모서리/엣지 및 새 개발용 검증 정상 앞면 표면/손상 뒷면 표면이다. 기존 b/c/p 완료 위치는 다시 요청하지 않는다. 기존 s/back은 면별 정상·관찰 제한 없음이나 구역 정답은 없어, 한 구역의 모서리/엣지만 확인할 후보로 사용할 수 있다. 면별 정상에서 구역 정상 정답을 자동 생성하지 않는다.

## 변경·검증·리스크·롤백

- 코드: card_condition/region_thresholds.py 신규, comparison.py 연결 및 기존 group_error_rates 함수 이동(기존 import 호환).
- 테스트: tests/test_region_thresholds.py 신규, test_region_experiment.py의 실제 비교 결과0.5 일치 검사 추가.
- 문서/배포: README.md, 이 기록, pyproject.toml0.4.9, 소비 프로젝트 CONDITION_ANALYSIS_TODO.md.
- Python 전체44개 통과. 경계값, 미확인 제외, 앞뒷면, 실물 동등 가중, 정답 없는 클래스 null 검사 포함. wheel0.4.9 로컬 빌드 성공. 신규 환경 설치와 독립 최종평가는 미실행.
- 리스크: 작은 재사용 val과 앞뒷면 클래스 편향이 남아 있다. 기준별 결과를 반복 보고 선택하면 검증셋에 과적합할 수 있다. 이 기능은 진단용이며 성능 향상을 보증하지 않는다.
- 롤백: comparison.py의 threshold_analysis 연결을 제거하고 group_error_rates 함수를 기존 위치에 복원, 신규 모듈/테스트와 문서/버전만 되돌린다. 기존 모델·라벨·분할·보고서는 보존한다.
