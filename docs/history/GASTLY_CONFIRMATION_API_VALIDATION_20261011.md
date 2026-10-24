# Gastly 대화 정답 반영과 독립 API 검증

개발 기반4/6=67% 유지. 사용자 재확인대로 Gastly 전체 모서리·엣지 라벨을1로 정리하고, 새2카드의 기존 독립 패키지/API/CLI 연결을 실제 모델로 검증했다. 모델 정확도 상향이나 Gemini 호출 절감은 없다.

## 변경 파일·핵심 diff

- data/independent-ebay-review-20261011.jsonl: Gastly labels.corner_defect/edge_defect를0→1, 비어 있던 reviewed_by를 사용자 대화 확인(2026-10-11)으로 기록. 근거는 사용자 ‘1번 모서리 결함 2번 엣지 결함이라고 라벨 저장했잖아’. 뒷면 두 좌표·종류·면 정답·구역별 미확인·앞면 gradable null·Persian 전체 항목은 보존했다. 새 정상 정답은0개.
- artifacts/gastly-confirmation-20261011/: 확인 영수증, 동결 inventory, 라벨 없는 API 요청2개, API 결과2개, 재현 verify_api.py, API/설치 CLI 결과·SHA 영수증.
- 소비 프로젝트 CONDITION_ANALYSIS_TODO.md: 확인 완료와 남은 정상 구역 정답 의존 기록. 모델 소스/운영 소비 코드/임계값/버전은 변경하지 않았다.

## 검증·결과

ReviewStore의 기존 원자 저장·백업·revision 충돌 검사를 사용했다. 수정 전후 point_rows의 모델 입력 패치/정답 완전 일치, Persian 및 Gastly side_annotations 완전 일치 확인. 실행 중8767 /api/review도 전체 모서리/엣지1·두 점 보존·region_labels={}를 제공함을 확인했다. 이전 독립 평가 보고서는 덮어쓰거나 반복 튜닝하지 않았다.

실제 ListingAnalyzer에 새2카드의 앞뒤 사진/box/관찰 제한만 전달했다. 입력에는 정답·split이 없다. 고정 엣지+관찰 모델을 로딩해 순차/배치 각각32구역 점수·상태/이유를 비교했고 최대 점수 차이0.0. 이미 알려진 엣지2점은 기존 독립 평가 점수와1e-6 이내 일치했고 모두 state=unknown/reason=score_deferred. 모서리는 unsupported. 두 매물 actions=['gemini_review'], local_complete_candidate=false, actual_calls_saved=0을 확인했다.

0.4.75 wheel을 저장소 밖 /private/tmp/condition-0475-installed에 설치했다. /private/tmp에서 Gastly CLI를 실행해16구역 probabilities·listing_readiness·observation_evidence·model SHA·Gemini 정책이 소스 API와 완전히 같음을 확인했다. 추가 학습/모델 선택/임계값 조정은 없다. 모델/source/live69행/새 정답/사진 SHA를 API 전후 및 설치 CLI 후 검산했다.

이번에는 소스 코드가 바뀌지 않아 전체150테스트를 다시 실행하지 않았다. 검증은 실제 저장/재로딩·모델/API/설치 CLI 실행과 명시적 assert이다. 직전 전체150테스트 결과는 INDEPENDENT_GASTLY_VALIDATION_20261011.md의0.4.75 검증이다.

정확도는 새2실물/양성 엣지2구역 TP1/FN1·누락률50%(1/2) 그대로다. 정상 구역0개라 오탐률null. 이전 대비 %p는 비교 정답/분모가 달라 계산하지 않는다. API의 미확인 보류 동작은 정확도 상향 근거가 아니다. 관찰 제한 test 양성0면·Gastly 앞면 미확인 유지로 일반화 판단은 보류한다.

## 다음 의존성과 중단 이유

Gastly 결함 지점·종류 재확인은 끝났다. 독립 오탐 측정을 위해 필요한 것은 좌측 하단 외 나머지 테두리7구역의 사람이 확인한 정상 범위다. 확인 전에는 구역을0으로 만들지 않는다. 현재 실행 TODO의 앞면 nested 실험은 학습 양성 실물 부족, 관찰 최종평가는 독립 제한 양성0에 의존한다. 그 밖의 가능한 새 입력 API/설치 경로 검증은 이번에 마쳤다. 동일 입력 반복 학습이나 test 기준 조정으로 개발량을 만들지 않는다.

## 리스크·롤백

오래 열려 있던 검토 화면은 정리 전 revision을 갖고 있어 저장 시 충돌할 수 있다. 저장하지 않은 작업을 보존한 뒤 새로고침하면 된다. 서버는 새 파일을 읽으며 강제 재시작하지 않았다. 기존 모델은 모서리를 평가하지 않고 엣지2점도 낮은 확신이다. Gemini 생략 정책은 활성화하지 않는다.

사용자 확인 정답을 보존하려면 코드/API 검증 롤백과 함께 inventory를 되돌리지 않는다. 정답 수정 자체를 취소해야 하면 data/independent-ebay-review-20261011.jsonl.<timestamp>.bak의 변경 전 파일을 새 백업과 비교해 원자 복원한다. API 검증 결과/문서는 보관하거나 별도로 제거해도 운영 코드에 영향이 없다.

에튜: 평가 기준0.5와 서비스 보류 범위0.3~0.7은 역할이 다르다. Gastly0.463은 이진 평가에서는 누락이지만 API에서는 미확인으로 남는다. 그렇다고 모델이 정확해진 것은 아니며, 불확실한 결과를 확정 판단으로 넘기지 않는 동작을 검증한 것이다.
