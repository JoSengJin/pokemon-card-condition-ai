# 매물 범위 집계·공간 블록 실험 — 2026-10-10

## 결과

0.4.27은 기존 비교 보고서에 매물별 분석 범위 진단을 연결하고, MobileNet 마지막 공간 블록을 제한적으로 학습하는 실험을 추가했다. 기존 운영 모델·라벨·Gemini 경로는 유지했다. 실제 호출 절감0건.

## 매물별 집계

`point-compare`/`region-compare`가 기존 이미지·정답·기하·점수·혼동행렬 검산을 통과한 뒤 집계한다. 모든 비제외 val 매물을 분모로 사용하므로 구역 정답이 없는 매물도 빠지지 않는다. 이번 자료는 val14매물/14실물이며, 기존 정답 구역 검증은50구역/8실물이다.

앞뒤 각각 모서리4·엣지8·표면9, 총42개 필수 항목을 계산한다. 정상<0.3, 결함>=0.7의 고정 탐색 조건이며 중간 점수는 보류한다. 학습되지 않은 출력, 구역 예측 누락, 사진 누락, 카드 영역 미지정, 관찰 제한을 서로 다른 사유로 남긴다. 정답 null 자체로 모델 점수를 정상·결함으로 바꾸지 않는다. 제한된 구역의 score는 가리고 다른 구역 판단은 보존한다. 반사를 카드 불량이나 구매 거부로 연결하지 않는다.

- 추가 사진 필요: 누락된 앞뒤 사진 또는 기록된 관찰 제한이 있는 경우. 자동 반사 검출이 아니라 사람 기록 기반이다.
- Gemini 검토: 현재 모델에는 센터링·전체 관찰 가능성·동일 실물 확인이 없어 항상 유지한다. 구역 수준 미평가·미지원·점수 보류 사유도 별도로 기록한다.
- 로컬 완료 후보: 현재는 항상 false. 구역 범위 완료와 매물 전체 완료를 구분하는 차단 조건이다.

224/448 및 새 미세조정 모두 추가 사진 필요6매물, 구역 범위 완료0, 로컬 완료 후보0이었다. 완료율0은 현재 기능·범위 조건과 희소 예측에 대한 오프라인 진단이며, 새 매물 정확도 실측이나 Gemini의 대체 가능성 평가가 아니다. 전체 매물 후보0을 카드 상태 불량으로 해석하면 안 된다.

## 사람 확인과 부분 미세조정

사용자가 s 뒷면 좌측 상단의 표면 벗겨짐을 224px에서도 식별할 수 있다고 확인했다. `artifacts/input-visibility-human-s-20261010.json`에 학습 정답과 별도 저장했다. 한 train 사례에 대한 확인이며 모든 결함의 가시성이나 최소 해상도 기준을 확정하지 않는다.

가시 입력에서도 고정 특징이 부족할 가능성을 확인하려고 기존 round18/224/edge-context/균형 학습/seed42/20epoch 예산을 유지하고 마지막 inverted residual 블록만 학습했다. 이 블록에는 공간 convolution이 있어 과거 마지막1×1 convolution만 학습한 실험과 다르다. frozen prefix는 캐시하고 마지막1×1 블록과 BatchNorm 통계도 고정했다. head lr0.001, 공간 블록 lr0.0001. val loss로 선택한 공간 블록과 head를 함께 복원·저장한다. 검증 단계에는 gradient/optimizer update가 없다.

| 설정 | 선택 epoch | FP | FN | AUROC | AP | 별도ㅅ 오탐 |
|---|---:|---:|---:|---:|---:|---:|
|고정 특징|20|5|4|0.7056|0.7689|4/8|
|공간 블록 미세조정|5|4|7|0.6333|0.6944|8/8|

누락과 별도 진단 오탐이 악화돼 채택하지 않는다. 같은 epoch를 비교한 인과 실험은 아니고 선택 정책까지 포함한 두 학습 절차의 비교다. 한 설정 실패를 모든 fine-tuning 실패로 일반화하지 않는다.

## 변경 파일·핵심 diff

