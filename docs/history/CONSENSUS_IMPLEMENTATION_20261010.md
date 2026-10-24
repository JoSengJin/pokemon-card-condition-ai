# 合의안 구현·해상도 비교 — 2026-10-10

## 완료 결과

0.4.26은 학습 입력 진단, 순위/보류 평가, point 실험의 224/448 공통 전처리를 구현한다. 운영 모델 교체나 Gemini 호출 생략은 하지 않았다. 실제 호출 절감은 0건이다. PokeCollector 운영 코드/DB와 사람 정답은 변경하지 않았다.

## 구현 파일과 핵심 diff

- `card_condition/side_experiment.py`: 실제 모델 전처리에서 PIL 이미지 반환을 분리. 원본 crop/224/448 PNG 진단과 학습 tensor가 같은 경로를 사용한다. 기본224 유지.
- `card_condition/edge_views.py`, `region_experiment.py`, `point_probe.py`, `point_benchmark.py`: point 학습부터 저장·별도 probe·속도측정까지 image_size 전달. 448은 point 실험만 허용. 구형 checkpoint의 누락값은224.
- `card_condition/point_dataset.py`: train-only 입력 진단용 split 선택. 기존 기본값 train/val 유지.
- `card_condition/input_review.py` 신규: 선택한 train 실물만 원본/모델입력 비교 HTML·PNG·JSON 생성. 기존 출력 덮어쓰기 거부. 검증/최종시험 사진을 진단에 읽지 않는다.
- `card_condition/score_diagnostics.py` 신규, `comparison.py`: 동일 정답·입력 및 혼동행렬 검산 후 ROC/PR 지점, AUROC/AP, 상수 기준선, 고정 보류 문턱값별 오류·coverage·실물 평균 오류율 기록. 둘 중 한 클래스가 없으면 순위 요약 null. 아무것도 판단하지 않은 경우 오류율 null. unknown 정답 제외.
- `card_condition/cli.py`: input-review 및 point-experiment --image-size 연결.
- `tests/test_input_review.py`, `test_score_diagnostics.py` 신규; `test_edge_views.py`, `test_point_comparison.py` 보강.
- `pyproject.toml`:0.4.26. README와 본 문서, 소비 프로젝트 CONDITION_ANALYSIS_TODO.md 갱신.

## 실제 실험

동결 round18 train127구역/25실물, val50구역/8실물을 그대로 사용했다. 엣지 정답이 있는 val는27구역/7실물이다. 같은 MobileNet 고정 backbone·balanced edge-context head·seed42·20epoch 예산·val loss 선택 규칙으로 입력 크기만 변경했다. 선택 epoch는224에서20,448에서9이므로 동일 epoch의 특징 분리 능력 비교로 해석하지 않는다.

| 설정 | 오탐 FP | 누락 FN | AUROC | AP | 구역 처리 중앙값 |
|---|---:|---:|---:|---:|---:|
|224|5|4|0.7056|0.7689|24.95ms|
|448|7|5|0.5167|0.6040|27.05ms|

처리 시간은 MPS, 모델 로딩 제외, 이미지 읽기·전처리·추론 포함, val50구역×3회다. 매물 전체 지연이 아니고 파일 캐시 영향을 포함한다. 속도 차이의 유의성은 검증하지 않았다.

반복 개발 진단 ㅅ의 정상 엣지 오탐은4/8→8/8. 448 채택 보류. 해상도를 높이면 모든 모델이 나빠진다는 결론은 아니다.

224의 정상<0.3/결함>=0.7 조건은 정답 있는27구역 중6구역만 판단했고 오류0건이나 모두 한 실물이다. coverage22.2%는 매물 완료율/호출 절감률이 아니다. 0.1/0.9 조건은 판단0건이므로 안전성이 입증되지 않는다. 문턱값을 운영에 채택하거나 확률 교정으로 해석하지 않는다.

기존 세 출력 모델의 표면 AUROC는 기본0.5042·클래스 보정0.4903이다. 문턱값 조정만으로 현재 특징의 구분 능력이 해결된다고 보기 어렵다.

## 산출물·재현

- `artifacts/input-review-consensus-20261010/index.html`: train s·ㄷ·ㅂ-new-back,16구역/41뷰. PNG를 클릭하면 실제 픽셀 크기. 원본 없는 세부를 확대가 복원하지 않는다.
- `artifacts/point-resolution-consensus-20261010.json`: 224/448 비교 및 모든 순위/보류 지표.
- `artifacts/point-consensus-three-targets-20261010.json`: 기존 세 출력 기본/보정 모델 진단.
- `artifacts/point-edge-context-448-20261010-round18-epochs20/`: 별도 신규 모델·입력·보고서. 기존 모델 보존.
- `artifacts/point-resolution-s-probe-20261010.json`: ㅅ을 학습/epoch 선택에 쓰지 않은 반복 진단.
- `artifacts/point-resolution-{224,448}-timing-20261010.json`: 실측 시간.

