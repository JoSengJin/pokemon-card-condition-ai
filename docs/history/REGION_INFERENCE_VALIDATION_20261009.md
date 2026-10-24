# 구역 추론 계약·추가 라벨 재실험 — 2026-10-09

## 구현
RegionAnalyzer 및 region-predict CLI를 추가했다. 사람이 지정한 카드 영역을 공유 region_box 함수로3×3 변환해 학습·추론 좌표 계산을 일치시켰다. area와 unknown_labels를 입력하고 구역 점수·null 사유·모델/학습 snapshot 해시·장치/시간을 반환한다.

- 관찰 제한: observation_limited로 null. 반사로 가린 항목을 정상이나 결함으로 바꾸지 않는다.
- 적용 불가 구역: not_applicable로 null. 미학습 출력: unsupported로 null.
- 모델 스키마/라벨/좌표/중복 관찰 제한/비유한 출력은 거부한다. weights_only=True로 로딩한다.
- requires_gemini=true, production_ready=false, actual_calls_saved=0. 반사 자동검출, 전체 등급·점수, PokeCollector 연결은 없다.

## 새 라벨 기준 실험
artifacts/regions-labeled-20261009-next.jsonl snapshot, train59/val37구역. MobileNet 고정 특징+head, crop224, seed42, epochs5, MPS로 동일 조건 실행. 원본/기존 실험은 보존했다. test는 읽지 않고 split 미지정 t도 제외했다.

| 항목 | train 정상/결함/미확인 | val TP/TN/FP/FN |
|---|---|---|
| 모서리 | 2/12/45 | 7/2/4/0 |
| 엣지 | 2/17/40 | 11/4/8/3 |
| 표면 | 2/43/14 | 16/2/10/2 |

선택 회차2, 최저 val BCE0.6705182791. val 구역/정답이 달라졌으므로 이전 TP8→11 등을 개선이라고 해석하지 않는다. 정상 표본 부족·오탐·누락 때문에 운영 채택 보류. 남은 위치6항목과 정상 사례 보강은 REGION_HUMAN_REVIEW_20261009.md에 갱신했다. 휴먼인루프 유지, 라벨 자동 수정 없음.

## 검증·산출물
전체35개 unittest 및 구역 관련6개 테스트 통과. 체크포인트 복원 예측 일치, 관찰 제한/적용 불가/미학습 null 사유, 잘못된 좌표/모델 메타데이터 거부 확인. 실제 새 모델과 사진에서 surface_defect=null, observation_limited, requires_gemini=true 확인. 모델 CLI와 패키지 검증은 아래 추가 기록을 참조한다.

산출물: artifacts/region-baseline-20261009-next/model.pt, report.json, artifacts/region-readiness-20261009-next.json, artifacts/region-inference-20261009-next.json. 독립 최종평가·운영 fallback 연동은 미실시.

추가 검증: 실제 region-predict CLI에서 관찰 제한 null과 fallback=true 확인. JS 검증·자동 이동 회귀 통과. 0.4.1 wheel 로컬 no-index/no-deps/no-build-isolation 빌드 및 소스 밖 임시 설치·모델 로딩 통과. 첫 실행은 venv symlink를 해제해 base Python으로 실행한 검증 스크립트 오류(torch 없음)였으며, 가상환경 경로를 유지해 통과했다. 새 머신에 의존성까지 설치하는 검증은 하지 않았다.

## 변경 파일·리스크·롤백
card_condition/region_model.py(신규), regions.py(region_box), region_dataset.py(공유 좌표 계산), cli.py(region-predict), tests/test_region_experiment.py, README.md, pyproject.toml(0.4.1), 사람 확인 문서, 이 문서, CONDITION_ANALYSIS_TODO.md.

호출자가 관찰 제한을 지정하지 않으면 반사 영역에도 모델 점수가 나올 수 있다. 보정되지 않은 점수이며 항상 fallback 대상이다. 사람 지정 경계·원근 오차가 남는다. 롤백은 region-predict 등록·region_model.py를 제거하고 버전을0.4.0으로 복원한다. 공유 region_box는 데이터셋이 사용하므로 유지하거나 기존 좌표식으로 함께 복원한다. 새 산출물은 보관하고 원본 라벨·기존 모델은 유지한다.
