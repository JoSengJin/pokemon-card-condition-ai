# DINOv2 백본 교체 비교와 기존 합의안 복귀

2026-10-11 / 0.4.42

## 결론

DINOv2 ViT-S/14 고정 특징 교체 경로를 구현하고 실제 학습·검증했다. 순위 지표는 소폭 개선됐지만 오탐·누락이 그대로이고 균등 BCE가 악화해 사전 채택 기준 미달이다. 운영 교체는 하지 않는다. 현재 개발 기준은 다시 OBSERVATION_CONSENSUS_20261011.md의 종류별 입력 근거 진단이며 마스터 CONDITION_ANALYSIS_TODO.md 상단 실행 순서로 관리한다. 완료 라벨을 재요청하지 않는다.

이 결과는 특정 백본·CLS·224px·가중 centroid 조합의 결과다. Gemini 조언 전체가 틀렸다거나 DINOv2의 모든 방식이 부적합하다는 결론은 아니다.

## 사전 통제와 실제 결과

DINOV2_EXPERIMENT_PLAN_20261011.md에 백본 교체만 시험하는 범위와 채택 기준을 먼저 기록했다. 관찰 제한 종합 타깃, 사람 확인 box 동결 source, train46면/25실물·val24면/14실물, 원본 해시·그룹·정답·이미지 전처리, 기존 클래스/실물 균등 centroid와 /D 거리식이 동일하다. 추가 정규화·온도·SPP·멀티태스크·임계값 선택·test 사용은 하지 않았다.

| 지표 | 기존 MobileNet | DINOv2 ViT-S/14 |
|---|---:|---:|
| FP / FN (0.5) |7 / 4|7 / 4|
| AUROC |0.487395|0.529412|
| AP |0.426233|0.437595|
| 균등 BCE |0.698560|1.303159|
| 무정보 BCE |0.693147|0.693147|
| FP예산7에서 최대TP(사후 진단) |3|3|

사전 연구 채택 기준은 AUROC/AP 개선, BCE<ln2, FP/FN 모두 증가하지 않고 하나 이상 감소다. 미달이므로 candidate_accepted=false다. 비교기 ranking_improved=true만으로 채택하지 않는다.

특징 차원576→384와 CLS 특징 스케일도 바뀐다. 동일 /D 거리식을 사용해도 backbone 간 확률 단위가 교정되는 것은 아니므로 BCE 악화를 표현력 악화 하나로 단정하지 않는다. 양의 온도 스케일로 0.5 판정이나 순위는 바뀌지 않으므로 이번 오류 수 개선을 위해 온도를 추가 탐색하지 않는다. 작은 반복 val의 미세 AUROC 상승은 독립 성능 입증이 아니다.

## 구현 범위

- card_condition/observation_backbone.py: 선택 전용 DINOv2 ViT-S/14 CLS384 descriptor. nn.Module wrapper의 singleton spatial map으로 기존 global pooling 경로 재사용. 공식 코드 revision7764ea0f912e53c92e82eb78a2a1631e92725fc8 고정, frozen/eval.
- card_condition/visibility_model.py: 기본 MobileNet 유지, DINOv2는 centroid/context/box 단독 조건에서만 허용. 보고서·checkpoint에 이름/코드revision 기록, 잘못된 계약 거부. 구형 MobileNet checkpoint의 메타데이터 누락도 호환.
- card_condition/cli.py: visibility-experiment --backbone 선택 옵션. 기본 mobilenet_v3_small.
- tests/test_observation_backbone.py: pinned/frozen descriptor, 저장·재추론 일치, 잘못된 revision/혼합실험 거부, 구형 checkpoint 복귀.
- pyproject.toml0.4.42, README.md, 계획/본 보고서, 소비 프로젝트 CONDITION_ANALYSIS_TODO.md.
- artifacts/observation-dinov2-20261011/{model.pt,report.json,comparison.json,recovery.json,verify.py}: 실행 결과와 복귀 해시. 기존 source/model/report와 사람 라벨은 그대로다.

기존 torch/torchvision/Pillow 외 필수 pip 의존성을 추가하지 않았다. 최초 선택 실행에 공식 코드·약84MB 가중치를 다운로드한다. 공식 source는 고정 Git revision으로, 내려받은 가중치는 SHA256으로 recovery.json과 보고서에 기록한다. 이후 inference에는 캐시 코드와 checkpoint 저장 가중치를 쓴다. 캐시 코드가 없으면 코드 확보를 위해 네트워크가 필요할 수 있다. 사진 외부 전송은 없다. xFormers 부재 경고는 있었지만 기본 PyTorch 경로에서 실제 MPS 실행에 성공했다.

## 실행·검증

```sh
TORCH_HOME=artifacts/torch-cache .venv/bin/card-condition visibility-experiment artifacts/observation-geometry-20261011-source.jsonl artifacts/NEW-DIRECTORY --centroid --backbone dinov2_vits14 --device mps
```

기존 이름의 output을 덮어쓰지 않는다. 실제 source·입력 이미지 해시와 live 파일의 기존 audit SHA가 동일함을 확인했다. 후보 및 복귀용 기존 checkpoint 각각 검증24면 재추론에서 보고서와 최대 차이0.0. 같은 validation 입력 비교·학습수/그룹수/가중치 정책 일치 확인. 전체89테스트 통과(27.085초), wheel0.4.42 빌드 및 Python/HTML36파일 source byte 일치. 기존 라벨 서버/UI는 수정하지 않아 재시작/재라벨링이 필요 없다.

## 바로 복귀하는 방법

이미 default는 MobileNet이고 운영 교체가 없어 모델 되돌리기 작업이 필요 없다. recovery.json의 active_development는 OBSERVATION_CONSENSUS_20261011.md다. 기존 보고서/모델/source/합의문/사용자 live의 SHA256을 기록했고 기존 모델의 실제 추론도 확인했다. 기존 checkpoint를 visibility-predict에 지정하거나 실험 --backbone을 생략하면 MobileNet 경로다. 새 연구를 시작할 때마다 이전 결과와 사람 정답을 보존한다.

코드까지 되돌리려면 .backups/dinov2-0442/의 visibility_model.py·cli.py·pyproject.toml·README.md를 복원하고 신규 observation_backbone.py·test_observation_backbone.py를 제거한다. 이후 변경이 있으면 해당 diff만 되돌린다. 사용자 라벨/source/원본은 복원하지 않는다. 선택 실험 기록·캐시는 보존해도 운영 영향이 없다.

## 다음 개발

OBSERVATION_CONSENSUS의 원칙대로 train의 관찰 제한 사유별로 입력 신호와 무늬/배경 혼동을 먼저 진단하고 독립 입력 가설을 사전에 고정한다. 흐림 train0·그늘 val0의 자료 공백을 헤드 수 증가로 해결했다고 주장하지 않는다. SPP/멀티태스크/온도는 이번 실패를 이유로 일괄 추가하지 않는다. 기존 고해상도 원본·깨끗한 비교 사진 부재 답변과 완료 라벨을 유지한다. 실제 Gemini 절감은0건이다.

공식 구현 근거: [Meta DINOv2 고정 revision hub](https://github.com/facebookresearch/dinov2/blob/7764ea0f912e53c92e82eb78a2a1631e92725fc8/hubconf.py), [공식 백본 factory](https://github.com/facebookresearch/dinov2/blob/7764ea0f912e53c92e82eb78a2a1631e92725fc8/dinov2/hub/backbones.py). 프로젝트 성능의 근거는 위 로컬 실험 기록이다.
