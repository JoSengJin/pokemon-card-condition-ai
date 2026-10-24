# 관찰 제한 누락·오탐 동반 변화: 모의 컨설팅 합의와 검증

2026-10-11 / 0.4.38. 실제 Google·Claude 관계자나 외부 모델을 호출하지 않았다. 비전 학습 관점과 평가·수석 개발 관점의 독립 에이전트 검토를 대조하고 사용자에게 합의안을 먼저 보고한 뒤 구현했다. 사용자 사진은 외부로 보내지 않았다.

## 결론

사진 보강 이후 제한 누락이 줄었던 직접 원인은 검증 사진 전체의 점수 상승이다. 그 자체는 분리 능력 향상이 아니다. 대표 특징 거리 분류기를 추가 시험했지만 기준을 넘지 못했다. 모델을 운영 채택하지 않으며 실제 Gemini 절감은 0건이다.

이번 숫자는 **관찰 제한 분류**의 결과다. 카드 엣지·표면 손상 분류 결과와 섞지 않는다. 관찰 제한은 카드 불량이나 구매 제외를 뜻하지 않는다.

## 토론에서 확인된 사실

1. 기존 context → ㅈ 보강 context의 동일 검증 24면에서 모두 점수가 상승했다. 평균 +0.01442, AUROC는 0.36975로 동일하고 AP는 소폭 하락했다. AUROC가 같다고 개별 순위까지 동일한 것은 아니다.
2. 클래스별 학습 loss 총 가중치는 각각 1이다. 단순한 양성 사진 수 증가로 인한 클래스 불균형이라고 설명할 수 없다. 양성 실물 6→9로 신규 3실물이 양성 가중치의 1/3을 차지하며 **학습 내용의 구성**은 크게 변했다.
3. 선택 epoch은 context 2, tiles 1이다. 이후 학습 loss는 줄지만 검증 loss는 악화한다. 같은 학습 반복이나 epoch 증가를 먼저 처방할 근거가 없다.
4. 기존 세 후보의 검증 balanced BCE는 모두 항상 0.5를 출력하는 무정보 기준 ln(2)=0.693147보다 나쁘다.
5. checkpoint 선택은 클래스·실물 균등 BCE, FP/FN 표시는 비가중 0.5 판정이다. 서로 다른 기준이므로 loss 소폭 개선과 오탐 증가는 동시에 일어날 수 있다.
6. train/val 실물·픽셀 중복 검사가 있고 backbone은 고정 eval 모드다. val 특징을 미리 계산했다는 이유만으로 학습 누수라고 단정할 수 없다. 다만 같은 val을 반복 개발에 사용했으므로 독립 최종 성능은 아니다.

## 가설과 반론

- 신규 6면은 사진 전체 box이고 기존은 대체로 카드 crop이다. 배경·촬영 조건이 제한 여부 대신 학습됐을 가능성이 있지만 인과는 입증하지 않았다.
- ImageNet 고정 특징이 작은 기스 검출이나 반사·그늘에 의한 관찰 제한을 충분히 표현하는지 불명확하다. 이번은 관찰 제한 문제이며 작은 기스가 실제 손상인지의 정답을 바꾸지 않는다.
- shadow는 train에만, blur는 val 양성이 있으나 train 양성은 없다. 종합 제한 라벨 하나로 서로 다른 현상을 학습하는 데 자료 공백이 있다.
- 임계값 변경이나 점수 교정은 판정 수를 바꿀 수 있지만 잘못된 순위를 해결한다는 보장이 없다. 타일도 이미 악화했고 특징 수와 초기화까지 달라지므로 pooling 하나를 원인으로 확정하지 않는다.

## 개발 전에 합의한 범위

- 무정보 BCE, AUROC/AP, 클래스별 평균 점수, 동일 사진 점수 변화, 같은 FP 예산에서 최대 TP를 비교한다. 사후 FP 예산 진단값으로 운영 임계값을 선택하지 않는다.
- 같은 사진·box·고정 특징·가중치를 유지하고 분류 방식만 변경한다. train에서만 클래스별 실물 균등 대표 특징을 계산하는 nearest-centroid 후보를 한 번 시험한다.
- 대표 특징은 weighted mean이다. D차원 특징 x의 logit은 `(||x-mu0||²-||x-mu1||²)/D`이며 기존 Linear의 weight/bias로 정확히 표현된다. `/D`는 평균 제곱거리 단위이고 교정된 확률이 아니다. BCE 개선만으로 성공 판정하지 않는다.
- 정규화 추가, 임계값 탐색, 검증 라벨 변경, 최종 test 사용, 운영 fallback 변경은 이번 범위에서 제외한다.

## 실제 결과

train 46면/25실물, 동일 val 24면/14실물(제한 7, 비제한 17). centroid는 검증으로 epoch을 선택하지 않으며 `epochs=0`, `selected_epoch=null`; history의 한 행은 학습 반복이 아니라 적합 후 loss 측정이다.

| 후보 | FP / FN (0.5) | AUROC | AP | balanced BCE | FP≤3에서 최대 TP |
|---|---|---|---|---|---|
| 기존 context | 3 / 6 | .3697 | .2813 | .7267 | 2 |
| ㅈ 보강 context | 6 / 5 | .3697 | .2787 | .7221 | 1 |
| ㅈ 보강 tiles | 15 / 3 | .2857 | .2534 | .7523 | 1 |
| 동일 ㅈ 자료 centroid | 7 / 4 | .4874 | .4262 | .6984 | 2 |