- `card_condition/listing_readiness.py` 신규: 검산된 구역 결과를42개 필수 항목과 매물별 사유로 집계. 학습 정답과 결과를 변경하지 않는다.
- `card_condition/comparison.py`: val 전체 매물을 집계에 제공, 각 모델의 listing_readiness·fine_tune_spatial 메타데이터 기록.
- `card_condition/region_experiment.py`: 기본 비활성 fine_tune_spatial 옵션, MobileNet point-grid/context만 허용. 마지막 공간 블록만 train gradient 허용·선택된 backbone/head 함께 복원. 기본 학습 경로 유지.
- `card_condition/cli.py`: point-experiment --fine-tune-spatial 연결.
- `tests/test_listing_readiness.py`, `tests/test_point_spatial.py` 신규; `tests/test_point_comparison.py` 연결 검증 추가.
- `pyproject.toml`0.4.27, README, 본 문서, 소비 프로젝트 CONDITION_ANALYSIS_TODO.md 갱신.

## 실행·산출물

```sh
.venv/bin/card-condition point-experiment artifacts/point-evidence-20261010-round18.jsonl artifacts/new-spatial --epochs 20 --device mps --balance --edge-input context --fine-tune-spatial
.venv/bin/card-condition point-compare artifacts/point-evidence-20261010-round18.jsonl artifacts/new-listing-comparison.json artifacts/point-edge-context-20261010-round18-epochs20/report.json artifacts/new-spatial/report.json
```

실제 결과: `artifacts/listing-spatial-consensus-20261010.json`, 새 모델 `artifacts/point-edge-spatial-20261010-round18-epochs20/`, 별도 반복 진단 `artifacts/point-spatial-s-probe-20261010.json`.

## 검증·리스크

- 전체66개 테스트 통과(14.373초). 반사 구역만 미확인, 보이는 결함/정상 보존, 사진 누락·미평가·미지원·점수 보류 분리, 구역 완료가 전체 완료로 승격되지 않음, 매물 수와 실물 수 구분을 검증했다.
- 공간 블록만 weight 변경, frozen prefix/최종1×1 및 BatchNorm running statistics 불변, 저장 모델의 직접 추론과 보고서 점수 일치, 미사용 test 이미지 미열기 검증.
- wheel0.4.27 빌드·포함31파일 소스 byte 일치 확인.
- live 라벨 SHA256 d2d60c77ccb7dc4a626169a1df0edbe556f96e298e747a0e81ee7c5b394dd75c 및 round18 SHA256 7b9129b09350357aa6d4aef8ad2cc63817a77bd799d05c3aa7bed15beddaf547 불변.
- 반복 val·ㅅ은 독립 최종시험이 아니다. 미세조정 메모리·매물 전체 지연·동시 처리량은 측정하지 않았다. 관찰 제한은 사람 입력이며 자동 감지 성능을 주장하지 않는다. 기존 sparse 보고서로 전체 구역을 새 추론한 것은 아니다.

## 다음 휴먼인루프

정상 뒷면 촬영 조건이 부족하고 미세조정만으로 해결되지 않았다. 서로 다른 PSA10 최대3장의 앞뒤 원본과 인증번호를 다음 보강 후보로 요청한다. 인증번호는 같은 실물을 묶는 데 쓰고 공개하지 않는다. PSA10을 모든 구역 정상 정답으로 자동 변환하지 않으며 케이스 반사·기스와 카드 결함을 구분한다. 기존 실매물과 함께 검증하고 동일 인증번호 사진은 같은 group으로 유지한다. 독립 최종시험용 사진은 학습/모델선택에 노출하지 않는다.

## 롤백

`/private/tmp/condition-listing-before/`의 comparison.py/region_experiment.py/cli.py/pyproject.toml/README.md를 원래 위치로 복구하면0.4.26 코드로 돌아간다. 신규 listing_readiness.py 및 두 신규 테스트를 제거하고 test_point_comparison.py의 listing 연결 assertion을 되돌린다. 새 모델/진단 결과는 해당 신규 artifacts 경로만 보관 또는 제거한다. 데이터 백업 복원이나 운영 DB 변경은 필요 없다. rollback 파일은 임시 경로이므로 장기 보관을 원하면 별도 보존해야 한다.
