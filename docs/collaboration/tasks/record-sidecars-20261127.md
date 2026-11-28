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
experiment: 없음. 사진 비교 HTML은 대상이 아니다(모델 평가 없음). 성과·진척 HTML은 `docs/collaboration/HTML_REPORTING.md`에 따라 기본 checkout의 Git 제외 `artifacts/record-sidecars-20261127/report.html`에 만든다.

## 4. 계약 갱신과 인계 (2026-11-27, status = ready_for_review, 미통합·미push)

- 허용 파일 추가: 파일당 함수 7개(PAIR_CODING §2.1)를 시험 파일에도 적용해 `tests/test_zone_rows_files.py`(T1), `tests/test_experiment_sidecars_gates.py`(T2), `tests/test_rater_gate_real.py`(T3)를 더했다.
- T3 구현 중 고정(07에 없던 것): 값은 `=` 뒤 전체 문자열로 비교(07의 50·56·62/64가 재현되는 방식). 답의 구역을 모두 담지 않은 AI 파일은 기록만 하고 판정에 쓰지 않는다. 전체를 담은 AI 파일이 0개면 `unknown`. `ai_identical`·`ai_suspect`는 확인 문장과 무관하게 남는다.
- T5 구현 중 고정: 대조 결과가 후보보다 행이 많으면(E 946 대 942) 후보 행 전부가 정답·그룹·사진·상자까지 같을 때만 비교하고 안 쓴 행 수를 출력한다.

| task | tip SHA | 함수 수(제품 파일) | 자료 없는 worktree | 기본 checkout 자료 읽기 전용 지정 |
|---|---|---|---|---|
| T1 | `b2653cce826ef659824463b5586246b69ade8dec` | zone_rows 5 | 9건 rc=0, 건너뜀 3(실자료 2 + 실행기 모듈 1) | 9건 rc=0, 건너뜀 1(실행기 모듈) |
| T2 | `626c2feaf261b65372be7b95ae944ebc54ea362f` | sidecars 5, experiment_record 17→17 | 40건 rc=0, 건너뜀 1 | 40건 rc=0 |
| T3 | `443c783595c100d34bf018592d17c261cf903037` | rater_gate 5 | 6건 rc=0, 건너뜀 2 | 6건 rc=0 |
| T5 | `3fd03cfe2e01a08d81ac99fe32a1553368fbf170` | stats 6 | 4건 rc=0, 건너뜀 1 | 4건 rc=0 |

- 임시 결합(detached, T0 위에 네 브랜치 cherry-pick, `e15b29e904dea9d20ae44073dd36e5afbd2569fb`, 확인 후 worktree 제거): 59건 rc=0. 자료 없음은 건너뜀 6, 자료 지정은 건너뜀 0.
- 바이트 동일성: 합성 fixture 2종의 `plan.json`·`reference.json`·`result.json` SHA256이 `ceed731` 코드와 T2 코드에서 같았다.
- `git diff --check` 각 worktree rc=0.
- 미검증: 실제 `./experiment` 실행(금지 범위), 통합 뒤 기본 checkout 검사, 엣지·표면 4상태 실답, 별도 코드 리뷰(하위 모델 호출 미승인).
- 미착수: T7(우선 하), T4·T6(범위 밖).
- 통합 순서: `921d152` → 이 인계 커밋 → T1·T2·T3·T5 각 `921d152..tip`. 파일이 겹치지 않는다.
- 롤백: 새 파일 삭제 + `git revert <통합 SHA>`.

## 5. 코드 리뷰와 수정 (2026-11-27, §2·§4와 다르면 이 절이 우선)

리뷰: Superpowers `requesting-code-review`, 하위 에이전트 1명, 대상 `e15b29e904dea9d20ae44073dd36e5afbd2569fb`(기준 `921d152`). Critical 0, Important 7(I-1~I-7), 구현 세션이 모두 재현·코드 대조. 사용자 "7건 수정해".

