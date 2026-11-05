# 자동 검토 correct 단계 32KB 초과 수정

- task_id: `review-correct-input-20261025`
- owner: Claude
- status: integrated (2026-11-05 Codex, source 0ce69d886576927264b3bcb1bbafcfa4cae46098 → main 8bfb160)
- base_sha: `de33cab` (main = origin/main 확인 시점)
- branch: `claude/review-correct-input-20261025`
- goal: 최신 자료(`2dea72236b02`)의 `./review --auto` 재개가 Codex correct 사전 검사(32,000 bytes)에 막히지 않게 한다. 입력 상한·근거 ID·저장 응답 재사용·호출 상한·중복 방지는 그대로 둔다.
- 발견: 22:48 실행에서 Codex verify 1회(20,600 tokens)가 완료됐다. 프로그램 검증(`actual_point_guard`, expected=False)이 correct를 요구했고, correct 프롬프트가 32,851 bytes여서 `input_size`로 모델 요청 전에 차단됐다(`validation_or_execution_error`). 수정 전 코드로 다시 실행하면 같은 차단이 반복된다(mock 재현, 호출 0).
- 원인: verify/correct Codex 입력에 `latest_plan.summary.required_cohorts`(id·acceptance 목록)와 `latest_result.summary.required_cohorts` 표가 같은 id·gate를 중복으로 실었다. correct는 여기에 verify 응답(약 4KB)을 더한다.
- allowed_files: `card_condition/cross_review_auto_context.py`, `tests/test_cross_review_correct_input.py`, 이 문서, ignored `artifacts/review-correct-input-20261025/index.html`(기본 checkout).
- forbidden_files: 모델·worker·평가 정답·사람 라벨·기존 검토 폴더·`CODEX_PROMPT_BYTES`·비밀 설정.
- contract: 계획 cohort가 id·acceptance만 갖고, 그 (id, acceptance) 집합이 최신 결과 cohort 표와 정확히 같을 때만 계획 쪽 목록을 참조 문자열로 바꾼다. 하나라도 다르면 기존 목록을 유지한다. 표의 정확한 gate는 그대로 남는다. Gemini·심판 입력과 packet은 바뀌지 않는다.
- structure: `cross_review_auto_context.py` 함수 1→1개(인라인 비교, 새 함수·호출 전이 없음). 새 테스트 파일 함수 3개. 기존 호출 경로 `run_codex_first → codex → codex_task → review_context` 변경 없음(기존 경로 깊이 초과는 이번 변경 전부터 있던 상태).
- checks:
  - 실제 저장 자료 mock 재현: correct 프롬프트 32,851 → 31,616 bytes(상한 32,000), verify 컨텍스트 26,253 → 25,038 bytes.
  - 복사 폴더 재개 replay(mock Codex, Gemini 호출 시 예외): 수정 후 `resumes` 기록, 저장 verify 재사용(재요청 없음), correct 1회(31,616 bytes), 검증 통과 후 Gemini 전 `additional_call_limit` 정지. 수정 전 코드는 같은 replay에서 `input_size` 차단, mock 호출 0.
  - 새 테스트 2개: 수정 전 코드에서 1개 실패, 수정 후 통과. `test_cross_review*.py` 207개 통과.
  - 전체 800개: worktree에서 실패 6·오류 8. 수정을 stash한 같은 worktree에서도 같은 실패가 재현되어 이번 변경과 무관하다(Git 제외 artifact 부재, 공유 의존성 venv의 sandbox 경로). 기본 checkout의 해당 모듈은 통과.
  - review identity: 현재 main 코드로 최신 packet을 만들면 `2dea72236b02`와 identity가 일치하고, 변경 파일은 동결 source hash 대상이 아니다.
- experiment: 없음. 모델·학습·실제 Codex/Gemini/NVIDIA 호출 0회. 성능 변화 없음.
- 미검증: 실제 Codex가 correct에서 유효한 수정안을 내는지, 그 뒤 Gemini·NVIDIA 실제 호출 성공 여부.
- risk: correct 여유가 384 bytes뿐이다. 이번 저장 응답은 고정이라 결정적으로 통과하지만, 이후 더 큰 packet·응답에서는 다시 `input_size` 차단이 날 수 있다(차단은 모델 요청 전이라 비용 없음). verify가 비용을 쓴 뒤 correct가 막히는 구조 자체는 그대로다.
- rollback: 통합 SHA를 `./develop -- git revert <SHA>`로 되돌린다. 되돌리면 `2dea72236b02` 재개는 다시 `input_size`로 막힌다.

## Codex 현재 main 검증 — 2026-11-05

- 통합: `8bfb160`의 전체 SHA와 원본 대응은 `git log`의 cherry-pick trailer로 확인한다. 기존 현재 코드에 +7줄, 새 테스트 2개를 포함한 전달 커밋만 통합했다.
- 저장된 verify 응답과 과거 packet, 현재 context/prompt 구성 코드, **합성 correction.errors**를 사용한 읽기 전용 프롬프트 구성: 통합 전 32,666 bytes → 통합 후 31,440 bytes(상한 32,000 불변). 정확한 과거 호출 replay·새 AI 응답이 아니다. 입력의 cohort ID·acceptance 동일 시만 결과 표 참조로 대체하며 다른 기준은 유지한다.
- 관련 `test_cross_review*.py` 207개 통과(신규 2개 포함). 첫 잠금 내 실행은 임시 fixture에 부모 checkout lock FD가 상속되어 실패1/오류26이었다. 부모 main 잠금은 유지하고 자식 테스트에서 `CARD_CONDITION_WORKSPACE_LOCK_FD` 환경변수만 제거해 임시 root의 별도 잠금을 사용하자 전체 통과했다. 코드 실패를 숨기거나 잠금을 삭제하지 않았다.
- 실제 Codex correct 응답·Gemini·심판·실험·모델 추론은 실행하지 않았다. 다른 packet의 32KB 통과나 응답 품질을 보장하지 않는다. 이번 고정 입력의 여유는 560 bytes다. 토큰/비용 절감률과 모델 성능은 미측정이다.
- 감사·HTML: ignored `artifacts/worktree-followup-20261105/`. 원래 worktree와 브랜치는 삭제하지 않는다. 전체 결과는 `docs/collaboration/reports/worktree-followup-20261105.md`.