FP 예산 3은 이번 실험 전에 기존 context의 0.5 결과로 고정했다. 같은 자료의 linear 대비 centroid는 순위 지표가 개선됐지만 무정보 기준 미달이고 실제 0.5 판정 오탐도 늘었다. FP≤6에서는 두 후보 모두 최대 TP 2다. 개선을 확정하거나 모델을 교체하지 않는다. 오류는 사용자 정답을 바꿀 이유가 아니다.

근거: `artifacts/observation-consensus-20261011.json`, `artifacts/observation-centroid-20261011/report.json`, 기존 세 report. centroid 24면 실제 checkpoint 재추론 차이 최대 0.0(MPS). live 라벨과 동결 snapshot SHA256 모두 `ae2514f040e152fb65b0e3f708a7ae5a7d8adab18469fac5951fb19327bc4598`; 원본 파일 해시도 학습 전후 동일.

## 코드와 실행

- `card_condition/visibility_model.py`: train-only centroid 옵션, 보고서 무정보 기준 검사. 기존 기본 AdamW 동작과 checkpoint 추론 구조 유지.
- `card_condition/visibility_compare.py`: 검증 사진·박스·그룹·정답·사유·해시 동일성 검사, 지표 재계산, 점수 이동·동일 FP 예산 진단. `research_candidate_only`는 연구 후보 표시일 뿐 운영 승인 아님.
- `card_condition/cli.py`: `--centroid`, `visibility-compare` 명령.
- `tests/test_visibility_model.py`, `tests/test_visibility_compare.py`: 거리식·저장/추론 일치·val 정답 교환 시 head 불변·일괄 점수 상승 오판 방지·동점 및 입력 변경 거부.
- `pyproject.toml`, `README.md`, 본 보고서, 실행 artifacts와 마스터 TODO.

```sh
TORCH_HOME=artifacts/torch-cache .venv/bin/card-condition visibility-experiment artifacts/observation-jieut-20261011-source.jsonl artifacts/NEW-DIRECTORY --centroid --device mps
.venv/bin/card-condition visibility-compare artifacts/observation-baseline-20261010/report.json artifacts/observation-centroid-20261011/report.json
```

새 실험 경로를 사용해야 하며 기존 결과를 덮어쓰지 않는다. 비교기는 저장된 report의 입력 해시를 대조하며 원본을 다시 읽어 검증하는 명령은 아니다. 이번 실행에서는 별도로 실제 파일 해시와 checkpoint 재추론도 확인했다.

## 최종 검증

전체 83테스트 통과(25.853초). 새 비교 CLI 실제 실행 성공. centroid 검증 24면 MPS 재추론 최대 차이 0.0. wheel 0.4.38 빌드 성공 및 패키지 Python/HTML 34파일 소스 byte 일치. 첫 검사에서 같은 임시 디렉토리에 있던 구형0.4.26 파일을 선택해 불일치가 났으며, 정확한0.4.38 파일명을 지정해 재확인했다. 운영 서버/UI는 수정하지 않았고 브라우저 저장 동작은 이번에 재검증하지 않았다.

## 다음 판단

지금 부족한 것은 학습 횟수보다 **촬영 제한과 카드 무늬·배경을 구별하는 입력 근거**다. 다음 별도 실험은 제한 종류별 오류를 보고 같은 이미지의 전처리만 바꾸는 등 독립된 입력 가설부터 정해야 한다. 이번 실패를 이유로 완료 라벨을 다시 요청하지 않는다. 같은 실물의 깨끗한 비교 사진과 고해상도 원본이 없다는 사용자 답변도 유지한다. 새로운 종류별 일반화 주장은 독립 자료 없이는 할 수 없다.

## 리스크·롤백

분류 품질은 여전히 부족하며 Gemini를 대체할 수 없다. 비교 검사 통과도 배포 승인이 아니다. 현재 데이터가 작고 반복 val이어서 수치 개선의 통계적 우위는 주장하지 않는다.

`.backups/observation-consensus-0438/`의 기존 5파일을 이후 변경 유무 확인 후 복원하고 신규 `visibility_compare.py`와 `test_visibility_compare.py`를 제거하면 코드 롤백된다. 새 artifacts는 기록으로 보존 가능하다. 사람 라벨·원본·운영 모델은 수정하지 않아 데이터 롤백이나 서비스 재시작은 필요 없다.

## 참고한 1차 자료

- scikit-learn [분류 임계값과 순위 평가](https://scikit-learn.org/stable/modules/classification_threshold.html): 점수 순위와 최종 판정 기준은 별개이며 같은 데이터에 맞춘 임계값 조정은 과적합 위험이 있다.
- scikit-learn [모델 평가와 단순 기준 모델](https://scikit-learn.org/stable/modules/model_evaluation.html): 학습 모델은 단순 기준과 비교해야 한다. 해당 자료는 일반 평가 원칙의 근거이며 이 프로젝트의 성능 증거는 로컬 실험 보고서다.