- 허용 파일 추가: T2 `card_condition/cross_review_auto_contract.py`(PROTECTED 한 줄), 새 시험 `tests/test_{experiment_sidecars,zone_rows,rater_gate,cluster_stats}_rejects.py`.
- §1·§2 보정: 실행기가 받는 `rater_kind`는 `ai_suspect`·`unknown`만. `human`은 증거 형식이 정해지기 전까지 거절. 중복 JSON 키 거절.
- zone_rows: `--provenance`를 주면 dict·네 verdict·`answer_sha256`을 항상 검사. side는 `back`만. 유한한 양수가 아닌 ppm 거절. `기준 판본 불일치`의 0은 미측정.
- rater_gate: 답 파일은 주석·빈 줄 말고 못 읽는 줄이 있으면 거절. 인라인 주석 거절. `no_match_found`는 같은 화면(또는 화면 표기 없음)의 전체 포함 AI 파일이 있고, 못 읽은 AI 파일이 `.log`·숨김 파일뿐일 때만. `ai_identical`·`ai_suspect` 표시는 다른 화면 파일로도 남는다. 결과: JSON 판정 파일이 있는 묶음은 `unknown`.
- stats: 후보·대조 점수 모두 검사, 후보 id 중복·식별 칸 누락 거절, 사진 1장은 구간 미측정.

| task | 수정 후 tip SHA |
|---|---|
| T1 | `489d3b0ab4e91653ea6aa70c3438e8fe4a7c7c72` |
| T2 | `1d7ebc7865df9e3cc2f9b48e630cd9c85e29f0d1` |
| T3 | `8da1a73f97825126832d9693e5ecf6d31f2404d5` |
| T5 | `bc37a10d6e4188baf0e930f721e040081d3b066c` |

- 반례 시험은 수정 전 네 브랜치에서 모두 실패(RED), 수정 후 통과.
- 임시 결합 `479d23c8d136d20332cc4ed6f3df8f4df1210c3e`(worktree 제거함): 13개 시험 모듈 72건 rc=0. 자료 없음 건너뜀 6, 자료 읽기 전용 지정 건너뜀 0. 합성 fixture 2종 세 파일의 바이트 동일.
- 함수 수: 새 제품 파일 최대 6, 새 시험 파일 7 이하. `cross_review_auto_contract.py` 3→3.
- 미검증: 자동 검토 관련 19개 모듈 212건 중 80건은 Git 제외 `nemotron-review.json`이 없어 `FileNotFoundError`(기준 `921d152`에서도 같은 목록). 통합 뒤 기본 checkout에서 돌려야 한다. 수정분 재리뷰, 실제 `./experiment`.
- 남긴 작은 지적: 0건 정확 상한, zone_rows 입력 SHA·미매칭 측정 건수, 사이드카 교차 검사(AI 의심 수·구역 이름·input_hold·band 이름).

## 6. T3 증거 보존 수정 (2026-11-28, §5의 rater_gate 항목과 다르면 이 절이 우선)

사용자 지시(2026-11-28)로 재리뷰 3건을 수정했다. T3 tip `4a2ecc8ac946427f41ea7e42449812958a7d8cd3`, 변경 `tools/rater_gate.py`와 새 시험 `tests/test_rater_gate_evidence.py`.

