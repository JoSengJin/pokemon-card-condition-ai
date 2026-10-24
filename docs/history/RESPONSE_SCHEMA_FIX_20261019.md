# 응답 형식 오류 진단·보완

개발 수용기준 3/3 완료: API 응답 스키마 명시, 비밀값 없는 오류 구분, mock 회귀 검증. 수정 후 실제 API 연동 재검증은 하지 않았다.

실패 실행 `artifacts/manual-cross-review/a62e86aeea99/result.json`과 SQLite calls 기록은 status=request_error, result=null, usage 입력4270/출력397/총4667이다. 실제 호출 시도는 1회다. usage를 전달받은 뒤 후처리에서 실패했을 가능성이 높지만, 기존 구현은 원문·실패 단계를 남기지 않아 JSON 문법/필드 누락/타입 오류 중 어느 것인지 확정하거나 응답을 복원할 수 없다. 기존 DB·결과를 수정하거나 재호출하지 않았다.

## 변경 파일·핵심 diff

- card_condition/cross_review.py: 기존 JSON MIME 지정에 response_json_schema를 추가했다. 8개 필수 필드를 모두 문자열로 지정하고 추가 필드를 금지한다. 파싱/검사 실패를 response_error로 분리하고 invalid_json 또는 invalid_schema라는 고정 진단 코드만 상태·journal에 저장한다. 원문 오류·응답·키를 로그에 출력하지 않는다. 기존 실패 기록은 재분류하지 않는다.
- card_condition/cross_review_manual.py: 통신 오류와 응답 검사 오류를 한글로 구분한다. 과거 request_error는 형식 오류일 수도 있음을 표시한다. 토큰 집계와 종료/중복 방지 동작은 유지한다.
- tests/test_cross_review.py, tests/test_cross_review_manual.py: SDK 요청에 스키마가 포함되는지, 잘못된 JSON/배열/빈 응답/비문자열 필드에서 usage 보존·종료·재개 시 재호출 차단과 한글 출력을 확인한다.

Google 공식 [Structured outputs](https://ai.google.dev/gemini-api/docs/structured-output)와 현재 설치된 google-genai GenerateContentConfig.response_json_schema 지원을 확인했다. 모델명·thinking 설정·호출 상한3·자동 재시도 없음·키는 그대로다.

## 실행 검증

`PYTHONPATH=tests .venv/bin/python -m unittest test_cross_review test_cross_review_manual test_cross_review_evidence -v` — 60개 통과. 로그: artifacts/cross-review-response-schema-20261019/tests.log.

이번 개발 중 실제 Gemini 호출 0회, 추가 실제 토큰 없음. 위 4667은 사용자가 실행한 실패 검토의 기록이다. mock 테스트 토큰과 혼합하지 않았다. 모델 학습·새 추론·성능 실험은 하지 않았다.

## 리스크·롤백

스키마 제약은 출력 형식의 안정성을 높이지만 응답 내용의 타당성·언어·정답을 보장하지 않는다. 수정된 요청의 실제 서버 수용 여부는 이번에 호출하지 않아 미검증이다. SDK mock으로 요청 구성과 로컬 동작만 검증했다. 자동 재호출로 확인하지 않는다.

실행 명령은 동일하다. 완료된 실패 검토 뒤 명령을 다시 실행하면 새 검토이므로 API 한도를 추가 소비할 수 있다. 실패 원문이 저장되지 않은 기존 검토를 복원하려고 재호출하지 않는다.

롤백: .backups/cross-review-response-schema-20261019/의 cross_review.py와 cross_review_manual.py를 card_condition/으로, test_cross_review.py와 test_cross_review_manual.py를 tests/로 복원한다. 기존 DB·응답·usage는 보존한다.
