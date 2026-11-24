# 품질 규칙 적용 · 발견 2건 · 결정 5건 통합 계약 (2026-11-25)

```text
task_id: quality-decisions-20261125
owner: 계획·리뷰·조립 Claude Opus 5.5 / 구현 Claude Sonnet 5.5 (하위 에이전트 5개, 사용자 승인 분업)
status: ready_for_review
base_sha: f37f2cb0cfe54dbc2807470a6ed1a77e565916e7 (로컬 main. 조립 시점 origin/main은 18825ee)
branch: claude/quality-integration-20261125 (필수) / claude/quality-approval-options-20261125 (선택 3개)
goal: 품질 규칙 16개와 선택표, 실행기 미측정 기록, 화면 안내 2건 정정이 시험과 함께 통합 가능하고, 사용자 결정은 승인만 하면 붙일 수 있는 커밋으로 분리된다
allowed_files: 필수 브랜치와 선택 브랜치의 `git diff --name-only <base_sha> <끝>` 목록
forbidden_files: data/, artifacts/, 사람 라벨·정답·평가 자료, development-progress.json, PROGRESS_CRITERIA.md, 기본 checkout의 미커밋 파일
contract: review-rule 8개 ID·경계 불변, 계획·기록의 acceptance_passed 불변, 화면의 SCRIPT·STYLE·선택지·답 형식 불변, 승인 범위 불변
experiment: 없음 (학습·추론·외부 AI 실험 호출·라벨 변경 없음)
```

이전 작업 브랜치(`claude/quality-rules-apply-…`, `claude/quality-rule-names-…`, `claude/quality-rules-integration-…`, `claude/quality-approvals-…`, `claude/quality-decisions-…`, `claude/qd-*`)는 **통합하지 않는다**. 공개하지 않을 자료가 과거 커밋에 있어 내용을 다시 조립했다.

## 쓴 규칙과 스킬
- Superpowers 7.0.1: writing-plans(계약 안에서만), verification-before-completion, requesting-code-review(별도 Opus 5.5 리뷰어), receiving-code-review — 네 본문 전체를 읽었다. dispatching-parallel-agents·subagent-driven-development는 선택표대로 쓰지 않았다. TDD는 회귀 시험의 "고치기 전 실패 확인"만.
- 품질 규칙: `short-request-reading`, `single-source-criteria`, `label-screen-round-trip`, `regression-for-every-fix`, `label-provenance`, `label-agreement-watch`, `stop-repeated-misses`, `explicit-verdict-merge`, `zero-denominator-unmeasured`. `worker-review-checklist`는 worker 변경이 없어 해당 없음. 나머지는 실험·판정이 없어 해당 없음.

## 처리 결과

| 항목 | 처리 | 어디에 |
|---|---|---|
| 관찰 제한 휴대폰 화면 기본 안내 | 정본에 맞춤(자격아님·모름은 이 화면에 없어 미확인) | 필수 |
| 모서리 재판정 화면 안내 | 정본에 맞춤. 같은 문구를 쓰는 `relabel_corner_highres_pages.py`의 새 화면에도 적용됨. 2026-11-21 재판정은 이전 문구(d1e2197) | 필수 |
| 사용자 요청 분석 자료 | 통합본과 새 이력에서 제외(원본은 기본 checkout의 미커밋 초안 폴더). 올리려면 따로 지시 | 필수 |
| 일치율 값(최소 분모 30·목표 카파 0.80·경고 0.60) | 승인용 커밋 | 선택 1 |
| 연속 미달 3회 | 승인용 커밋, 통합 뒤 새 실험부터 | 선택 2 |
| 기준 버전 기록 안 A(모서리 화면·가져오기) | 승인용 커밋 | 선택 3 |
| AI 판정 지시서와 사람 기준의 차이 | 줄별 권장과 패치. 기본 checkout의 미커밋 지시서에 `patch -p1`로 적용(원본 SHA-256이 같을 때만) | 제안서 + 패치(승인 뒤 적용) |