- AI 파일: 주석·빈 줄 말고 못 읽은 줄은 번호를 기록하고 읽힌 구역은 대조한다. 값이 충돌한 구역은 뺀다. `.log` 밖의 파일에 못 읽은 것이 있으면 `comparison_complete=false`, `incomplete`에 사유를 남기고 `no_match_found`를 내지 않는다. `ai_identical`·`ai_suspect` 우선순위는 그대로다.
- 점 파일도 읽는다. 판정 줄이 없는 `.DS_Store`·`._*`만 `excluded_files`에 사유와 함께 제외한다. 에디터 임시·백업 파일은 읽히면 대조하고, 못 읽으면 불완전으로 본다.
- 겹침 0도 `comparisons`에 남긴다. 파일마다 `answer_total`, `screen`(same|other|unknown), `unread_lines`를 남긴다.
- 답·AI 파일은 BOM을 처리한다. 값 안의 둘째 구역 대입(`z숫자` 뒤 `=`·`:`, 전각 포함), 전각 구역 번호, `:`가 없거나 값이 빈 휴대폰 구역, `- `가 붙은 휴대폰 줄을 거절한다.
- 원문 붙여넣기(예외 문법 추가 없음): 원문은 그대로 두고, `<pasted_content>` 블록 하나의 본문을 그대로 옮기고 첫 줄에 `# 원문sha256=<원문 SHA-256>`을 붙인 사본을 판정한다. 확인 문장은 `--statement` 파일로 준다. 원문에 `# 화면=` 줄이 없으면 만들어 넣지 않는다(`screen=unknown`). 블록 밖의 판정 줄(stage1 원문의 첫 화면, `미판정` 포함)은 이 절차의 대상이 아니다.

검증:
- 새 시험을 수정 전 `8da1a73`에서 실행: 실패 16, 오류 7. 수정 후 T3 시험 14건 통과.
- 실데이터: 답 폴더 파일 20개의 수정 전후 판정·구역 수·대조 결과가 같다(판정 7, 거절 13). 추출 사본은 screen1 1블록, stage1 4블록 모두 `ai_identical` 64(각 사본 본문과 원문 블록 동일, stage1 4블록 값은 `input-2`~`5`와 같음). 원본 해시 불변.
- 임시 통합 `0662421`(복제본): 기록 도구 시험 77건 통과(실데이터 읽기 전용). 전체 시험 main `ceed731` 1374건·통합 1419건, 둘 다 실패 1·오류 138이고 실패 ID 목록 동일. 건너뜀 5→11. 대표 원인은 Git 제외 `nemotron-review.json` 없음 101줄, `confounder_head` 없음 13줄.
- 함수 수: `rater_gate.py` 6, 새 시험 7. 호출 깊이 `main→compare→values→line_pairs` 3.

남은 틈과 결정 대기(정책·통계는 바꾸지 않음):
- 줄을 지우거나 일부를 `#`로 막은 일부 사본은 정상 일부 파일과 구분할 수 없어 차단하지 않는다.
- 화면 표기가 없는 무관한 전체 파일도 `no_match_found`의 "같은 화면" 조건을 채운다(`screen=unknown`으로 기록만 함).
- 복사본이 `.log`면 차단하지 않는다. 화면별 허용 값·필수 구역 정의가 없어 `z1=a z2 b` 같은 값과 구역 누락은 검사하지 않는다.
- 일부 구역 일치로는 판정하지 않는다. Wilson 상한은 구역 독립을 가정하고 AI 파일 여러 개와의 반복 비교를 보정하지 않는다.
- 불완전 사유는 provenance 파일에만 있다. `zone_rows`는 `no_match_found`를 `unknown`으로 바꾸고 사유를 행에 옮기지 않는다.

## 7. T3 독립 리뷰와 3건 수정 (2026-11-28, §6과 다르면 이 절이 우선)

리뷰: 하위 에이전트 1명, 대상 `8da1a73..4a2ecc8`. Critical 0, Important 3, 구현 세션이 3건 모두 재현. 사용자 "3건 수정". 수정 후 T3 tip `eebaf4f0e32a9d9a75068d1547e05b5f7887ded4`.

- 휴대폰 AI 줄: 못 읽은 구역은 키를 남기고 값 없음(일치로 세지 않음)으로 둔다. 나머지 구역은 대조한다. 일치 수 k는 하한이 되며 파일은 불완전으로 기록한다. 판정 식·기준선은 그대로다.
- AI 폴더의 폴더 링크(따라가지 않음), 깨진 링크, 일반 파일이 아닌 항목, 읽기 권한이 없는 폴더·파일을 `incomplete`에 사유와 함께 남긴다. 잠긴 파일 하나로 전체가 거절되지 않는다. 깨진 기본 AI 폴더 링크도 포함한다.
- 두 카드가 한 줄에 붙으면 답은 거절한다. AI 파일은 둘째 카드가 시작되는 지점부터 첫 카드에 판정을 붙이지 않는다.

