# record-sidecars-20261127 (T0: 공통 계약)

설계 정본: `docs/collaboration/plans/accuracy-expert-chain-20261126/07-experiment-ops.md` §4. T1·T2·T3·T5가 이 문서를 따른다.
이 작업은 모델 성능을 바꾸지 않는다. 분모·제외 건수·판정 주체가 기록에 보이게 할 뿐이다.

## 1. 형식 (07 §4-1)

계획의 선택 칸. 없으면 지금과 똑같이 동작하고 `reference.json`·`result.json`에 새 키가 생기지 않는다.

```json
"sidecars": {
  "exclusions": {"path": "artifacts/<묶음>/exclusions.json", "sha256": "<64hex>"},
  "row_facts":  {"path": "artifacts/<묶음>/row_facts.json",  "sha256": "<64hex>"},
  "bands": [0.2, 0.4, 0.5, 0.6],
  "preregistration": {"rules_sha256": "<사전 블록 파일 해시>", "branch_dependent": true,
                      "branch_observed": "A|B|C", "branch_evidence": {"path": "...", "sha256": "..."}}
}
```

- `exclusions.json`: `{"<칸>": {"<구역>": {"정상": n, "결함": n, "미확인": n, "판단 불가": n, "상자 미확인": {"정상": n, "결함": n, "미확인": n, "판단 불가": n}, "AI 동일": n, "AI 의심": n, "기준 판본 불일치": n}}, "kept_rule": "<문장>"}`
- `row_facts.json`: `{"<행 id>": {"background": "bg_bright|ok|corner_cut|no_blue_border|unmeasured", "px_per_mm_layer": "<10|10-15.3|>=15.3|unmeasured", "rater_kind": "human|ai_identical|ai_suspect|unknown", "criteria_sha256": "<hex>|버전 미상", "input_hold": true|false}}`
- `bands`: 기본 `[0.2, 0.4, 0.5, 0.6]`. 기술 표용이며 판정 문턱이 아니다.

## 2. 07이 문장으로만 둔 것의 고정 (이 계약에서 정함)

1. **칸 / 구역**: 칸 = 행 id를 `/`로 나눈 끝에서 두 번째 조각(`corner`, `edge`, `corner_defect`). 구역 = 행의 `area`.
2. **세는 법**: 구역 하나는 맨 위 `정상·결함·미확인·판단 불가` / `상자 미확인.*` / `AI 동일` 중 한 곳에만 센다. `AI 의심`·`기준 판본 불일치`는 위에 겹쳐 세는 표시 칸이다.
3. **kept_rule**은 아래 두 문장 중 하나만 허용한다(실행기가 문장으로 합산 방법을 정한다).
   - `BOX_OUT` = `정상·결함만 행으로 둔다. 상자 미확인 사진의 구역은 행에서 뺀다`
   - `BOX_IN` = `정상·결함만 행으로 둔다. 상자 미확인 사진의 구역도 행에 포함한다`
