# 0.4.49 오프라인 매물 상태·관찰 제한 연결

## 범위와 결과

CONSULTING_CONSENSUS의 매물 단위 평가와 OBSERVATION_CONSENSUS의 관찰 제한/손상 분리를 연결했다. 추가 학습·임계값 조정·라벨 변경 없이 두 고정 모델의 결과를 한 보고서에서 조회한다. 독립 test 사진 없음 답변은 유지하고 완료 라벨 재요청은 하지 않는다.

실제 MPS 실행: 같은 observation-geometry source의 val 비제외 15매물, 엣지160구역, 관찰 제한27면. 뒷면 사진 누락2건과 ㅅ 앞면 카드 영역 미지정1건은 null 점수로 기록했다. 기존24면 관찰 제한 실험과 분모가 다르다. 이 명령은 관찰 제한 정답 유무로 사진을 선별하지 않는다.

같은 입력의 옵션 없는 실행과 구역 predictions·listing_readiness 완전 일치. 결과는 artifacts/listing-observation-20261011.json, 대조군은 listing-observation-baseline-20261011.json, 검산은 listing-observation-checks-20261011.json. 관찰 제한 저점수가 사람의 반사 라벨을 지우지 않고 고점수도 카드 결함/구매 제외로 바뀌지 않는다. 운영 승인·독립 정확도 개선 주장 없음, requires_gemini=true, actual_calls_saved=0.

## 변경 파일과 핵심 diff

- card_condition/listing_observation.py 신규: 앞뒤 명시·사진당1회 추론, 사람 제한/반사 위치 보존, 누락은 unknown, 비정상 점수 차단. 면 단위 점수로 제한 위치를 추정하지 않는다.
- card_condition/listing_inference.py: 선택 관찰 체크포인트 해시와 추론 결과를 별도 필드에 연결. 기존 구역 마스킹/정책 불변. 추론 중 manifest/모델/사진 변경 시 보고서 저장 거부.
- card_condition/cli.py: listing-infer --observation-checkpoint 옵션. 기본 동작 유지.
- tests/test_listing_inference.py: 연결 전후 구역/정책 동등성·저점수 반사 보존·앞뒤 전달·모델 변경 차단 검사.
- tests/test_listing_observation.py 신규: 영역 누락/미지정 사람 관찰값·NaN/범위 밖 점수 검사.
- pyproject.toml:0.4.49. README.md:선택 옵션과 한계 설명.
- 본 보고서, 신규3개 artifacts, 소비 프로젝트 CONDITION_ANALYSIS_TODO.md:실행 기록. 소비 프로젝트 실행 코드/DB 변경 없음.

## 검증

전체109테스트 통과(34.955초), 새 helper2테스트와 기존 통합 테스트 통과. wheel 0.4.49 내 Python/HTML42파일이 소스와 바이트 일치. 실제 CLI MPS 실행과 대조 실행 완료. 최초 구역 패치 목록을 manifest로 지정한 실행은 schema 오류로 안전하게 거부됐고 산출물 없이 종료됐다. 이후 원본 매물 manifest로 실행했다.

live 라벨 SHA c61e11649ed52cd86af1b40ee4eafab45bb604f71c4ccfdf64d69b118ebdbf94 유지.
source SHA 245430db5006a38d8d53a9061f5d21cc1fec99b3520f753c52121c5c3841e77c 유지.
관찰 모델 SHA bb19115e0a133ec2fb82229e1e15222544b026e0c1b657c3b4fb7fb72b082bda 유지.

## 리스크와 롤백

관찰 점수는 미교정·면 단위이며 독립 검증 전이다. 추가 모델의 메모리/추론 비용이 발생한다. 제한 원인·위치를 자동 판정하지 않는다. 이 연결은 정확도 개선이나 Gemini 절감의 증거가 아니다. UI/서버/운영 fallback 변경은 없다.

즉시 복귀: --observation-checkpoint 옵션을 생략하면 기존 경로. 소스 복원은 .backups/listing-observation-0449의 listing_inference.py·cli.py·pyproject.toml·README.md를 원래 경로에 복사하고 신규 helper/테스트를 제거한다. 기존 테스트 파일에는 이번 연결 검사 블록만 제거하고 사람 라벨/모델 파일은 건드리지 않는다.

에튜: 관찰할 수 있는가와 결함이 있는가는 다른 예측 문제다. 결과를 먼저 분리해 연결해야 반사 점수가 카드 상태 판정으로 잘못 전파되는 것을 검증할 수 있다.