검증: 새 시험 `tests/test_rater_gate_review.py` 4개는 `4a2ecc8`에서 실패(하위 사례 12), 수정 후 T3 18건 통과. 실데이터 답 폴더 파일 20개는 `8da1a73` 대비 결과 동일, 추출 사본 5개 동일, 원본 해시 불변. 임시 통합 `ad1e1df`: 기록 도구 81건 rc=0, 전체 시험 main 1374건·통합 1423건 모두 rc=1(실패 1·오류 138, ID 목록 동일). 함수 수 `rater_gate.py` 7(상한), 새 시험 6.

미수정(리뷰 작은 지적): 해독 안 되는 `._*` 사본이 OS 파일로 제외됨, 사유 문장의 `Z4:`가 거절됨, 빈 `.gitkeep`이 차단, `# 원문sha256=` 사본·BOM 답을 `zone_rows`가 읽는지 미확인, `.log` 사본 예외. 이번 3건 수정분의 독립 리뷰는 하지 않았다.

## 8. T3 조합표 수정 (2026-11-28, §6·§7과 다르면 이 절이 우선)

확인 리뷰(`4a2ecc8..eebaf4f`, Critical 1·Important 1, 구현 세션 재현) 뒤 사용자 "조합표 만들고 수정". T3 tip `33c1e569389bb1403b79f306ed2788acc6b85296`.

- 해석부를 `tools/rater_gate_lines.py`(`line_pairs`, `values`)로 분리. 함수 수 `rater_gate.py` 5, `rater_gate_lines.py` 2.
- AI 파일의 구역별 우선순위: 온전한 줄의 값이 우선. 깨진 줄은 온전한 줄에 없는 구역만 채운다. 결정하는 쪽의 값이 둘 이상 다르면 그 구역을 뺀다(온전한 줄끼리 충돌한 구역은 깨진 줄로 다시 채우지 않는다). 아무도 못 읽은 구역은 값 없음: 충돌 아님, 일치 아님.
- `no_match_found`의 비교 근거는 같은 화면 조건의 전체 포함 파일 중 못 읽은 구역이 0(`unread_zones`)인 것만. `ai_identical`·`ai_suspect` 식은 그대로.
- 구역 이름 오타(`=`·`:` 포함)는 그 구역만 버린다. 둘째 카드(`/front=`·`/back=`, 둘째 `box`)부터는 붙이지 않는다. `box` 칸에 둘째 카드가 붙은 줄은 통째로 못 읽음(답은 거절).
- 알려진 한계: 사본이 깨진 줄에만 있고 온전한 줄의 값이 다르면 온전한 줄이 이긴다(그 파일은 불완전으로 기록, `.log`는 차단 안 함).

검증: 조합표 `tests/test_rater_gate_table.py`(줄 조합 21개 × .txt·.log, 근거 사례 5, 부분 손상 4, 답 거절 6)는 `eebaf4f`에서 실패 28, 수정 후 T3 22건 통과(기대값 변경 없음). 한 글자 변형 줄 2318개를 정상 줄 앞뒤에 둔 4636조합: 예외 0, 깨진 줄이 정상 줄 증거를 바꾼 경우 0. 실데이터 답 폴더 파일 20개는 `8da1a73` 대비 동일, 추출 사본 5개 동일, 원본 해시 불변. 임시 통합 `a7b482c`(기준 main `699dcde`): 병합 충돌 없음, 기록 도구 85건 rc=0, 전체 시험 main 1374·통합 1427 모두 rc=1(실패 1·오류 138, ID 목록 동일).

