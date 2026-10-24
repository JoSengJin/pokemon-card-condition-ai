# 관찰 제한 자동 판정 기준 모델 — 2026-10-10 / 0.4.35

## 개발 결과

합의안의 관찰 가능성 자동 판정 경로를 상태 결함 분류와 분리했다. visibility_model.py의 데이터 준비→학습→선택 checkpoint→별도 이미지 추론과 CLI 두 명령을 구현했다. 기존 PyTorch/Pillow/torchvision MobileNetV3 Small만 재사용했으며 새 의존성·외부 API 호출은 없다. 운영 연결은 하지 않았다.

타깃1은 명시된 visibility_issues가 있는 면,0은 명시적 빈 목록이고 면 gradable=1인 면이다. 사유 미기입·gradable 미확인·사유 없는 평가불가는 정상으로 채우지 않는다. 관찰 제한이 있어도 보이는 결함 정답은 그대로 유지한다.0은 결함 없는 카드라는 뜻이 아니다. 저장 체크박스의 빈 목록이 사용자의 모든 제한 부재 확인을 완벽히 보증하지 않으므로 라벨 정의의 한계로 남긴다.

사람 box 전체 crop→224px pad→고정 ImageNet 공간 평균 특징→1출력 linear head. 사유 문자열·gradable·결함 라벨은 이미지 특징 입력이 아니라 학습 정답 작성에만 사용한다. 새 사진 추론은 이미지와 box만 받는다. 각 클래스의 각 실물 질량을 균등하게 하고 같은 실물의 여러 면을 독립 실물로 세지 않는다. train/val 역할을 변경하지 않았고 test는 읽지 않았다.

## 실제 실행

동결 artifacts/observation-source-20261010.jsonl은 live66행의 byte 사본이다. 제외/미분할/test 및 정답·box 부족 면은 학습하지 않는다. 유효 train40면/22실물(제한8면·비제한32면),val24면/14실물(제한7면·비제한17면),미확인/box·주석·사진 부족32개 면 항목 제외(실제 사진32장이라는 뜻은 아님). train 제한 사례는6실물,val 제한은4실물이다. 같은 실물의 앞뒤가 제한/비제한 양쪽에 있을 수 있어 클래스별 실물 합은 전체와 다를 수 있다.

seed42,20epochs,MPS,224px,고정backbone,AdamW head lr0.001. 학습/선택은 각각 해당 split의 클래스→실물 균등 BCE다. 선택epoch2. 기존 모델의 결함 checkpoint/임계값과 결합하지 않았다.

|검증 지표|결과|
|---|---:|
|관찰 제한 검출 TP|1|
|관찰 제한 누락 FN|6 / 7|
|제한 없음 오탐 FP|3 / 17|
|제한 없음 TN|14|
|AUROC|0.3697|
|AP|0.2813|
|균형 정확도|0.4832|

기준0.5에서 제한 누락이 많고 순위도 낮으므로 운영 채택하지 않는다. 점수/임계값을 같은 val에 맞춰 반복 탐색하지 않는다. 전부 제한 예측 기준선은TP7/FP17,전부 비제한 기준선은TN17/FN7이다. 실물별 오류/고정 보류 구간/PR·ROC는 report.json에 함께 보존했다. diagnostics의 normal/defect 표기는 일반 함수 재사용에 따른 타깃0/1 이름이며 카드 정상/하자로 해석하면 안 된다.

## 다음 개선의 근거

train 제한 사유는 glare6,perspective2,cropped2이며 중복이 있다. blur/obstruction/low_resolution 양성 학습 사진은0이다. val에는blur1·obstruction1이 있어 새로운 사유까지 검증에 포함됐으며 이 두 면도 누락했다. glare도 실패하여 unseen 사유만으로 실패를 설명할 수 없다. 작은 표본 다양성 및 전체224 공간평균 표현이 후보 가설이고 원인 확정은 아니다.

다음은 기존 완료 라벨을 재요청하거나 원본 확대본을 추가하는 작업이 아니다. 신규 실물 최대3장 단위로 반사/흐림/가림 사례와 관찰 가능한 비교 사진을 보강하거나, 실제 train 한계 위치가 충분히 지정된 경우 구역 수준 목표를 설계한다. 제한이 있어도 카드 자체가 불량하다는 라벨을 만들지 않는다. 미사용 최종시험 자료를 개발에 가져오지 않는다.

## 변경 파일·검증·리스크·롤백

신규 card_condition/visibility_model.py, tests/test_visibility_model.py. 수정 card_condition/cli.py, pyproject.toml0.4.35,README.md,마스터 TODO. 신규 동결snapshot/모델/report는 artifacts/observation-*에 보존한다. 원본 학습 데이터·사진·기존모델·PokeCollector 운영코드/DB는 수정하지 않았다.

검증 결과는 최종 실행 후 아래에 기록한다. 학습 report 예측과 checkpoint 재로딩의 실제MPS 단일면 점수가1e-5 이내 일치했고 live JSONL은snapshot과byte 동일이다. metadata/box/유한값 검증 및 test 미접근, 미확인 정답 제외, 분할/픽셀 누수 차단은 회귀 테스트에 포함한다.

초기 테스트의 좌표 예외 문구 기대값이 기존 검증 문구와 달라 실패했고 실제 메시지에 맞춰 수정했다. 해당 실패는 학습 결과가 아니라 테스트 기대 문자열의 문제다.

리스크: box는 사람이 지정해야 하며 자동 제한 위치/종류 검출이 아니다. 낮은 점수로 사람 관찰 제한을 해제하지 않는다. score는 교정된 확률이 아니다.0.5 및 탐색 보류 구간은 운영 정책이 아니다. 실제 Gemini절감0건.

롤백: .backups/visibility-0435/의cli.py/pyproject.toml/README.md를 복원하고 신규모듈/테스트를 제거한다. 산출물은 증거로 별도 보관 가능하다. 사용자 라벨 복원은 필요 없다. TODO 이번 항목만 되돌리면 된다.

최종 검증: unittest discover 전체78개 통과(24.880초), 0.4.35 wheel 빌드 성공. 포함 Python/HTML 33파일이 현재 소스와byte 일치. 최종시험·운영 API·브라우저 UI 검증은 수행하지 않았다.