```sh
.venv/bin/card-condition input-review artifacts/point-evidence-20261010-round18.jsonl artifacts/new-input-review --card s --card ㄷ --card ㅂ-new-back
TORCH_HOME=artifacts/torch-cache .venv/bin/card-condition point-experiment --help
```

CLI의 실제 옵션은 --help를 따른다. 실험 때 사용한 Python 호출은 experiment(manifest, new_output, epochs=20, device='mps', point_grid=True, balance=True, edge_input='context', image_size=448)이다. 새 출력 경로를 사용한다.

## 다음 개발 경계와 매물 출력 계약

1. 고정 타일 실험은 기존 사람 좌표가 있는 train 사례의 입력 가시성 진단을 근거로 설계한다. 양성 구역의 모든 타일을 결함으로 복제하지 않는다. 위치가 알려진 학습 crop만 쓰고 추론 때 사람 좌표를 요구하는 방식도 피한다. 동일 데이터에 크기와 타일 변경을 동시에 적용하지 않는다.
2. 매물 관찰 상태와 결함 상태를 분리한다. 부분 반사/사진 누락은 정상·결함을 의미하지 않는다. 보이는 구역의 판단은 유지하고 가려진 범위만 unknown과 이유를 보존한다. 반사가 있으면 카드 전체가 불량이거나 구매 부적합하다고 출력하지 않는다.
3. 매물의 요구 범위(앞뒤·센터링·모서리·엣지·표면), 관찰 가능한 범위, 모델 지원 범위, 보류 범위를 비교한다. 사진 부족/관찰 불가는 `추가 사진 필요`, 보이지만 모델 판단 불확실은 `Gemini 검토`, 모두 충족하는 경우만 `로컬 완료 후보`로 정의한다. 두 문제가 함께 있으면 둘 다 기록한다. 이는 설계 계약이며 현재 자동 라우터가 완성됐다는 뜻이 아니다.
4. 엣지 전용 결과로 전체 상태 분석 완료를 선언하지 않는다. 구역 coverage를 매물 완료율로 바꾸지 않는다. 독립 최종시험과 채택 기준 전에는 모든 실험에 requires_gemini=True, production_ready=False를 유지한다.

## 검증과 리스크

- unittest discover 전체62개 통과(13.583초), `/private/tmp/condition-consensus-tests.log`.
- PNG→정규화 tensor가 실제 side_tensor와 정확히 같은지, train-only 진단이 val/test 파일을 열지 않는지 검증.
- 448 학습→checkpoint→probe·benchmark 크기 전달, 잘못된 checkpoint 크기 거부 및 구형224 기본값 검증.
- wheel0.4.26 빌드 성공 및 포함 소스 파일 byte 일치 검산.
- live labels SHA256 `d2d60c77ccb7dc4a626169a1df0edbe556f96e298e747a0e81ee7c5b394dd75c`, round18 `7b9129b09350357aa6d4aef8ad2cc63817a77bd799d05c3aa7bed15beddaf547` 불변.
- HTML의 브라우저 렌더링은 확인하지 못했다. 브라우저 도구가 file URL을 거부하여 우회하지 않았고, 생성 PNG의 로컬 확인과 tensor 일치 테스트만 완료했다.
- 기존 val와 ㅅ은 반복 개발 자료다. 통계적 우위·새 매물 일반화·운영 안전성을 입증하지 않는다. 진단 출력은 원본 사진을 포함하므로 로컬 보관한다. 진단 도중 오류가 나면 일부 생성된 새 출력 디렉터리가 남을 수 있으며 별도 새 경로로 재실행한다.

## 롤백

운영 모델·라벨은 바뀌지 않아 실험 폴더를 사용하지 않으면 운영 영향이 없다. 라이브 라벨 백업을 되돌릴 필요도 없다.
코드0.4.25 복구가 필요하면 `/private/tmp/condition-point-benchmark-wheel/pokemon_card_condition-0.4.25-py3-none-any.whl`의 card_condition 파일을 복구하고, 신규 input_review.py/score_diagnostics.py와 대응 신규 테스트를 제거한다. pyproject 버전을0.4.25로 돌린다. 소스 경로를 실행 중이면 wheel 재설치만으로 소스 복구가 되지 않는다. 변경된 기존 테스트는 이전 소스와 맞춰 복구해야 한다. 신규 실험 결과는 증거로 보관하거나 해당 신규 경로만 제거할 수 있다.
