# 최신 자료 실제 실행 검증 — 2026-10-19

요청 검증 수용기준 3/4(75%) 확인: ① 최신 자료의 실제 정상 응답, ② 프로세스 종료 후 중복 호출 없는 재개·종료, ③ 실제 usage 보고와 사용 가이드. ④ r의 실제 추가 API 요청 성공은 이번 응답의 사람 확인 보호 조건으로 검증하지 못했다. mock 검증과 실제 검증을 구분한다.

## 실제 실행

- 명령: `./review`를 PTY 대화형 터미널에서 직접 실행.
- 실행 ID: `d69b482dde1b`.
- 모델: `gemini-3.5-flash-lite`, thinking minimal, 최대 3회. 전용 키는 기존 Free tier 확인 기록과 일치함을 해시로 확인했다. 키 원문은 출력하지 않았다. 무료 등급은 저장된 AI Studio 확인 기록(2026-10-18T22:29:53.210377+00:00)을 사용했으며 이번에 콘솔을 새로 조회한 것은 아니다.
- 입력: `artifacts/edge-normal-objective-20261019/result.json` 기반 최신 실패 3건, 같은 평가 자료의 전후 수치, 후속 공간 진단, 실패 이력, 관련 코드 일부. 사진·전체 대화·전체 저장소는 전송하지 않았다.
- 정상 JSON·한국어 응답 수신 → LangGraph compare interrupt 저장 → r 입력 → 사람 확인 보호 조건으로 추가 요청 차단 → q 저장 후 프로세스 종료 → 같은 명령 재실행 → 동일 응답·동일 동결 packet·동일 호출 key 복원 → Enter 종료.
- 최종 `unresolved`, active.finished=true, pending=0. 실험을 채택하거나 실행하지 않았다.

Gemini는 logsumexp 스케일 0.1→0.05 변경을 제안했으나, 이미 승인된 정상 영역의 육안 라벨 재확인을 요구했다. 원인 설명은 코드로 검증되지 않은 제안이다. 완료 라벨을 다시 묻거나 변경하지 않았고, r 보호 조건을 우회하거나 다른 새 검토를 시작하지 않았다. 따라서 r 자동 질문의 실제 후속 응답을 받았다고 보고하지 않는다. 현재 차단은 human_confirmation 문자열 유무에 따른 보수적 분기라 불필요한 라벨 재질문에도 추가 검토가 막힐 수 있다.

## API 실측

| 항목 | 이번 검토 |
|---|---:|
| 실제 Gemini 호출 / 정상 응답 | 1 / 1 |
| r에 의한 추가 호출 | 0 — 보호 조건 차단 |
| 프로세스 재개로 인한 추가 호출 | 0 |
| 입력 토큰 | 4,270 |
| 출력 토큰 | 415 |
| 총 토큰 | 4,685 |
| cached_content_token_count | 2,001 — 입력 metadata의 일부, 합계에 다시 더하지 않음 |
| thoughts_token_count | 미확인(null) |

수치는 calls journal의 실제 SDK usage_metadata다. 기존 실행의 토큰을 합산하지 않았다. SDK 자동 재시도는 attempts=1이며 별도 유료 모델 fallback은 없다. 비용이나 절감률은 추정하지 않는다.

## 검증 증거

- `artifacts/cross-review-live-resume-20261019/terminal.log`: 실제 명령 출력, r 차단, q 저장, 재개, Enter 종료.
- `before-resume.json`: q 직후 완료 호출 1건·대기 1건·packet/응답 SHA.
- `resume-verification.json`: 동일 packet/응답/호출 key 유지, 재개 후에도 호출 1건·대기 1건 확인.
- `verification.json`: 실제 요청 수·usage 원본·최종 상태·검증 한계.
- `artifacts/manual-cross-review/d69b482dde1b/`: 동결 packet/config, SQLite checkpoint·호출 journal, 응답·종료 결정.
- `mock-regression-tests.log`: 핵심/수동 실행/근거 수집 58개 테스트 통과. r→r로 최대 3회, q 이후 다음 질문 선택·중복 방지, 4회째 차단, 반복 종료·사람 확인 차단·API 오류 등을 mock SDK와 실제 SQLite/LangGraph로 검증했다. 이 테스트의 토큰은 실측 합계에 포함하지 않았다.

## 변경·리스크·롤백

이번에는 프로그램 소스·프롬프트·테스트·키·라벨·학습 모델을 수정하지 않았다. 새 문서 `LANGGRAPH_USAGE_GUIDE_KO.md`, 이 보고서와 위 실행 산출물을 추가했고, 기존 active 포인터는 이번 완료 검토를 가리킨다. 명령은 그대로다.

리스크: 실제 외부 호출 한 건으로 무료 한도를 소비했다. 사람 확인 필드에 따른 보수적 차단 때문에 r 실제 추가 요청은 미검증이다. 이미 완료한 라벨을 다시 요청할 필요는 없다. 이번 결과는 연동·상태 복원 확인이며 모델 성능 개선·일반화 검증이 아니다. 새 추론·성능 실험을 하지 않아 모델 비교 HTML도 갱신하지 않았다.

롤백: 소스 변경이 없어 코드 롤백은 필요 없다. 문서만 제거할 수 있으며, 외부 요청과 사용량은 되돌릴 수 없다. 실행 DB·usage·응답 기록은 감사와 중복 방지를 위해 보존한다. 완료된 이 검토는 execute로 조회해도 재호출하지 않지만, `review` 명령을 다시 실행하면 새 검토가 시작될 수 있다.