4. **합 검사**: 칸마다 맨 위 `결함` 합(BOX_IN이면 `상자 미확인.결함`을 더함) = 주 평가 행의 target 1 수, `정상`도 target 0과 같다. 주 평가 행에 있는 칸이 파일에 없으면 거절한다.
5. **row_facts의 예외 키**: `_measure_sha256` 하나만 행 id가 아닌 맨 위 키로 허용한다. 나머지 키 집합 = 주 평가 + 필수 평가 행 id 집합.
6. **층**: `px_per_mm_layer`는 ppm < 10 → `<10`, 10 ≤ ppm < 15.3 → `10-15.3`, ppm ≥ 15.3 → `>=15.3`. `input_hold` = 배경이 `corner_cut`·`no_blue_border`이거나 층이 `<10` (06 M2).
7. **점수 구간**: 아래 경계 포함. `<0.2`, `0.2-0.4`, `0.4-0.5`, `0.5-0.6`, `>=0.6`.
8. **사전 등록**: `rules_sha256`은 64hex 필수. 선택 키 `rules_path`가 있으면 그 파일 해시를 대조한다(07은 파일 위치 칸이 없었다). `branch_dependent=true`면 `branch_observed ∈ {A,B,C}`와 `branch_evidence` 파일 해시 일치가 필수다.
9. **결과 칸**: `result.json`의 `strata_table` = `{"after": [{background, px_per_mm_layer, rater_kind, band, target, n}], "before": [같은 형식]}`. 주 평가 행만 센다. `acceptance_passed`는 바꾸지 않는다. 07의 `tally(rows, scores, sidecars)`는 대조 점수가 필요하므로 `tally(result, sidecars)`로 한다.
10. **판정 주체(D-7 미결정)**: `ai_suspect` 행은 빼지 않고 `row_facts.rater_kind`로 표시만 한다. `ai_identical`은 행에서 빼고 `AI 동일`로 센다(07 §4-3).
11. **provenance (`<답>.provenance.json`, T3 → T1)**: 최소 키 `verdict`(`ai_identical|ai_suspect|no_match_found|unknown`), `answer_sha256`, `comparisons`(파일별 `path, matches, total, sha256, mtime`). T1은 `no_match_found`를 `human`이 아니라 `unknown`으로 옮긴다(07 §4-4 "사람 증명 아님"). `human`은 이 도구들이 만들지 않는다.

## 3. task 계약

공통: `base_sha` = 이 문서를 담은 커밋(T0). T0 자체의 base_sha = `ceed7313fceade911993933514236cf628535327`. owner = Claude, status = assigned.
금지: `tools/d2_rows.py`, `tools/diagnostics/ab-sample-size-20261124/size.py`, 기존 시험 파일, 라벨·데이터·비밀 파일 수정, 학습·추론·`./experiment`·`./review`·외부 AI, main 통합·push.
모든 소스 수정은 각 worktree의 `./develop -- <수정 명령>` 안에서 한다. 자료가 없는 worktree의 실자료 회귀는 건너뛰고 "미검증"으로 적는다.
공통 checks: `git diff --check`, allowed_files 대조.
롤백: 새 파일 삭제와 `git revert <통합 SHA>`.

| task_id | branch | allowed_files | checks | structure 함수 수(전→후) / 호출 깊이 |
|---|---|---|---|---|
| T1 zone-rows | `claude/rec-t1-zone-rows-20261127` | `tools/zone_rows.py`, `tests/test_zone_rows.py` | 07 §4-3 회귀 1~4: `tests/test_zone_rows.py` | zone_rows 0→≤5 (`parse, build, facts, write_new, main`) / main에서 ≤4 |
| T2 sidecars | `claude/rec-t2-sidecars-20261127` | `card_condition/experiment_sidecars.py`, `card_condition/experiment_record.py`(import, 호출 2줄, dict 1칸), `tests/test_experiment_sidecars.py`, `COMMON_EXPERIMENT_RECORDS.md`(절 하나) | 07 §4-2 회귀 1~5, `PYTHONPATH=tests:. python -m unittest test_experiment_record test_acceptance_caps` | experiment_record 17→17(기존 초과, 추가 없음), experiment_sidecars 0→5(`freeze, check_exclusions, check_facts, check_prereg, tally`) / `main→run→prepare→freeze→check_*`=4, `main→run→_run→complete→tally`=4. 기존 5전이 경로는 늘리지 않음 |
| T3 rater-gate | `claude/rec-t3-rater-gate-20261127` | `tools/rater_gate.py`, `tests/test_rater_gate.py` | 07 §4-4 회귀 1~4 | rater_gate 0→≤5(`values, compare, chance, verdict, main`) / ≤4 |
| T5 cluster-stats | `claude/rec-t5-cluster-stats-20261127` | `tools/diagnostics/cluster-stats-20261127/stats.py`, `tests/test_cluster_stats.py` | 05 2-2 DEFF 1.33·1.44, S4 b=30·c=26 | stats 0→≤7 / ≤4 |

handoff: 전체 커밋 SHA, 변경 파일, 구조 확인, 검사 명령·종료 코드, 미검증, 리스크, 롤백.
experiment: 없음. HTML: 모델 성능 평가가 없으므로 사진 비교 HTML 대상이 아니다.
