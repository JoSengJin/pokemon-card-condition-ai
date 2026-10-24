# PSA10 보강·고정 타일 검증 — 2026-10-10

사용자가 세 카드 뒷면 테두리 전체를 확인해 정상이라고 명시했다. psa10/1·2·3을 서로 다른 train 실물 psa10-1·2·3으로 등록하고 뒷면 엣지8구역씩24개만 정상으로 반영했다. 앞면·모서리·표면·센터링과 전체 평가 가능 여부는 추정하지 않았다. 앞뒤 사진이 같은 실물인지 자동 검증하지 않았다. PSA10은 사용자 제공 참고 정보이며 인증번호/등급을 독립 검증하지 않았다. 카드 영역은 원본을 보고 제안한 box로, 사람이 정밀 확인한 좌표라고 표시하지 않았다.

기존61개 레코드는 의미상 동일, 신규3개 추가로64개다. 전체 live 자료에는 별도 진단 ㅅ도 포함돼 val58구역이지만, 실제 비교에는 round18을 그대로 복사하고 신규 train3개만 추가한 `point-evidence-20261010-round19-fixed-val.jsonl`을 사용했다. train127→151, 비교 val50/8실물 불변(엣지 정답은27구역/7실물). 같은 카드의8구역을8실물로 세지 않는다. 정상 뒷면 엣지 train 실물2→5. 별도 ㅅ은 학습/epoch선택에서 제외하고 반복 진단으로만 사용했다. 최종 test는 읽지 않았다.

## 가설과 구현

먼저 기존224px/고정 MobileNet/균형 엣지 head/seed42/20epoch 설정을 유지하고 신규 정상 자료 효과만 비교했다. 이어 같은 round19 자료에서 입력 방식만 고정2×2 타일로 바꾸었다. 매 구역의 전체224px 특징과 4타일 각각224px 특징을 추출하고, 타일 특징의 채널별 최댓값과 전체 특징을 이어 하나의 head로 구역을 분류한다. 타일마다 구역 결함 정답을 복제하지 않고 구역당 한 loss만 계산한다. 결함 점 좌표로 타일을 선택하지 않으며 같은 고정 위치를 학습/추론에서 사용한다. 네 타일은 원본 픽셀을 늘리지 않는다. max 특징이 결함 위치나 확률을 뜻하지도 않는다.

`--edge-input tiles`는 선택 실험이다. 기본 context/views 및 과거 checkpoint 호환을 유지한다. tiles checkpoint에 전용 architecture와 edge_input 정책을 저장하고 로더에서 일치 여부를 검증한다. 공간 블록 미세조정과 tiles 결합은 허용하지 않는다. 새 의존성은 없다.

## 동일 검증 결과

|설정|선택 epoch|오탐 FP|누락 FN|AUROC|AP|
|---|---:|---:|---:|---:|---:|
|point-edge-context-20261010-round18-epochs20|20|5|4|0.7056|0.7689|
|point-edge-context-20261010-round19-epochs20|20|6|3|0.6778|0.7424|
|point-edge-tiles-20261010-round19-epochs20|16|6|2|0.8000|0.8455|

별도 ㅅ 정상 엣지8구역 오탐: round18 context4개 → round19 context1개 / tiles1개. 반복 진단이며 독립 일반화 증명이 아니다. tiles는 신규 자료 반영 context보다 누락3→2, 구분 지표 AUROC0.678→0.800으로 개선됐다. round18 대비 오탐5→6은 악화했다. 채택 보류하며 후보만 보존한다.

고정 탐색용 normal<0.3/defect≥0.7에서 tiles는 정답 있는27구역 중11개 판단·16개 보류, 판단11개 중오탐1·결함 정상 통과0이다. 이는 검증 재사용 탐색 결과이며 안전성/운영 임계값 승인 근거가 아니다. 매물 범위14매물/14실물의 로컬 완료 후보는0, 실제 Gemini 절감0건이다. 센터링·표면·모서리를 대체하지 못한다.

동일 MPS/50구역/3회 측정(이미지 읽기·crop·전처리·동기화 포함): context 중앙값22.85ms/p95 39.17ms, tiles106.89ms/182.43ms. 약4.7배 느리다. 별도 실험 실행과 동시에 측정하지 않았다. 매물 전체 지연·동시 부하·메모리는 미측정이다.

