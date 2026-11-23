# Codex 인계: 세 규칙 강제 조사 (Claude, 2026-11-24)

이 문서는 사실 인계다. 새 개발·실험·외부 호출 승인이 아니며 메인 역할을 넘기지 않는다. 규칙 원문은 AGENTS.md·PAIR_CODING.md가 우선한다.

## 지금 달라진 것

1. **GitHub main 보호(사용자 설정).** ruleset `main-no-force-push`(id 27943692): active, 기본 브랜치, `non_fast_forward`·`deletion`. 일반 push는 그대로다. 공개 API로 확인했고 bypass 목록이 비어 있는 것은 사용자 화면으로 확인했다. 실제 force push 거절 시험은 하지 않았다. main 외 브랜치는 대상이 아니다. 강제 push가 필요하면 사용자만 일시 해제할 수 있다.
2. **Claude 전용 기록 훅.** 기본 checkout의 추적하지 않는 `.claude/settings.local.json`에 등록했다. 막지 않고 `would-block.jsonl`에 남긴다. 끄기는 그 파일 삭제 또는 시작 환경의 `RULE_GUARD_OFF=1`. **Codex에는 적용되지 않는다.**
3. **문서 이동.** 참조가 없던 8개를 `docs/history/`로 옮겼다(`ec92afa`, 내용 불변). 목록은 docs/history/README.md.

## 통합하지 않은 것

- 브랜치 `claude/rule-guard-20261124`: 판별기 고정 `4a9273a`, 인계 문서 `25cccb3`(전체 SHA는 `git rev-parse`로 확인). 파일은 `tools/rule_guard/*`, `tests/test_rule_guard.py`, 해당 task 문서. push하지 않았다.
- **그 worktree를 지우지 말 것.** 훅이 그 경로의 코드를 쓰고 로그도 거기 쌓인다. 지우면 기록만 조용히 멈춘다.
- 통합은 현재 메인이 검토해 정한다. 차단용으로 쓰지 않는 것을 추천한다.

## 측정 (모델 성능과 무관)

| 시험 | 결과 |
|---|---|
| 11월 Claude 호출 8,681건(고정 뒤 1회 채점) | 잠금 위반 77건 중 미탐 6, 잠금 오차단 0. 실험 오차단 1. 실험·force push 위반은 0건이라 미탐률 미측정 |
| 실제 세션 1회(Sonnet 5.5, 격리 복제본) | 금지 호출 4건 모두 기록, 막힘 0 |
| Opus 5.5 우회 45개 | 45개 모두 판별기 통과. 격리 실행으로 43개가 실제 위반, 2개 미확인. 정상 명령 오차단 11/11, 4개 미확인 |

라벨러와 판별기 작성자가 같은 Claude 세션이다(독립 아님). 우회 비율은 코드를 보고 고른 공격이라 실제 위반률이 아니다. Codex 기록은 명령 수만 셌고 사람 라벨이 없어 정확도 미측정이다. 개발 진척률·모델 성능 변화는 없다.

근거는 기본 checkout의 Git 제외 `artifacts/rule-guard-20261124/`(report.html, LABEL_CRITERIA.md, data/, session-test/, bypass-test/, drafts/).

## 강제되지 않는 것

- 잠금(`./develop`)과 실험 실행기 규칙은 여전히 문서 규칙이다. AGENTS.md는 바꾸지 않았고 줄이지 않는다.
- `./experiment`의 linked worktree 거부, worker의 실행기 환경변수 검사는 미구현이다(card_condition 변경이라 별도 task·승인). 등록되지 않은 worker 거부는 과거 실험 269건 기준으로 거부됐을 것이 0건이다.
- Codex용 훅·rules, pre-push·pre-commit 훅(`core.hooksPath`)은 설정하지 않았다. 초안은 drafts/.

## Codex가 확인할 것

1. `git fetch` 뒤 main SHA와 이 문서를 대조한다.
2. main push가 non-fast-forward로 거절되면 force로 우회하지 말고 fetch해 원인을 해결한다.
3. worktree 정리 때 `claude/rule-guard-20261124` checkout을 유지한다.
4. 다음 후보(미승인): 실험 규칙을 실행기·worker 쪽에서 강제하는 task.

## 롤백

문서는 `git revert`. 훅은 `.claude/settings.local.json` 삭제. ruleset은 사용자가 Disabled로 바꾸거나 삭제.
