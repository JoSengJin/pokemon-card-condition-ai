# 0.4.63 동일 타일 입력의 반복 디코딩 제거

## 결과

독립 프로젝트 개발 기반 4/6단계(67%, 정확도 아님). 동일 MPS15매물/160구역/관찰27면에서 점수·마스크·보류·사진 SHA·연구 플래그를 포함한 전체 매물 보고서가 이전 결과와 정확히 일치했다. actual_calls_saved=0, production_ready=false 유지.

전후 각3회 교차 순서 비교 중앙값 13.871905→5.789794초(58.26%감소), Image.open 호출827→187회. 각 구역의 전체+4타일은5회에서1회로 감소했고 관찰 모델27면은 기존1회씩 유지했다. 이 측정은 동일 기기·기존 검증 자료의 지연시간이며 정확도 개선/운영 동시 처리량 근거가 아니다.

## 변경 파일과 핵심 diff

- card_condition/side_experiment.py: EXIF 적용 RGB 이미지의 crop/pad를 prepared_image로 공통화. view_tensors는 같은 구역의 고정 view를 생성할 때 한 번 디코딩한다. 정규화·floor/ceil 경계·BILINEAR·회색 padding 보존. 전역 캐시 없음.
- card_condition/edge_views.py: 순차/배치 특징과 frozen prefix 타일 생성이 공유 generator 사용. 순차 백본 호출 순서/배치 크기/풀링과 gradient 경로 유지. 타일별 정답 복제 없음.
- tests/test_view_decode.py: 독립 PIL 기준식으로 JPEG·EXIF회전·흑백→RGB·224/448 정확한 텐서 일치, 구역당 한 번 열기, 다음 요청의 파일 교체 반영, prefix 타일 일치 검증.
- pyproject.toml:0.4.63. README.md 사용 설명. 본 문서와 artifacts/view-decode-20261011/verify.py·checks.json 검증 근거.
- 소비 프로젝트 CONDITION_ANALYSIS_TODO.md: 제공 사진이 기존val임과 추가 사진 없음 기록; 학습 편입/완료 라벨 재요청 금지. 운영 소비 코드는 수정하지 않음.

## 실행 검증

- 전체132테스트 통과40.509초. 최초 일부 테스트 실행에서 tests 경로를 누락해 test_pipeline import 오류가 났고 PYTHONPATH=tests로 수정한 실행7테스트 통과. 제품 코드 오류로 처리하지 않음.
- 원본 모델 및 frozen source/live SHA 불변: checks.json. 기존15매물 결과와 정확한 전체 dict 일치. 실제 사진 변경 중 요청 거부와 관찰 미확인 유지 테스트도 전체 suite에 포함.
- wheel0.4.63 빌드, Python/HTML49파일 byte 일치. 저장소 밖 /private/tmp/condition-0463-installed에서2테스트 통과, module 경로 확인.
- 이번에는 별도 재학습·독립 최종평가·서버/UI 재시작·운영 Gemini 호출을 수행하지 않음.

## 리스크와 롤백

한 구역의 RGB 디코딩 이미지가 view 생성 동안 메모리에 남는다. 5개 tensor를 모두 GPU에 올리는 배치 정책은 기존과 같으며 이번에는 실제 RAM peak/동시 부하를 측정하지 않았다. 하나의 호출 안에서만 재사용하므로 다음 요청의 파일 변경이 숨겨지지 않는다. 매물 API의 전후 SHA 검사 유지.

.backups/view-decode-0463/card_condition/side_experiment.py, edge_views.py 및 pyproject.toml을 같은 상대 경로에 복원하면 이전 처리로 복귀한다. tests/test_view_decode.py는 신규 파일이므로 구형 코드로 롤백할 때 함께 제거/보관한다. 새 문서/README 절은 이력으로 보존 가능하다. 모델·라벨은 변경하지 않았으므로 복원 대상이 아니다. 현재 AGENTS 사용자 선호를 예전 버전으로 덮어쓰지 않는다.

## 다음 의존성

반사 전용 nested 임계값 비교는 앞면 반사 양성2실물로 분리 학습 양성0인 fold가 있어 보류한다. 사용자가 제시한 ebay-616b7ea985f25f/photo-1.jpg는 기존val이므로 train에 넣지 않는다. 사용자 “추가 사진 없음” 유지. 독립 test도0개이므로 일반화/운영 우회 검증을 만들어내지 않는다. 동일 재학습이나 완료 라벨 재요청으로 이 공백을 메우지 않는다.

## 에튜 포인트

디코딩은 압축 JPEG를 픽셀 배열로 푸는 CPU 작업이다. GPU 백본 호출만 배치화해도 파일을5번 풀면 이 비용은 남는다. 이번에는 원본1회 디코딩→전체/4타일 crop→기존 신경망 순서로 바꿨다. 같은 입력 tensor를0오차로 대조해 계산 효율 개선과 모델 품질 변경을 구별했다.
