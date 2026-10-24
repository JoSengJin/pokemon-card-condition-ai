# ㅇ 별도 뒷면의 부분 정상·결함 반영 — round21

## 사람 확인과 반영

사용자가 learn/ㅇ/img_2.png는 기존 img_1.png와 다른 실물이며, 좌측 상단/하단만 엣지가 정상이고 나머지6테두리는 엣지 결함, 중앙에는 미세 화이트닝이 있다고 직접 확인했다. 별도 id/group=ㅇ-new-back, train으로 등록했다. 앞면을 기존 ㅇ와 묶지 않았고 pair_verified=false다. 중앙 화이트닝은 안쪽 인쇄면의 표면 결함1로 기록했다. 모서리/센터링/나머지 표면/전체 평가 가능성은 미확인이다. 정확한 점 좌표를 추측하지 않았다.

카드 box [.043,.022,.961,.979]는 보조자의 시각적 제안이며 사람 검증 좌표로 주장하지 않는다. 파일 중복0 및 train/val 내 디코딩 이미지 중복0을 확인했다. 최종시험 사진은 열지 않았다. test의 저장된 hash가 없는 사진까지 디코딩 중복이 없다고 주장하지 않는다. 새 사진을 전체 정상 카드나 정상8구역으로 기록하지 않았다.

기존65레코드 불변, 새1레코드 추가=66. round20 fixed-val snapshot에 이 실물만 추가해 round21을 생성했다. 기존 train/val의 구역 입력 메타데이터를 모두 동일성 검산했다. train159→168구역, val50구역/8실물 유지; 엣지 정답 val27/7실물 유지. 신규 정상 엣지2/결함6/중앙 표면1이다. 정상 뒷면 엣지 학습 실물6→7, 이 중 구형 일본 디자인 정상 구역을 포함한 실물1→2다. 이는 카드 전체 정상 수가 아니다.

## 한 가지 데이터 보강 실험

round20과 동일 MobileNet frozen backbone/tiles224/seed42/20epoch/MPS/균형 train head/균형 val checkpoint 선택을 유지했다. source/optimizer/임계값 변경 없음. 이번 모델은 edge_defect만 지원하므로 중앙 표면 라벨은 저장·보존됐지만 해당 표면 결함을 학습한 것은 아니다. 두 모델 모두 epoch20 선택.

|지표|round20 균형 선택|round21 균형 선택|
|---|---:|---:|
|FP / FN (0.5)|5 / 3|4 / 3|
|TP / TN|12 / 7|12 / 8|
|AUROC|0.8278|0.8222|
|AP|0.8771|0.8690|
|별도ㅅ 정상8구역 오탐|1|1|
|탐색 .3/.7 판정 구역 / 오류|7 / 0|5 / 0|
|탐색 판정이 나온 실물 / 정답7실물|2|1|
|전체 매물 로컬 완료|0|0|

개선된 오탐은 d/back/lower_right 한 구역이다. 기존 누락3곳 e/back/upper_center, w/front/lower_left, ebay-7db839f540a696/back/lower_center는 그대로 남았다. .3/.7 판정5개는 모두 d에 몰려 있다. 특정 오탐1개 개선을 일반화 개선으로 해석하지 않으며 전체 지표·보류 범위가 함께 개선되지 않아 운영 채택하지 않는다. val을 반복 개발에 사용한 결과로 최종 성능 근거가 아니다.

같은 checkpoint listing-infer로14매물/152관찰가능 엣지 구역 실제 실행 완료. whole-listing 조건 미충족/센터링·모서리·표면 지원 부족 등 보류 유지. actual_calls_saved=0, requires_gemini=true.

## 검증과 산출물

데이터 반영 스크립트에서 이미지 디코딩·annotation schema·edge 정상2/결함6·surface 양성1·corner 미확인·기존65행 불변·기존 검증 입력 완전 불변·신규9구역·train만 추가를 assert했다. comparison은 정답/그룹/좌표/hash/혼동행렬을 검산했다. 학습 후 live 라벨 hash 불변 검증. 이번 턴 실행 소스 수정이 없어 전체 suite는 재실행하지 않았고, 직전0.4.32의72테스트 통과 결과와 구분한다.

artifacts/ieung-new-back-confirmation-20261010.json은 확인 근거·백업·원본/변경 후 hash를 기록한다.
artifacts/point-evidence-20261010-round21-fixed-val.jsonl
artifacts/point-edge-tiles-20261010-round21-balanced-selection/{report.json,model.pt,inputs.jsonl}
artifacts/balanced-selection-round21-comparison-20261010.json
artifacts/balanced-selection-round21-s-probe-20261010.json
artifacts/balanced-selection-round21-listing-inference-20261010.json

## 리스크·후속·롤백

샘플 다양성은 일부 늘었지만 독립 정상 실물·촬영 조건은 여전히 적다. 현재 결과는 확정 라벨을 다시 수정할 이유가 아니다. 같은 입력으로 네 모델을 무조건 반복 학습하지 않는다. 새 정상 구역이 있는 구형 일본판 실물 또는 관찰 가능한 결함 자료가 도착하면 부족 분포를 확인해 다음 실험을 정한다. 반복 val의 임계값을 조정해 운영 성능을 주장하지 않는다.

변경 파일은 data/learn-review.jsonl(새 레코드1), 신규 snapshot/실험 artifacts/본 보고서, 소비 프로젝트 CONDITION_ANALYSIS_TODO.md 실행 기록이다. 소스·패키지 버전·운영 모델/DB는 변경하지 않았다. 기본 샌드박스의 localhost 요청 실패를 종료로 잘못 판단해 서버 시작을 시도했으나 기존 포트 사용으로 거부됐다. 권한 있는 읽기 확인에서 기존8766 서버(PID8869)의 HTTP200을 확인했으며 기존 서버를 교체하거나 종료하지 않았다.

롤백은 data/learn-review-before-ieung-new-back-20261010.jsonl.bak로 복원하되 이후 사용자 저장이 있으면 전체 덮어쓰지 말고 ㅇ-new-back 레코드만 제거한다. 원래 ㅇ 카드 정답은 보존한다. 신규 round21 모델/진단만 별도 보관/제거하면 된다. 기존 운영 모델은 교체하지 않았다.