미수정 작은 지적: 해독 안 되는 `._*` 사본 제외, 답 사유 문장의 `Z4:` 거절, 빈 `.gitkeep` 차단, `zone_rows`의 추출 사본·BOM 읽기 미확인, `.log` 예외, 면 이름이 front/back이 아닌 둘째 카드, 일반 파일인 기본 `ai-reference`. §8 수정분의 독립 리뷰는 하지 않았다.

## 9. T3 마지막 리뷰 (2026-11-28, §6의 원문 붙여넣기 절차와 다르면 이 절이 우선)

대상 `eebaf4f..33c1e56`(누적 `8da1a73..33c1e56`). Critical 0, 이번 diff의 고쳐야 할 회귀 0, 기존 문제 Important 2. 구현 세션 재현. 코드는 바꾸지 않았다.

- I-1: 휴대폰 형식 AI 사본에 줄 앞 `* `·`1. `·`답: `, `;` 뒤 공백, ID 대소문자 변경이 있으면 겹침 0·완전 읽음으로 `no_match_found`(`8da1a73`도 `no_match_found`). 값 뒤 공백은 1/9로 `no_match_found`. 저장된 AI 폴더에서 휴대폰 형식 파일은 0개. **휴대폰 형식의 `no_match_found`는 "사본 아님"의 근거가 아니다.**
- I-2: `zone_rows`는 `ai_identical`만 행에서 뺀다. `comparison_complete`·`incomplete`는 읽지 않고 `--provenance`는 선택 인자다(코드 대조, 리뷰어 합성 실행). 불완전한 `unknown`의 행 처리는 사용자 결정(D-7 계열).
- 정정: §6의 `# 원문sha256=` 추출본은 관문만 통과하고 `zone_rows.parse`는 `#` 줄을 거절한다. T1과 계약을 맞추기 전에는 이 추출본을 행 변환에 쓰지 않는다.

## 10. 남은 한계 2건의 원인과 극복 (2026-11-28, §6~§9와 다르면 이 절이 우선)

적용: Superpowers systematic-debugging(원인 → 단일 가설 → 실패 시험 → 한 가지 수정), TDD(판정 무결성 로직), verification-before-completion. 하위 리뷰는 부르지 않음.

### 원인
- 해석기가 `=` 앞의 아무 문자열이나 ID·구역 이름으로 받아들였다. 접두어·공백·대문자가 이름의 일부가 되어 `unread=[]`, 겹치는 구역 0개의 "완전히 읽은 무관한 파일"이 됐다. "읽음"을 "답과 대조됨"으로 취급한 것이 원인이다.
- T3 수정이 세 번 넘게 새 틈을 냈으므로(§6~§8) 해석기에 허용·거부 형식을 더 늘리지 않았다.

### 수정
- T3 `776c217`: `rater_gate_lines.unmatched`(비교용 정규화: NFKC·대소문자·글자/숫자만). 답의 카드 `id/side`를 적었으나 그대로 시작하지 않는 줄, 또는 정규화해야만 답과 같아지는 구역 이름·값이 있으면 incomplete에 적는다. `.log` 예외는 그대로. 값·일치 수·기록·`ai_identical`·`ai_suspect`는 바꾸지 않는다. 달라질 수 있는 판정은 `no_match_found → unknown`뿐이다.
- T1 `d8f8dcd`: `zone_rows`가 `#` 줄을 주석으로, 답을 utf-8-sig로 읽는다(§9의 정정 해소). `comparison_complete`가 true로 기록되지 않으면 경고를 출력한다. 행은 빼지 않는다.

