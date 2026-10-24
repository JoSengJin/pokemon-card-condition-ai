# 미세 엣지 신호 집계 검증 — 2026-10-10 (0.4.34)

## 사진·정답 혼동 정리

사용자가 세 결함(좌하단/우상단 모서리 까짐·우측 중간 엣지)은 img_1을 보고 설명했다고 정정했다. img_2의 정상 엣지2/결함6/중앙 표면1은 그대로 유지한다. live recordㅇ의 img_1에 두 모서리 양성만 사용자 근거로 추가했다. 기존 모든 엣지 구역·다른65레코드는 불변이다. img_1의 좌하단 엣지0과 모서리1은 서로 다른 결함 종류여서 충돌하지 않는다. 앞서 상단 중앙 가시성 응답은 사진 연계가 확정되지 않아 입력 손실의 검증 근거로 사용하지 않는다. 위치 정정 receipt도 img_1 기준으로 바로잡았다.

이번 중앙/타일 실험에 사용한 frozen round21은 변경하지 않았다. 새 모서리 라벨은 live에 보존되지만 이번 엣지 전용 실험의 학습 자료/대상이 아니다. 핑크 표시 캡처는 사람이 확인한 미세 엣지 근거이며, 표시된 캡처를 학습 이미지로 넣거나 정밀 점 좌표를 추측하지 않았다. 배경/무늬는 img_2의 우측 중간과 시각적으로 일치하지만 crop→원본 픽셀의 정밀 대응은 계량 검증하지 않았다.

## 입력 크기와 가설

train ㅇ-new-back 상단 중앙 원본 구역은144×200px, 고정 타일은72~73×100~101px다. 224px pad는 축소가 아니라 확대다. 그러므로 이 입력에서 ‘224로 축소돼 사라졌다’고 단정할 수 없다. bilinear 보간·미세 신호·전체 공간 평균·사진 품질 등은 별도 가설이다. 확대만으로 없는 디테일을 복원하지 않는다. 다른 구역/사진의 크기까지 동일하다고 일반화하지 않는다.

선택 실험 tiles-max는 기존 전체 구역의 공간 평균 특징을 유지하고, 네 세부 타일만 공간 평균에서 공간 최댓값으로 변경한다. 이후 네 타일의 채널별 최댓값 집계는 기존과 같다. 하나의 구역 정답/loss이며 타일에 결함 정답을 복제하지 않는다. 정확한 위치/하위 손상 종류를 검출하는 모델은 아니다.

## 같은 조건의 한 실험

round21-fixed-val, MobileNet frozen backbone,224px,seed42,20epoch,MPS,train class balance,val balanced-selection 모두 기존과 같다. 미세조정 옵션과 조합하지 않았으며 데이터/입력box/이미지 보간/학습률/임계값은 변경하지 않았다. 선택 epoch는16이다.

|지표|기존 avg tiles|spatial max tiles|
|---|---:|---:|
|FP/FN (0.5)|4/3|5/5|
|TP/TN|12/8|10/7|
|AUROC|0.8222|0.6556|
|AP|0.8690|0.7753|
|별도ㅅ 정상8구역 오탐|1|3|
|탐색 .3/.7 판정 구역 / 오류|5/0|11/3|
|탐색 판정 실물 / 정답7실물|1|4|

검증50입력 구역/8실물 중 엣지 정답27/7실물(정상12·결함15)이다. 보류가 줄었지만 확정 판정 오류도 증가했다. 여러 지표가 악화돼 운영 채택하지 않는다. 새 checkpoint는 별도 후보 보관하며 기존 모델/라우팅을 교체하지 않는다. 최대 집계가 개선을 보장하거나 실패 원인을 특정했다고 주장하지 않는다. 기존 반복val을 계속 보면서 학습률/threshold를 탐색하지 않는다.

## 파일·검증

- card_condition/edge_views.py: 선택 정책 tiles-max, 전체 평균 유지/타일 공간 max.
- card_condition/region_experiment.py: 선택 학습 입력·architecture/crop_policy metadata 연결; fine-tune-spatial 조합 거부.
- card_condition/point_probe.py: 새 checkpoint 정책과 supported/edge_input 일치 검증; 기존 loader를 사용하는 probe/benchmark/listing 추론과 공통 전처리.
- card_condition/cli.py: --edge-input tiles-max 선택.
- tests/test_tile_max.py 신규: 수학적 pooling 계산/기존 평균 경로 동일, backbone 고정, 실제 학습→저장→추론 점수 일치, 정책 불일치 거부, test 미접근/manifest 불변, 매물 추론 연결.
- pyproject.toml0.4.34, README/본 보고서/TODO; live img_1 모서리 정답·확인 receipts.

