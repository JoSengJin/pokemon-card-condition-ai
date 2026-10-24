# 고정 타일 공간 블록 미세조정 검증 — 2026-10-10 (0.4.33)

## 합의안과 한 가지 실험

고정 특징 분류기의 표현 부족 가설을 검증했다. 이전 공간 블록 미세조정은 context 입력만 지원했다. 이번에는 같은 round21 fixed-val/tiles224/seed42/20epoch/MPS/train class balance/val balanced-selection을 유지하고 마지막 MobileNet 공간 블록 학습 여부만 변경했다. 추가 사진/정답/입력 타일 규칙/epoch 예산/optimizer 학습률은 변경하지 않았다. 마지막 공간 블록 lr=.0001·head=.001은 기존 context 미세조정과 같은 설정이다. 서로 다른 모델의 성능이 반드시 좋아진다고 전제하지 않았다.

prefix는 eval·requires_grad=false로 고정하고 전체 구역+고정2×2타일5개에 대해 공간 특징을 미리 계산한다. train에서만 마지막 inverted residual block과 head의 gradient를 갱신한다. tile tail feature는 전체구역 평균 특징과 네 타일 평균 특징의 채널별 max를 합쳐 구역당 한 정답/loss를 계산한다. 결함 구역의 네 타일에 결함 정답을 복제하지 않는다. BatchNorm running statistics는 고정한다. val은 torch.set_grad_enabled(false)로 model선택 loss만 계산한다. 최저val epoch의 tail과 head를 함께 복원해 동일checkpoint를 저장한다.

기존 frozen tiles/context 경로는 기본값 그대로다. 새 CLI 사용은 point-experiment <snapshot> <새 폴더> --edge-input tiles --fine-tune-spatial --balance --balanced-selection --epochs 20 --device mps. point_probe/listing_inference/benchmark의 공통 로더는 저장된 전체 backbone을 읽으므로 별도 서비스 경로나 새로운 모델 architecture 이름이 필요 없다.

## 실측

검증50입력 구역/8실물 중 엣지 정답27/7실물(정상12·결함15). 두 모델 모두epoch20 선택.

|지표|기존 round21 frozen tiles|round21 spatial tiles|
|---|---:|---:|
|FP/FN (0.5)|4/3|3/4|
|TP/TN|12/8|11/9|
|AUROC|0.8222|0.8167|
|AP|0.8690|0.8574|
|별도ㅅ 정상8구역 오탐|1|2|
|탐색 .3/.7 판정 구역 / 오류|5/0|9/0|
|탐색 판정 실물 / 정답7실물|1|3|
|매물 전체 로컬 완료 / 실제절감|0/0|0/0|

오탐 감소와 보류 범위 확장이 일부 있었지만 누락·별도 정상 오탐이 증가하고 순위 지표가 낮아져 운영 채택하지 않는다. .3/.7의 판정 오류0은 작은 반복val의 선택적 결과이며 안전성 보장이 아니다. 같은 val에 맞춰 lr/epoch/문턱값을 반복 조정하지 않는다. frozen checkpoint를 교체하지 않는다.

원래 frozen 누락 구역의 점수/원본 대략 크기: e/back/upper_center0.4721·124×172px, w/front/lower_left0.4563·295×401px, ebay-7db839f540a696/back/lower_center0.4067·403×445px. 세 구역 모두 상대적으로 작은원본이라는 단일 원인으로 단정할 근거가 없다. 이 진단은 개발val을 읽은 것으로 최종시험을 열지 않았다.

## 입력 가시성 진단 보완과 휴먼인루프

기존 input-review는 전체 구역/테두리 띠만 제공해 최신 tiles 입력을 직접 볼 수 없었다. 같은 fixed_tile_boxes를 재사용해 네 타일의 native/224/448 PNG를 추가했다. PNG를 정상화한 tensor가 모델 side_tensor와 byte 수준으로 같은지 테스트했다. 선택 가능한 자료는 기존대로 train만이다. 기존 원본/띠 진단을 유지한다. 이미지 확대가 원본의 미세 정보를 복원한다고 주장하지 않는다.

train의 ㅇ-new-back만 입력 진단 생성:9구역/57뷰, artifacts/tile-input-review-round21-20261010/. 상단 중앙의 original/full224/tile224 비교 그림은 upper-center-contact-sheet.png다. 사람에게 원본과 모델 입력에서 엣지 손상이 보이는지 한 항목만 확인한다. 기존 결함 정답을 다시 수정하라는 요청이 아니며, 가시성 응답으로 정상/결함 라벨을 자동 변경하지 않는다. 정확한 손상 pixel을 추측하거나 val 사진을 학습 입력 진단 후보로 보내지 않았다.

## 파일·검증·리스크·롤백

변경: card_condition/edge_views.py(tile_prefix_maps/tile_tail_features), region_experiment.py(opt-in tiles spatial 경로), cli.py(help), input_review.py(고정타일입력미리보기), tests/test_point_spatial.py·test_input_review.py, pyproject.toml0.4.33, README, 본 보고서 및 소비 프로젝트 CONDITION_ANALYSIS_TODO.md 실행기록.

전체73테스트 통과(최종22.758초). 새 경로의 cached feature와 직접추론 feature 일치, gradient는 spatial block에만 전달, trainable block 이외 backbone/BatchNorm 불변, 저장checkpoint 직접추론이 report와일치, 최저val 선택·test 미접근·원manifest 불변 검증. 세부 PNG224 pixel과 실제 model tensor 일치, val/test 입력 진단 거부도 검증했다. 실제 모델학습/비교/별도ㅅ probe/매물14개152구역 추론 완료. artifacts/tile-spatial-round21-input-hashes-20261010.json으로 live 라벨·fixed manifest·원report 불변 확인했다.

리스크: 새 선택 실험은5뷰 spatial activation을 보관하므로 frozen head보다 학습 연산·메모리가 크다. 실제메모리 peak는 미측정이다. input-review의 이미지 파일 수와 JSON samples는 증가한다. 기본 추론/운영분기는 불변이다. 모델 구조·사진 내용·데이터 다양성 실패를 하나의 원인으로 확정하지 않았다.

롤백: .backups/tile-spatial-0433/의8파일을 원래 위치로 복원하고 신규 spatial 모델·진단·보고서와 TODO 해당기록을 별도 보관/제거한다. 기존 사용자 라벨/사진/운영DB를 되돌릴 필요 없다.
