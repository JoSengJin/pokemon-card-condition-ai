# 클릭 라벨·타일 모델 최종평가 연결 — 0.4.67

## 문제와 수정

기존 region-evaluate는 region_rows만 읽어 사람이 클릭한 defect_points를 최종평가에서 놓쳤다. 최신 타일 모델의 학습 입력과 최종시험 입력이 달라질 수 있었다. point 모델은 학습과 동일한 point_rows(grid=True, splits={test})를 사용하도록 연결했다. 구형 region 모델 입력 경로는 유지한다.

같은 구역의 여러 점은 하나로 합치고, 명시적 정상 구역만 음성으로 사용한다. 전체 카드 gradable이 미확인이어도 사람이 확인한 국소 결함은 평가 가능하다. 지원되는 알려진 정답이0개면 성공 보고서를 저장하지 않는다. 최종시험에서 학습·모델선택·임계값 조정은 실행하지 않는다.

## 변경 파일

card_condition/region_evaluation.py, tests/test_point_final_evaluation.py, pyproject.toml, README.md, 본 문서, 마스터 CONDITION_ANALYSIS_TODO.md, artifacts/point-final-20261011/checks.json 및 기존 분할을 보존한 development-only.jsonl 진단 스냅샷.

## 검증

전체138테스트 통과(41.943초). 저장소 밖 wheel 설치본 관련6테스트 통과(3.247초). 패키지52개 Python/HTML파일 byte 일치. 새 테스트는 임시 실물6개를 원래 train/val/test 분할대로 유지하고 실제 tiles head를1epoch 학습한다. test2실물의 앞뒤4구역을 점/정상 라벨로 평가하고 동일 RegionAnalyzer 점수와 소수7자리까지 대조한다. 같은 구역의 두 클릭은 한 표본, 미확인 표면은 null, 지원되지 않는 종류만 있는 평가 입력은 거부한다. 기존 면/구역 누수·변경 보호도 전체 테스트에 포함된다.

실제 선택한 타일 체크포인트로 기존 train/val을 그대로 보존한 스냅샷을 최종시험에 제출해 exit1·성공 보고서 미생성을 확인한다. 원본 source/live/모델 SHA는 checks.json에 보존한다. 현재 미사용 test0장이므로 실제 독립 정확도는 미측정이다. fixture 정확도를 서비스 정확도로 보고하지 않는다. 선택 모델 변경 없음·이번 실제 정확도 개선 미확인·운영 절감0건·개발 기반4/6(67%, 정확도 아님).

## 사용

기존 region-evaluate 명령과 --history를 그대로 사용한다. point checkpoint이면 evaluation_kind=point_final, 구형 region checkpoint이면 region_final이다. history에는 모든 이전 개발 manifest를 전달한다. test 결과를 다음 모델선택에 재사용하지 않는다.

## 리스크·롤백

점 라벨이 있는 모델은 이전에 누락되던 알려진 구역도 집계하므로 이전의 region_rows 보고서와 분모가 달라질 수 있다. 서로 다른 분모의 정확도 차이를 성능 개선으로 해석하지 않는다. 다른 사진의 동일 실물 group 확인은 여전히 사람 책임이다.

후속 변경 유무를 확인한 뒤 .backups/point-final-0467/의 region_evaluation.py·pyproject.toml을 복원하고 test_point_final_evaluation.py를 제거한다. README의 해당 절은 되돌린다.0.4.66 보호 로직은 유지 가능하며 사람 라벨·모델·운영 서버 롤백은 필요 없다.

에튜: 학습과 추론/평가의 전처리가 같아야 비교가 성립한다. 학습이 ‘클릭이 속한 고정 구역’을 보는데 시험이 클릭을 무시하면 다른 문제를 채점하게 된다. 이번에는 학습의 구역 생성 함수를 평가에도 재사용해 그 차이를 없앴다.
