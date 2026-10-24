# r 자동 반증 검토

개발 수용기준 4/4 완료: 자동 질문·근거 선택, 한글 전송 미리보기, 재개 시 질문/호출 중복 방지, 검토당 최대 3회 유지. 모델 성능 개선을 뜻하지 않는다.

명령은 `./review` 그대로다. 응답 후 `r`만 누르면 추가 검토한다. Enter는 종료, q는 보존 후 나가기다.

## 핵심 변경

- `card_condition/cross_review_manual.py`: API 없는 로컬 규칙으로 현재 원인 가설과 실험 제안을 대조한다. 첫 반증은 증상/원인과 최신 결과·오류·코드의 모순, 두 번째는 단일 변수와 반증 가능한 성공/실패 기준이다. 손실/logsumexp 또는 공간/마스크 주장이 있으면 각각 학습과 추론의 구분, 공간 진단의 적용 범위를 묻는다. 존재하는 근거 ID만 선택하며 해당 가설의 실패 근거도 포함한다.
- 선택 질문·근거 원문과 전송 범위를 화면에 표시한다. 질문과 안내는 한글이며 코드·식별자·저장된 근거 원문은 보존한다. 동결된 기존 근거 묶음 + 현재 응답 + 새 질문을 보낸다. 전체 대화를 누적하지 않는다.
- 제출한 반증 종류는 기존 decision 기록에 함께 저장한다. 재개 후 다음 질문을 선택한다. 사람이 필요한 응답·반복 주장·새 대조 항목 없음·예산·API 오류 종료와 기존 체크포인트/캐시/최대 3회는 유지한다. r 한 번은 추가 호출 최대 한 번이며 질문 생성용 호출은 없다.
- `tests/test_cross_review_manual.py`: r만으로 3회 상한, 유효 근거 선택, 현재 주장별 질문, 사람 의존 차단, q 재개 시 다음 질문/완료 호출 보존, 동일 주장 2회에서 종료를 검증한다.
- README.md, ONE_COMMAND_REVIEW_20261019.md, CURRENT_REVIEW_EVIDENCE_20261019.md: 직접 질문/ID 입력 안내를 현재 동작으로 갱신했다.

## 실행 증거

`PYTHONPATH=tests .venv/bin/python -m unittest test_cross_review_manual test_cross_review test_cross_review_evidence -v` — 58개 통과. API 응답은 mock, LangGraph와 SQLite 중단·재개는 실제 실행했다. 로그: `artifacts/cross-review-auto-question-20261019/tests.log`.

현재 프로젝트 최신 자료에서도 로컬 선택을 실행했다. `artifacts/cross-review-auto-question-20261019/local-selection.json`에 latest_result/remaining_errors/related_code/executed_code 선택 결과를 남겼다. 이 파일의 응답은 선택 규칙 확인용 가설이며 새 Gemini 응답이 아니다.

이번 실제 Gemini 호출 0회, 실제 사용 토큰 미측정. 모의 3회 시나리오의 합계 150토큰은 테스트 값이다. 학습·추론·성능 실험은 실행하지 않았다. 실행 명령·키·라벨·모델은 변경하지 않았다.

## 리스크와 롤백

규칙 기반 반증이므로 모든 주장을 의미적으로 이해하는 것은 아니다. 화면에서 선택 근거와 질문을 확인할 수 있고 결과는 제안으로만 저장한다. 최대 3회는 목표 횟수가 아니라 상한이며 반복·사람 의존이면 먼저 종료한다. r 이후 취소 질문 없이 API가 호출되므로 보존만 원하면 q를 사용한다.

`.backups/auto-counter-review-20261019/`의 cross_review_manual.py를 card_condition/으로, test_cross_review_manual.py를 tests/로 복원하고 같은 폴더의 안내 문서 3개를 루트에 복원하면 이전 수동 입력 방식으로 돌아간다. 실행 DB·decision·응답 기록과 키는 보존한다.