전체75테스트 통과(25.121초). 실제 새 후보 학습/비교/별도ㅅ probe/14매물152관찰가능 엣지 구역 추론 실행. .3/.7은 고정 탐색 기준이며 운영 정책이 아니다. whole-listing 완료0·실제Gemini절감0. artifacts/tile-max-round21-input-hashes-20261010.json으로 실험 시작 후 live 라벨/frozen snapshot/원report 불변을 확인했다. 학습자료 사진과 운영DB를 변경하지 않았다. 최종시험 사진은 열지 않았다.

## 다음 휴먼인루프·리스크·롤백

현재 tiny whitening의 정확한 원본 위치/가시성이 연결된 사례가 부족하다. 같은 val로 또 다른 집계를 반복하기 전에 img_2의 더 큰 원본 파일이 있는지 확인한다. 같은 실물의 고해상도 사진은 같은 train group으로 보존하고 새로운 독립 실물 수로 세지 않는다. 다른 촬영/크롭이면 좌표·관찰 범위도 자동 복사하지 않는다. 확대 캡처·생성형 복원은 원본 디테일의 대안이 아니다. 사람이 이미 확정한 결함 정답을 모델 결과 때문에 다시 수정하도록 요청하지 않는다.

리스크: spatial max는 정상 무늬/밝은 픽셀에도 강하게 반응할 수 있으나 이번 오류의 확정 원인으로 증명된 것은 아니다. 후보가 악화돼 선택 기능만 보존하고 기본 tiles 동작은 유지한다.

롤백: .backups/tile-max-0434/의 코드/버전/README를 복원하고 신규 tests/test_tile_max.py 및 artifacts를 별도 보관/제거한다. 정확한 사용자 img_1 모서리 라벨은 코드 롤백 때문에 지우지 않는다. 데이터까지 복원해야 하면 이후 사용자 저장을 덮어쓰지 말고 이번 두 corner 필드/notes만 백업과 비교해 선택적으로 되돌린다. 소비 프로젝트는 TODO 문서만 변경했다.


## 추가 특징 추출기 비교 — 기존 ResNet18

새 라이브러리/다운로드 없이 로컬에 이미 캐시된 torchvision ImageNet ResNet18 가중치를 사용했다. 현재 작은 MobileNet 표현이 병목인지 비교하기 위한 별도 가설이다. 동일 round21/224px/평균 tiles/20epoch/seed42/MPS/class balance/balanced-selection을 유지하고 backbone_name만 resnet18로 바꿨다. spatial-max와 섞지 않았다. 입력/라벨·학습 예산·선택 loss는 동일하지만 모델 구조와 feature dimension은 당연히 다르다. 선택epoch20.

|지표|MobileNet 평균 tiles|ResNet18 평균 tiles|
|---|---:|---:|
|FP/FN (0.5)|4/3|4/6|
|TP/TN|12/8|9/8|
|AUROC|0.8222|0.6278|
|AP|0.8690|0.7392|
|별도ㅅ 정상8구역 오탐|1|1|
|탐색 .3/.7 판정 구역 / 오류|5/0|4/1|
|탐색 판정 실물 / 정답7실물|1|2|

더 큰 특징 추출기로 바꾸는 것만으로 좋아지지 않았으며 누락이 늘어 운영 채택하지 않는다. 특정 한 모델의 결과를 모든 backbone/전이학습 실패로 일반화하지 않는다. checkpoint는 별도 보존한다. 매물 전체 지원 구역 추론14매물/152구역도 실행했으며 전체완료0/실제절감0이다. 이 실행 elapsed 약16.15초는 동시 부하·반복 측정 없는 한 실행 값이므로 속도 우위 근거로 사용하지 않는다.

기존 함수 API가 지원하던 backbone 선택을 point-experiment CLI의 --backbone으로 연결했다. 기본 mobilenet_v3_small은 유지한다. 재현:

    card-condition point-experiment artifacts/point-evidence-20261010-round21-fixed-val.jsonl <새 폴더> --backbone resnet18 --edge-input tiles --balance --balanced-selection --epochs 20 --device mps

실제 산출물: point-edge-resnet18-tiles-20261010-round21/, resnet-tiles-round21-comparison-20261010.json, resnet-tiles-round21-s-probe-20261010.json, resnet-tiles-round21-listing-inference-20261010.json, resnet-tiles-round21-input-hashes-20261010.json. 실험 시작 후 live/frozen/원report hash 불변 확인. CLI --help에서 선택값 표시 확인. 최대값/ResNet18 중 승자를 자동 선택하지 않고 기존 후보를 유지한다.