## 통합 순서
1. 필수: `claude/quality-integration-20261125`(코드 끝 `5f893ab`, 이후는 문서만)를 base_sha 위에서 순서대로 전부 cherry-pick(또는 fast-forward).
2. 선택: `claude/quality-approval-options-20261125`의 제목이 `APPROVAL`인 항목 중 승인한 것만. 1 = `0b1dc33`, 2 = `5cd0740`, 3 = `f1c1e6f`와 바로 뒤 보완 커밋 `fix(label): APPROVAL 3 follow-up`(둘을 함께). 어떤 조합·순서로도 붙는다(12가지 확인). 3을 넣으면 통합 담당이 label-criteria-version task의 status를 integrated로 바꾼다. 승인 기록(날짜·근거)을 커밋 메시지나 통합 기록에 남긴다. 승인 없는 것은 넣지 않는다.
3. 지시서 패치는 승인 뒤 기본 checkout에서 적용하고 SHA-256을 기록한다.
- 선택 커밋이 고치는 파일: 1 = `LABELING_PROTOCOL.md`·`docs/agent/QUALITY_RULES.md`·`docs/AGENT_START.md` / 2 = `COMMON_EXPERIMENT_RECORDS.md`·`docs/agent/QUALITY_RULES.md`·`docs/AGENT_START.md` / 3 = `tools/label_criteria.py`·`tools/mobile_corner_label_pages.py`·`tools/mobile_corner_label_import.py`·`tests/test_label_criteria_record.py`·`LABELING_PROTOCOL.md`·`docs/agent/QUALITY_RULES.md`·`docs/AGENT_START.md`·`docs/collaboration/tasks/label-criteria-version-20261125.md`.

## Q09(`zero-denominator-unmeasured`) 설계와 호환
판정식은 그대로 두고 결과에 `acceptance_caps`를 더했다. 계획의 `evaluation_counts`는 선택 칸이다. 과거 기록 222건·평가 556개를 읽기 전용으로 다시 계산해 저장된 판정과 다른 것 0(정상 행 0인 평가 136, 결함 행 0인 평가 0). 자동 검토 계획에는 아직 `evaluation_counts`가 없다.

## structure
새 파일의 함수 수: acceptance_caps 2, test_acceptance_caps 7, test_corner_label_round_trip 7, test_label_criteria_source 7, test_label_text_regressions 5, test_quality_rule_routes 3, test_visibility_blind_round_trip ≤7, (선택 3) label_criteria 5, test_label_criteria_record 7. 기존: experiment_record 17 → 17(기존 초과), mobile_visibility 3 → 3, relabel_corner_blind 3 → 3. 호출 경로: `main→run→prepare→check_declared_counts` 3, `main→run→_run→prepare→check_declared_counts` 4, `main→run→_run→complete→cap_status` 4. 자동 검토에서 들어오는 경로는 호출자를 더하면 4를 넘지만 같은 깊이의 기존 호출(`complete→required_cohort_results→compare_predictions`)이 이미 있다(동적 경로는 미확인).

## checks
명령·종료 코드·최종 SHA는 성과 HTML과 통합 보고에 적는다. 환경: 시험은 기본 checkout의 `.venv`를 실행에만 사용, 전체 시험은 임시 복사본 + 비밀값 없는 합성 `nemotron-review.json`.

## 미해결
1. `tools/relabel_zone_pages.py`의 SCRIPT가 `#alln` 버튼을 요구하는데 `tools/relabel_corner_blind_pages.py` 화면에는 없어, 스크립트가 중간에 멈추고 "결과 복사" 버튼이 연결되지 않는다(누르면 결과 칸은 갱신된다). 같은 SCRIPT를 쓰는 highres 화면도 코드상 같다. 시험은 이 오류 하나만 알려진 것으로 허용한다. 실제 브라우저 미확인.
2. `tools/ebay_back_adjudicate_page.py:26`에 옛 관찰 제한 문구가 남아 있고, `tools/relabel_corner_repro_pages.py:11-13`은 모서리 문구를 따로 갖는다(추정 금지·mm 문턱 문구 없음). 고치지 않았다.
3. 과거 필수 평가 136개는 오탐 상한이 측정되지 않았다. 판정은 바꾸지 않았다.
4. 정본 대조 시험은 정해 둔 구절만 본다. 반대 뜻의 문장이 추가되는 것은 못 잡는다.

## 미검증·리스크·롤백
- 미검증: 실제 전화 브라우저, 새 세션이 선택표를 스스로 쓰는지, 실제 실험에서의 `acceptance_caps`, 규칙이 정확도를 높이는지, 지시서 패치의 판정 효과.
- 리스크: `acceptance_passed=true`만 읽으면 미측정 상한을 놓칠 수 있다. 읽기 기록에는 ECC 원문의 짧은 인용과 프로젝트 작업 원칙 이름이 있다. 연속 미달 값을 승인하면 앞으로의 탐색이 일찍 멈춘다.
- 롤백: 통합 커밋을 역순으로 `./develop -- git revert <SHA>`. 선택 커밋은 하나씩 되돌릴 수 있다. 지시서는 `patch -R -p1`.