### 외부 방식과 접목
| 방식 | 출처 | 접목 |
|---|---|---|
| 전부 인식한 뒤 처리, 관대한 수용 경계 | LangSec, RFC 9413 | 적용: 대조되지 않은 지시를 "완전"으로 보지 않음 |
| 복사 탐지의 공백·대소문자·구두점 무시 | Schleimer·Wilkerson·Aiken, winnowing (SIGMOD 2003) | 적용: 탐지 전용 정규화. k-gram 지문은 표본·문턱이 새로 필요해 보류 |
| 변형 관계 시험 | Segura 외, metamorphic testing 설문(TSE 2016) | 적용: "형태를 지키는 잡음은 일치 없음을 만들지 못한다" |
| 사후 추정보다 생성·수집 시점 증거 | 키 입력·붙여넣기 기록 연구, SLSA 검증 증명 | 미적용: 새 입력 화면(T4)·정책 결정 필요 |
| 불완전한 검증을 통과로 쓰지 않는 소비 단계 | 설계 원칙(위 출처가 직접 증명한 것은 아님) | 일부: 경고만. 행 제외·차단은 D-7 계열 사용자 결정 |

조사는 검색 결과 요약 수준이며 원문 전체는 읽지 않았다. 특정 전문가가 이 문제를 이렇게 풀었다는 근거는 없고, 공개된 원칙을 옮긴 것이다.

### 검증
- 새 시험 `tests/test_rater_gate_unmatched.py` 4건(수정 전 10개 하위 실패), `tests/test_zone_rows_contract.py` 3건(수정 전 실패 3·오류 1). T3 26건·T1 15건(건너뜀 1) rc=0.
- 기본 checkout 읽기 전용: 답 20건 결과가 `33c1e56`과 같음, 원본 해시 전후 동일. 파싱되는 답 7건·대조 63쌍에서 새 거부 0건. 저장 자료에는 휴대폰 형식 AI 파일이 없어 그 형식의 거짓 거부는 실자료 미검증.
- 무작위 2~4글자 변형 6,000건(seed 20261128): 일치 없음 2,957 → 173, 그 밖의 판정 변화 0, 비교 기록 변화 0, 예외 0, 형태 보존 변형의 일치 없음 0.
- main `699dcde`에 다섯 브랜치 임시 병합(`9a998fa`, 제거): 충돌 0, `PYTHONPATH=tests:.`로 60건 + 32건 rc=0. 경로 설정 없이 한 실행은 가져오기 오류 4건(rc=1). 전체 suite는 이번에 다시 돌리지 않음.
- 함수 수: rater_gate 5, rater_gate_lines 4, zone_rows 5, 새 시험 ≤7. 호출 깊이 ≤4.

### 남는 한계
- 카드 ID를 지우거나 글자를 바꾼 사본, 화면 캡처, 번호 형식에서 값·구역 번호를 고쳐 쓴 사본은 텍스트로 알 수 없다. `no_match_found`는 여전히 사람 증명이 아니다.
- 같은 카드를 언급만 한 정상 AI 메모(`.log` 아님)는 `unknown`을 만든다(의도한 보수 방향).
- 한계 2의 행 제외 여부는 미결정.

롤백: T3 `git revert 776c217`, T1 `git revert d8f8dcd`. status = ready_for_review, 미통합·미push.

## 11. 사용자 결정 D3 반영 (2026-11-28)
- 결정: 결과 파일에 "AI 판정과 일치하는 기록을 찾지 못했다는 사실은 사람이 직접 판정했다는 증거가 아니다."를 원문 그대로 명시한다. 탐지 실패를 사람 판정으로 승격하지 않고, 불완전 대조 행을 분모에서 임의 제외하지 않으며, 새 탐지 체계는 만들지 않는다.
- 변경: `tools/rater_gate.py` 결과 JSON에 고정 필드 `notice`·`limitation`(AI 사본 변형 미탐지), `tools/zone_rows.py`의 `exclusions.json`에 같은 두 필드. 판정 로직·제외 규칙·기존 필드 불변. 새 시험 `tests/test_rater_gate_notice.py` 2건.
- 시험: 관련 시험 54건 rc=0(건너뜀 5). 문구를 바꾸는 결함 주입 시 2건 실패(rc=1). 로그 `scratchpad/logs/d3-rec-312.log`.
- 롤백: 이 절의 커밋 `git revert`. 미통합·미push.
