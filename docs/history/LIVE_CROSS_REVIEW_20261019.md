# Gemini 1회 실호출 및 LangGraph 검증

결과: 전용 무료 프로젝트 키로 실제 generateContent HTTP 요청을 정확히1회 전송했으나 HTTP404로 실패했다. 실연동 완료나 모델 성능 개선으로 보고하지 않는다. 실사용 토큰은 응답 metadata가 없어 미확인이며0으로 기록하지 않았다.

이번 실검증 수용기준 3개 중2개 확인(67%): ①실제 요청1회 상한 준수 ②오류 checkpoint 종료·재진입 추가 호출0 ③정상 Gemini 응답→근거 대조 interrupt→재개는 실제 응답 부재로 미검증. 이는 전체 모델 개발 진척률/정확도와 무관하다.

## 요청과 실제 수치

- 요청 시각: 2026-10-19 07:23:46 KST.
- 모델: gemini-2.5-flash-lite, 최대1회, thinking_budget=0, 출력최대2048, 전체예산18048, 시간300초.
- 전송: 사용자가 명시 승인한 기존 오류5건·동일26구간 지표·실패가설2개·코드 발췌·출처 경로/해시. 키/사진/전체 대화/전체 저장소는 프롬프트에 넣지 않았다.
- HTTP 요청1, 성공 생성0, 자동 재시도0, fallback0, 재진입 추가 요청0.
- HTTP 응답404. SDK가 usage metadata를 반환하지 않아 입력/출력/thinking/총토큰 모두null(미확인). 입력 예약량3721은 UTF-8 바이트 기반 사전 예산이며 실제 토큰 수가 아니다.
- DB journal은 request_error 1행. 실제 LangGraph checkpoint.next는 빈 목록으로 종료 상태다. 같은 입력을 재진입해도 동일 오류를 반환하며 추가 전송하지 않았다.

증거: artifacts/cross-review-live-20261019/http-requests.json, initial.json, replay.json, replay-after-fix.json, state.sqlite, verification.json. 재현 runner run_once.py는 HTTP 전송 전에 영구1회상한을 확인한다. 키나 URL query/header를 기록하지 않는다. 최초 요청의 에러 본문은 기존 보안 정책에 따라 저장되지 않아 상세 서버 사유는 확정할 수 없다.

## 원인 진단과 수정

[공식 폐기/접근 안내](https://ai.google.dev/gemini-api/docs/deprecations.md)는 2.5 계열을 과거 사용 이력 프로젝트로 제한하고 새 프로젝트에는 3.5 Flash-Lite/3.8 Flash를 권한다. 이번 전용 프로젝트는 신규이며404와 일치한다. 가격표에 무료라고 표시된 사실만으로 신규 프로젝트 접근 가능성을 판단한 이전 선택을 정정했다.

[3.5 Flash-Lite 가격표](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite)의 무료 입력·출력과 [thinking 제어](https://ai.google.dev/gemini-api/docs/thinking)의 minimal 수준을 확인했다. 신규 기본 설정은 gemini-3.5-flash-lite + thinking_level=minimal로 변경했다. minimal은 thinking 토큰0 보장이 아니다. 출력 한도·전체 예산·실제 usage 기록·수동 실행 계약을 유지한다. 2.5 형식은 과거 실행 조회/기존 사용자 호환을 위해 유지한다.

새 기본 모델의 실제 요청은0회다. 이번 실행 packet/config/DB는 원래2.5 요청 증거로 동결했다. 새 기본 설정으로 변경했다고 이번 호출이 성공한 것으로 바꾸지 않는다. 다음 실제 호출은 이번1회상한을 초과하므로 사용자 추가 승인이 필요하다.

## 테스트와 한계

수정 전 mock25개, 수정 후26개 통과. 실제 LangGraph·SQLite를 사용하고 SDK만mock으로 호출 상한/반복 종료/사람 대기·재개/cache/오류/예산 및 모델별 thinking 옵션을 검사했다. pip check 통과. 이 mock 성공은 실제 Gemini 정상응답·근거의 타당성·모델 성능 증거가 아니다.

키 상세창이 열린 상태를 읽은 첫 UI 도구 출력에 키 전문이 포함됐다. 이후 상세창을 닫고 비밀값을 가렸다. 실험 로그/코드/프롬프트에는 키를 저장하지 않았다. 이 노출 때문에 키 교체가 필요하며, 이번1회 요청 뒤 임의 키 변경/추가 호출은 수행하지 않았다.

새 학습/추론/정답 변경0이므로 모델 평가 전후 HTML 대상이 아니며 새 누락률·오탐률 개선을 주장하지 않는다. 기존26구간 수치는 이전 증거를 전달한 것이고 이번에 재평가하지 않았다.

## 변경 파일·리스크·롤백

- card_condition/cross_review.py: 3.5 minimal 옵션 지원, 모델별 설정 검증, thinking_level 표시. legacy2.5 캐시 해시 형식을 보존했다.
- tests/test_cross_review.py: 새 기본 SDK 설정 검증과 legacy/새 thinking 형식 혼합 거부 검사.
- examples/cross-review/config.json, artifacts/cross-review-20261019/local-config.json: 신규 기본 모델/thinking 설정. 실제 요청은 수행하지 않는다.
- artifacts/cross-review-live-20261019/: 동결입력/실제 요청 영수증/응답 상태/DB/중복 방지 runner/검증·mock로그.
- 본 문서와 CROSS_REVIEW_20261019.md: 실패와 수정 사실 기록.

리스크: 새로운 기본 모델은 아직 이 키로 실호출하지 않았다. 모델 변경은 입력 식별값을 바꾸므로 과거 실행을 임의 재개하는 것이 아니라 새 실행이다. API 사용 가능 모델/무료정책/한도는 바뀔 수 있다.

롤백: .backups/cross-review-live-20261019/의 cross_review.py, test_cross_review.py, example-config.json, local-config.json을 각각 원위치로 복원한다. 단 이전2.5 설정은 신규 프로젝트에서404 가능성을 그대로 갖는다. API 추가 호출을 막기 위해 실제 DB·http-requests.json 영수증은 보존한다. 테스트용 신규 artifact만 실행 경로에서 제외할 수 있다. 사람 라벨/학습모델/수집코드는 수정하지 않았다.