## 다음 휴먼인루프의 근거

tiles 오탐6개 중5개는 d(front3/back2), 나머지는 i/back이다. d/back은 구형 일본 뒷면(POCKET MONSTERS 패턴), 정상 train 뒷면5실물은 현재 모두 파란 Pokemon 패턴이다(원본 육안 확인). 디자인/촬영 조건 차이가 원인이라는 가설이며 인과를 입증한 것은 아니다. d의 기존 정상/결함 정답을 모델에 맞춰 수정하거나 d를 train으로 옮기지 않는다. 다음 자료 보강은 같은 구형 일본 뒷면에서 사람이 확인한 정상 테두리 구역을 가진 다른 실물1~2장이 우선이다. 카드 전체 정상이나 PSA10일 필요 없다. 케이스 반사로 가려진 부분은 정상으로 라벨링하지 않는다. 기존 완료 카드 재작업은 요청하지 않는다.

## 변경 파일·핵심 diff

- data/learn-review.jsonl: 새3실물·사용자 확인 정상 엣지24구역, 기존61개 레코드 보존.
- card_condition/edge_views.py: fixed_tile_boxes, 전체+고정4타일 특징 max 집계.
- card_condition/region_experiment.py: tiles 선택 입력·특징 차원·전용 체크포인트 정책.
- card_condition/point_probe.py: 타일 정책 검증·공유 추론. 기존 point_benchmark는 같은 로더를 재사용한다.
- card_condition/cli.py: --edge-input tiles 노출.
- tests/test_edge_views.py: 고정 타일 범위/전체 면적·사람 좌표 독립·학습추론 일치·정책 위조 거부·benchmark·원본 불변·미사용 test 접근 차단을 기존 fixture에 추가.
- pyproject.toml0.4.28, README, 이 보고서, PokeCollector의 CONDITION_ANALYSIS_TODO.md 진행 기록.
- artifacts/import-psa10-20261010.json, psa10-human-confirmation-20261010.json, round19 raw/fixed 스냅샷, context/tiles 모델 디렉토리, psa10-tiles-round19-comparison-20261010.json, 별도ㅅ probe2개, 신규 모델 benchmark2개.

## 검증·리스크·롤백

전체66개 테스트 통과(14.623초). wheel0.4.28 빌드 및 포함31개 source/html 파일 byte 일치. 신규 정상24개만 추가, 기존 train/val 구역 정답 보존 assertion과 비교기 사진 해시/box/group/정답 검산 통과. 라이브 라벨 학습 도중 변경 없음 SHA256: 9ec6f1b6c880caf441323511ef57491a1bfae04b7c80f6d923ba15eb0623ecb4. 고정 비교 snapshot SHA256: a9e38635e278ed7890fc4486f4d58ed892cb8c66ff537af62dab08b33a3fb4da.

리스크: train 정상 뒷면 실물이5장뿐이고 PSA 케이스·해상도·뒷면 디자인 편향이 남는다. 반복 val 모델선택은 최종 성능 보장이 아니다. 타일 입력은 더 느리고 결함 위치를 직접 검출하지 않는다. PSA 등급·같은 실물 여부 미검증, 기존 운영 모델/DB/자동 Gemini 분기는 변경하지 않았다.

코드 롤백: `/private/tmp/condition-tiles-before/`의 edge_views.py·region_experiment.py·point_probe.py·cli.py·tests/test_edge_views.py·pyproject.toml·README.md를 각 원래 위치로 복구하면0.4.27로 돌아간다. 이 백업은 임시 경로다. 모델은 새 artifacts 디렉토리만 분리 보관/제거한다. 데이터는 이후 사용자 저장이 없음을 확인한 뒤 `data/learn-review-before-psa10-20261010.jsonl.bak`를 복원하면 새3실물 등록 전으로 돌아간다. 이후 저장이 있으면 전체 복원 대신 psa10-1·2·3 레코드만 선택적으로 제거해야 한다. TODO는 이번 완료 기록만 되돌린다.
