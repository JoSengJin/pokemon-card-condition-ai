# harness-a4-noreview-20261128 (구현: Claude, 분기 71ae689)

목표: 하네스가 띄우는 실험에서 외부 AI 자동 검토(`./review --auto`: Codex·Gemini)가 일어나지 않게 고정. 하지 않을 것: card_condition/ 수정, 실제 ./experiment 실행.

## 변경
- `harness/experiment_exec.py`: `_ENV`에 `CARD_CONDITION_AUTO_CHILD=1` 추가(`card_condition/development_review.py` `enabled()`가 설정·세션 ID와 무관하게 False). `build_plan`은 `config.plan`의 `gemini_calls_allowed`·`codex_model_calls_allowed`가 정수 0(bool·"0"·0.0·누락 거절)이 아니면 refused(계획을 몰래 바꾸지 않음).
- `tests/test_harness_b5_experiment_exec.py`: 가짜 ./experiment가 받은 환경(AUTO_CHILD)을 기록, 새 시험 `test_external_ai_review_is_off_for_the_child_and_plan_must_forbid_it`, 합성 계획 고정값에 `NO_AI`(두 키 0) 추가(이 키가 계획의 새 필수 항목이라서).

## 근거
- `CARD_CONDITION_AUTO_CHILD`는 cross_review.py·cross_review_manual.py·cross_review_auto_child.py에서도 "자동 검토 자식" 표지로 쓰이는 기존 값이라 재사용했다.
- 수정 전 시험: 환경 `[None] != ['1']`로 실패 확인. 결함 주입(환경 키 제거 / int 검사 제거 / 값 0 검사 제거) 3종 모두 시험이 잡음.

## 보고만 하는 반례(card_condition 미수정)
- `development_review.enabled()`: 설정에 session_id가 없고 환경에 CODEX_THREAD_ID도 없으면 `None == None`으로 켜지고, 37행 `os.environ['CODEX_THREAD_ID']`에서 KeyError. 하네스 경로는 AUTO_CHILD로 막히지만 수동 `./experiment` 경로는 그대로다.
- `gemini_calls_allowed == 0`이어도 `after_experiment`는 enabled 이후 journal·latest.json을 쓴다.

## 한계·미검증
- 증거 수준: 구현 완료 + 합성 종단 검증. 실제 ./experiment 실행은 안 했다(금지). `codex_model_calls_allowed` 키를 실제 ./experiment·card_condition이 읽는지는 확인하지 못했다(grep 결과 이 저장소 코드에서 쓰는 곳 없음, 하네스 쪽 필수 표지일 뿐).
- 계획 JSON에 두 키가 필수가 되므로 기존 계약 생성 경로(analyze/vs3 등)가 이 키를 넣지 않으면 실행 단계에서 refused된다. 전체 시험 결과는 아래.

## 롤백
`git revert <A4 커밋>` (두 파일 + 이 문서).
