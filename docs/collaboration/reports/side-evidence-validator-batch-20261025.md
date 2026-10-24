# 면 근거 sidecar 검증기 — 2026-10-25

task `side-evidence-validator-batch-20261025`. 기준은 base `357891e1435076378a85b695c7027c9769d871b0`이고 시작 HEAD는 `7e61e150696432e83c730899e8e889185552ae4a`이다. 이 검증기는 sidecar의 구조와 파일 일치를 검사하는 독립·선택 실행 도구다. 사람 의미, 판단의 독립성, 면 정답은 보증하지 않는다. 운영·A3·primary·수량 경로에 연결하지 않았다. 학습·추론·사진 열람·외부 AI 호출은 0회이며 진척률 30/100은 그대로다.

## 1. v0.1 기술 계약

직전 초안(`docs/collaboration/reports/side-evidence-contract-20261025.md`, Codex 보정 포함)은 보존한다. 아래는 실행 가능한 최소 계약이다. 초안 예시는 합성이며, 초안 schema(`v0-draft`)는 자동 변환하지 않고 거절한다.

### API와 CLI

- `card_condition.side_evidence.validate_sidecar(sidecar_path, evidence_root) -> dict`
  - 수용하면 JSON 직렬화 가능한 검증 보고 dict를 반환한다.
  - 외부 입력이 계약을 어기면 `ValueError`를 낸다. 메시지는 규칙 코드(예: `R1:`)로 시작한다.
  - 읽기 권한 등 파일 시스템 오류는 `OSError`를 그대로 낸다.
  - 코드 결함을 성공으로 숨기지 않는다.
- `.venv/bin/python -m card_condition.side_evidence_cli --sidecar INPUT --evidence-root ROOT --output NEW_JSON`
  - 기존 `card-condition` CLI에 연결하지 않는다.
  - 출력은 새 파일만 만든다. 기존 파일은 덮어쓰지 않는다.
  - 종료코드: 0 수용 / 1 sidecar 거절(`ValueError`) / 2 명령행 사용 오류 / 3 파일 시스템 오류(출력 파일 이미 있음 포함).
  - stderr에는 한 줄만 쓴다.

### sidecar v0.1

```json
{
  "schema": "side_evidence_sidecar/v0.1",
  "inventory": {"path": "inventory.json", "sha256": "<64 hex>", "rows_pointer": "/latest_supplements"},
  "search_scope": {"path": "index.json", "sha256": "<64 hex>"},
  "rows": [
    {
      "row_id": "<inventory row id>",
      "image_sha256": "<inventory row image_sha256>",
      "side_claim": "front",
      "review": {"status": "reviewed"},
      "evidence": [
        {"type": "human_statement", "claim": "side", "value": "back", "asserts_side": true,
         "source": {"path": "derived.jsonl", "sha256": "<64 hex>", "row_id": "<jsonl id>", "pointer": "/human_evidence/user_quote"},
         "origin": {"path": "response.json", "sha256": "<64 hex>", "row_id": null, "pointer": "/user_quote"},
         "note": "optional string"}
      ],
      "missing_sources": [
        {"path": "absent/human-response.json",
         "referenced_by": {"path": "pending.json", "sha256": "<64 hex>", "row_id": null, "pointer": "/human_response"}}
      ],
      "searched_no_side_evidence": false,
      "summary": {"human_side_origins": 1, "side_basis": "human_statement_conflicts_claim"}
    }
  ]
}
```

위 블록은 필드 형태 설명이며 `<64 hex>`는 자리표시다. 실행 가능한 fixture는 테스트가 실제 파일 바이트의 SHA로 만든다.

### 규칙

**파일 읽기**
- 모든 `path`는 `evidence_root` 기준 상대경로다.
- 다음은 거절한다(규칙 코드 `P`):
  - 빈 문자열, 절대경로, `..` 구성요소, 역슬래시
  - 정규형이 아닌 표기(`a/./b`, `./b`, `a//b`, `a/b/`). 같은 위치를 다른 표기로 써서 origin을 부풀릴 수 없게 한다(5단계 반례로 추가)
  - realpath가 root 밖으로 나가는 경우(root 밖으로 빠지는 symlink 포함)
  - 일반 파일이 아닌 대상(디렉터리, FIFO 등)
- 각 파일은 한 번 읽은 바이트로 SHA256과 파싱을 함께 수행한다. 경로를 셸이나 네트워크에 넘기지 않는다.
- 적대적인 동시 파일 교체까지 막는다고 주장하지 않는다.

**파싱**
- `.json`과 `.jsonl`만 지원한다. 그 밖의 형식은 거절한다.
- UTF-8로 읽는다. 중복 키, `NaN`·`Infinity`, 너무 깊은 중첩(`RecursionError`)은 `J`로 거절한다(깊은 중첩은 5단계 반례로 추가).
- JSONL은 빈 줄이 아닌 각 줄이 객체여야 하고, 문자열 `id`가 있어야 하며, 파일 안에서 유일해야 한다.

**참조(Ref)** `{"path", "sha256", "row_id", "pointer"}`
- `.json`이면 `row_id`는 null이고, pointer를 문서 루트에 적용한다.
- `.jsonl`이면 `row_id`는 필수 문자열이다. 그 `id`를 가진 행을 고른 뒤 pointer를 적용한다.
- pointer는 RFC 6901을 따른다.
  - `~1`은 `/`, `~0`은 `~`다. 그 밖의 `~` 조합은 오류다.
  - 배열 인덱스는 `0` 또는 앞자리 0이 없는 10진수만 허용한다. `-`는 거절한다.
  - 빈 pointer `""`는 루트를 선택한다. 다만 근거(source/origin/referenced_by) 참조에서는 빈 pointer를 거절한다. 특정 값을 가리켜야 하기 때문이다.
- 근거 참조가 가리키는 값이 JSON `null`이면 "참조 값 없음"으로 거절한다.

**inventory**
- `.json`만 허용한다. `rows_pointer`로 고른 값은 객체 배열이어야 한다(빈 pointer는 루트 배열).
- 행 식별은 inventory 행의 `id`(문자열, 유일)로 한다.
- 대조 필드:
  - `image_sha256`: inventory 행의 같은 이름 필드. `decoded_sha256`과 혼용하지 않는다.
  - `side`: 없으면 null. 있으면 `front`, `back`, null 중 하나.
- inventory 전체 행을 sidecar에 넣도록 강제하지 않는다.

**구조**
- 모든 객체는 정의된 키만 허용한다.
  - 행에 `side`·`target`·`box`·`point` 같은 정답 필드가 있으면 거절한다(R6).
  - `decoded_sha256` 같은 미정의 키도 거절한다.
- 타입 검사:
  - bool은 `type(x) is bool`로 검사한다.
  - 정수는 bool을 정수로 받지 않는다.
  - SHA는 소문자 64자리 hex만 허용한다.
- 근거 `type`과 `asserts_side`는 고정 대응이다.
  - `human_statement` → true
  - `codex_anchor_eligibility` → true
  - `review_slot` → false(R7)
- `claim`은 `side`만 허용한다(R6). `value`는 `front`나 `back`이다.
- `note`는 선택 문자열이며 의미를 해석하지 않는다.

**조사 상태**
- `not_reviewed` 행: `evidence`·`missing_sources`가 비어 있고 `searched_no_side_evidence`가 false여야 한다(R4).
- `reviewed` 행: 셋 중 하나 이상이 있어야 한다(R5).
- `searched_no_side_evidence: true`인 행에는 면을 주장하는 근거(`asserts_side: true`)가 없어야 한다(S1).
- 어떤 행이라도 `searched_no_side_evidence: true`이면 `search_scope`가 필요하다(S2).

**누락 원본**
- `missing_sources[].path`는 안전한 정규형 상대경로여야 한다.
- `referenced_by`는 근거 참조와 같은 방식으로 SHA와 pointer를 검사한다(R10). 그 값은 문자열이어야 한다.
- 참조 값의 후보 경로:
  - 상대경로 문자열이면 그 문자열 하나.
  - `/`로 시작하는 과거 절대경로 문자열이면, 구성요소 경계에서 자른 모든 접미 경로. 그 경로를 따라가 root 밖을 읽지는 않는다.
- 누락 경로는 후보 중 하나여야 한다(R10).
- 후보 중 하나라도 root 아래에 있으면 거절한다(R10). 짧은 접미로 바꿔 써서 실제로 있는 원본을 누락으로 위장할 수 없다(5단계 반례로 강화).
- 누락 원본은 `summary`에 근거로 세지 않는다.

**요약 재계산**(R8)
- `human_side_origins`: `human_statement` 항목의 서로 다른 origin `(path, sha256, row_id, pointer)` 수. 선언된 원본 위치의 중복을 제거한 수일 뿐이며 독립된 사람 판단 수가 아니다.
- 파일 대조 단계에서는 origin 경로를 realpath로 바꿔 다시 센다. root 안 symlink 별칭으로 같은 파일을 두 번 세면 R8로 거절한다(5단계 반례로 추가).
- `side_basis`:
  - `not_reviewed`
  - `no_human_statement`
  - `human_statements_disagree`: 사람 진술 값이 둘 이상
  - `human_statement_without_claim`: `side_claim`이 null
  - `human_statement_matches_claim`
  - `human_statement_conflicts_claim`
- 충돌·복수 진술은 거절 사유가 아니다. 보고만 하고 면을 고르지 않는다.

**SHA·결합**
- inventory SHA 불일치 → R1.
- 행이 inventory에 없거나, `image_sha256`·`side_claim`이 불일치 → R2.
- sidecar 행 중복 → R3. inventory id 중복 → R2.
- source·origin의 SHA 불일치, 파일 없음, 참조 값 없음 → R9.
- `search_scope` SHA 불일치 → R11.
- 미지원 schema·type·status·side_basis → R12.

**출력**(`side_evidence_validation/v0.1`)
- 담는 것: sidecar 파일 SHA, inventory·search_scope의 상대경로·SHA, 행별 상태·유형·요약, `semantic_verification: false`, `modifies_sources: false`, 결정하지 않은 항목 목록.
- 담지 않는 것: 참조 값(사람 답변 원문), 절대경로, 비밀값.

### 초안 대비 변경과 이유

| 초안 | v0.1 | 이유 |
|---|---|---|
| `schema: v0-draft` | `v0.1`, 초안 자동 변환 없음 | 초안 예시는 실행 가능한 원본이 아니다 |
| Ref `row_id` 항상 있음 | JSON은 null, JSONL은 필수 | 계약의 JSON/JSONL 참조 방식에 맞춤 |
| `asserts_side` 자유값 | 유형별 고정 | 슬롯은 면을 주장하지 않는다. 사람 진술이 면을 주장하지 않으면 면 근거가 아니다 |
| pointer 형식 미정 | RFC 6901, 근거 참조는 비어 있지 않은 pointer·non-null 값 | 초안 미해결 2의 실행 가능한 부분만 확정. 사진별 대응은 여전히 미해결 |
| `searched_no_side_evidence`와 근거 관계 미정 | 면 주장 근거와 공존 금지(S1), `search_scope` 필수(S2) | "찾지 못함"과 근거가 동시에 참일 수 없다 |
| R10 대조 방식 미정 | 상대 문자열은 동일 일치, 절대 문자열은 경계 접미 후보. 모든 후보가 root 아래에 없어야 함 | 과거 절대경로 문자열을 따라가지 않고 대조하되, 짧은 접미로 위장하지 못하게 함 |
| R9 source만 | source·origin 모두(Codex 보정) | origin도 선언된 위치이므로 존재·SHA 확인 필요 |

### 오류 코드

| 코드 | 뜻 |
|---|---|
| `F` | 형식·타입·키 |
| `P` | 경로·파일 종류 |
| `J` | JSON/JSONL 파싱·pointer·참조 형식 |
| `S1`, `S2` | 검색 결과와 근거·탐색 범위의 관계 |
| `R1`–`R12` | 초안 표의 규칙 |

## 2. 구현 (단계별)

| 단계 | 커밋 | 내용 |
|---|---|---|
| 1 | `aa0c95093c60ff623d006e58d60dc12159945f4f` | 이 보고서 1절 v0.1 계약 고정, task status `implementing` |
| 2 | `f42aca44babab59b5f20afbee346a77429d0087c` | `card_condition/side_evidence.py` 구조·요약 검증(`check_structure`, `compute_summary`, RFC 6901 pointer), `tests/test_side_evidence.py` |
| 3 | `a3da1d84dece21f644f03f3d3ba39d42e926637e` | `validate_sidecar`와 파일 대조(경로 안전성, 한 번 읽기 SHA·파싱, JSON/JSONL 참조, R1·R2·R9–R11), `tests/test_side_evidence_sources.py` |
| 4 | `662c34850bef5d816d7eee2f04afd2a6b4be46f8` | `card_condition/side_evidence_cli.py` 독립 CLI(같은 폴더 임시 파일 → `fsync` → `os.link`로 덮어쓰기 없는 공개), `tests/test_side_evidence_cli.py` |
| 5a | `1bc6303d7d9b2d45c26ed78e96b1dc3b17d88128` | 자체 검토 반례 3건을 실패하는 검사로 먼저 커밋. 당시 실패 3·오류 1 |
| 5b | `b45349e15a8cac767133c08ad652669160a8de21` | 최소 수정: 정규형 경로, origin realpath 재계산(R8), 누락 후보 경로 전체 부재(R10), 깊은 중첩 `J` |
| 5c | 이 문서 커밋 | 최종 보고서와 task 기록, status `ready_for_review` |

기존 `cli.py`·`data_coverage.py`·`pyproject.toml`과 공용 CLI 연결은 변경하지 않았다. `data_coverage`의 저장 방식은 읽어서 같은 원리만 따랐다.

## 3. 합성 실행 예

`tests/test_side_evidence_sources.py`의 `Fixture`로 임시 폴더에 합성 근거 root와 sidecar를 만든 뒤 실행했다. 경로는 그 폴더 기준 상대경로다.

```text
$ python -m card_condition.side_evidence_cli --sidecar sidecar.json --evidence-root evidence --output report.json
side-evidence: accepted 3 rows                                   (exit 0)
$ (같은 명령 반복)
side-evidence: file error: FileExistsError: output already exists; choose a new path   (exit 3)
$ (index.json 내용 변경 후 새 출력 경로로 실행)
side-evidence: rejected: R11: search_scope.sha256 does not match the index file        (exit 1)
```

첫 실행 출력 일부(행 2개만 발췌):

```json
{
 "schema": "side_evidence_validation/v0.1",
 "inventory": {"path": "inventory.json", "rows_pointer": "/latest", "rows_total": 3, "rows_described": 3},
 "search_scope": {"path": "index.json", "completeness_verified": false},
 "semantic_verification": false,
 "modifies_sources": false,
 "origin_count_meaning": "distinct declared origin locations; not independent human judgments",
 "side_basis_counts": {"human_statement_without_claim": 1, "no_human_statement": 1, "not_reviewed": 1},
 "rows": [
  {"row_id": "syn/photo-3", "side_claim": "front", "review_status": "reviewed", "evidence_types": ["review_slot"], "evidence_items": 1, "missing_sources": 1, "searched_no_side_evidence": false, "human_side_origins": 0, "side_basis": "no_human_statement"},
  {"row_id": "syn/photo-4", "side_claim": null, "review_status": "reviewed", "evidence_types": ["codex_anchor_eligibility", "human_statement"], "evidence_items": 2, "missing_sources": 0, "searched_no_side_evidence": false, "human_side_origins": 1, "side_basis": "human_statement_without_claim"}
 ],
 "not_decided": ["side conflict resolution", "A3, primary and quantity policy", "mapping one reply to several photos", "sources outside evidence_root"]
}
```

발췌에서 `sidecar_sha256`·`sha256` 값과 세 번째 행은 생략했다. 실제 출력에는 들어 있다. 출력에는 참조 값(합성 진술 문장), 임시 폴더의 절대경로가 없다(`test_a1_valid_sidecar_reports_without_touching_any_file`, `test_writes_new_report_and_preserves_inputs`에서 검사).

## 4. 사례별 검사

모든 사례는 임시 디렉터리의 실제 합성 파일 바이트와 SHA로 실행한다. 원본 데이터·사진·라벨은 사용하지 않는다.

| 사례 | 검사(파일::이름) | 결과 |
|---|---|---|
| A1 정상 수용·입력 보존 | sources::`test_a1_valid_sidecar_reports_without_touching_any_file`, cli::`test_writes_new_report_and_preserves_inputs` | 통과 |
| A2 파생 사본 → origin 1 | sources::`test_a2_derived_copy_counts_one_declared_origin`, structure::`test_derived_copy_keeps_one_declared_origin` | 통과 |
| A3 유형 공존 | sources::`test_a3_human_statement_and_anchor_coexist`, structure::`test_mixed_types_are_not_exclusive` | 통과 |
| R1 inventory 버전·pointer·파일 없음 | sources::`test_r1_inventory_version_mismatch` | 통과 |
| R2 행 없음·다른 이미지·다른 면·inventory id 중복 | sources::`test_r2_rows_must_bind_to_the_same_inventory_row`, `test_inventory_rows_need_ids_and_valid_sides` | 통과 |
| R3 sidecar 행 중복 | structure::`test_duplicate_rows_rejected`, sources::`test_structure_rules_also_hold_end_to_end` | 통과 |
| R4 미조사 행에 결과 기록(3종) | structure::`test_not_reviewed_is_separate_from_missing_and_empty_search` | 통과 |
| R5 조사했는데 결과 없음 | 위와 같음, end-to-end | 통과 |
| R6 정답 필드·비면 claim | structure::`test_truth_and_non_side_claims_rejected` | 통과 |
| R7 슬롯의 면 주장 | structure::`test_review_slot_cannot_assert_side` | 통과 |
| R8 요약 불일치·파생 사본 2회 계산·symlink 별칭 | structure::`test_derived_copy_keeps_one_declared_origin`, sources::`test_origin_spellings_and_aliases_cannot_inflate_origin_count` | 통과 |
| R9 source SHA, source는 맞고 origin만 틀림, origin pointer 누락, 파일 없음, JSONL id 없음, null 값 | sources::`test_r9_source_and_origin_are_both_verified`, `test_pointer_escapes_and_indexes_on_files` | 통과 |
| R10 참조 안 된 경로, 비문자열 값, 참조 SHA 불일치, 존재하는 원본을 누락 선언, 짧은 접미 위장 | sources::`test_r10_missing_sources_must_be_referenced_and_absent`, `test_shorter_missing_path_cannot_hide_a_present_source`, `test_missing_sources_never_count_as_evidence` | 통과 |
| R11 stale·없는 index | sources::`test_r11_stale_or_missing_search_index` | 통과 |
| R12 초안 schema·미지원 type·status·basis | structure::`test_unsupported_schema_type_status_and_basis` | 통과 |
| S1·S2 | structure::`test_empty_search_needs_scope_and_no_asserting_evidence` | 통과 |
| `..`·절대경로·root 밖 symlink(파일·디렉터리)·특수 파일 | sources::`test_paths_cannot_leave_the_root`, `test_special_files_are_not_read`, structure::`test_reference_forms` | 통과 |
| root 안 symlink 허용 | sources::`test_symlink_inside_the_root_is_followed` | 통과 |
| pointer `~0`/`~1`, 배열 인덱스, `-`, 앞자리 0, 빈 pointer | structure::`test_json_pointer_tokens`, sources::`test_pointer_escapes_and_indexes_on_files` | 통과 |
| JSONL 중복·id 없음, 잘못된 JSON, 중복 키, NaN, 비 UTF-8, 깊은 중첩, U+2028 | sources::`test_malformed_reference_files`, `test_deeply_nested_json_is_a_clean_rejection`, `test_jsonl_line_separator_inside_string_is_one_row` | 통과 |
| bool/int 혼동, null·빈 값, 미정의 키 | structure::`test_strict_types_do_not_confuse_bool_and_int`, `test_null_empty_and_bad_values`, `test_unknown_keys_rejected` | 통과 |
| SHA 일치 ≠ 의미 검증 | sources::`test_matching_sha_is_not_semantic_verification` | 통과(면과 무관한 값·사람이 아닌 origin도 수용됨을 고정) |
| CLI 종료코드·stderr 한 줄 | cli::`test_rejected_sidecar_exits_1_without_output`, `test_usage_error_exits_2`, `test_module_entry_point` | 통과 |
| 기존 출력·경쟁 출력 보존 | cli::`test_existing_output_is_never_replaced`, `test_competing_output_created_during_validation_is_preserved` | 통과 |
| 부분 쓰기 실패 후 파일 없음·재시도, hardlink 미지원 | cli::`test_partial_write_failure_leaves_no_file_and_can_retry`, `test_unsupported_hard_link_publishes_nothing`, `test_missing_output_folder_or_root_are_file_errors` | 통과 |

## 5. 자체 반례 검토

**재현된 결함 3건.** 모두 먼저 실패하는 검사로 커밋(`1bc6303`)한 뒤 최소 수정(`b45349e`)했다.
1. 같은 origin 파일을 `intake/./reply.json`처럼 다른 표기로 쓰거나 root 안 symlink 별칭으로 쓰면, 서로 다른 origin 2개로 수용됐다. 수정: 정규형이 아닌 경로를 `P`로 거절하고, 파일 대조 단계에서 origin realpath로 다시 세어 다르면 R8로 거절한다.
2. 참조 값보다 짧은 접미 경로(`legacy.json`)를 누락으로 선언하면, root 아래에 실제로 있는 원본(`artifacts/absent/legacy.json`)을 누락으로 통과시켰다. 상대 참조 값도 끝부분만 맞으면 수용됐다. 수정: 상대 값은 동일 일치만 허용하고, 절대 값의 모든 접미 후보가 root 아래에 없어야 한다.
3. 깊게 중첩된 JSON이 `RecursionError`로 빠져나가 간결한 거절이 아니었다. 수정: `J`로 거절한다.

**mutation 대조.** 임시 복사본에서 구현을 일부러 약하게 바꾼 14가지를 돌렸다. worktree는 변경하지 않았다. 14가지 모두 기존 검사가 실패를 냈고, 살아남은 변형은 0개다.
- origin 파일 검사 생략
- root 포함 검사 제거
- JSONL을 `splitlines`로 분할
- source로 origin 계산
- S1 제거
- R10 존재 검사 제거
- bool을 int로 허용
- 빈 근거 pointer 허용
- null 값 허용
- inventory 면 결합 생략
- search_scope SHA 생략
- 별칭 위치 검사 생략
- 정규형 경로 검사 생략
- CLI를 덮어쓰기 공개로 변경

**재현하지 못했거나 범위 밖으로 남긴 것**
- 적대적 동시 파일 교체(TOCTOU): 검사와 open 사이의 교체는 막지 않는다.
- 바이트가 같은 서로 다른 파일 두 개를 origin으로 쓰는 경우: 위치가 다르므로 2로 센다. 독립성을 판별할 수 없다.
- 거짓 origin(사람이 아닌 파일): 수용된다. 의미 검증을 하지 않는다는 경계를 테스트로 고정했다.

## 6. 의미 경계 (구현하지 않음)

- `semantic_verification: false`로 고정한다.
  - 검증기는 참조 값이 실제로 면을 말하는지, 사람이 쓴 것인지, 해당 사진을 가리키는지 확인하지 않는다.
  - 텍스트에서 면 진술을 추출하지 않는다.
  - Markdown은 지원하지 않는다.
- `human_side_origins`는 선언된 origin 위치의 중복 제거 수다. 통계적·인간적 독립성을 테스트로 입증했다고 주장하지 않는다.
- `search_scope`는 SHA만 확인한다. 검색이 완전했다는 증명이 아니다(`completeness_verified: false`).
- 충돌·복수 진술은 보고만 하고 면을 고르지 않는다. A3·primary·수량 판정 경로에 연결하지 않았다. 충돌 해결과 A3 정책은 사람 결정으로 남긴다.
- 작성자 신원 인증, inventory 변경 시 자동 마이그레이션, 일괄 sidecar 생성은 하지 않는다.

## 7. 검사 결과

- `PYTHONPATH=tests .venv/bin/python -m unittest test_side_evidence test_side_evidence_sources test_side_evidence_cli -v` → 48개 통과(구조 16, 원본 대조 23, CLI 9), 종료코드 0
- `.venv/bin/python -m compileall -q card_condition/side_evidence.py card_condition/side_evidence_cli.py` → 종료코드 0
- `git diff --check` → 통과
- base 이후 변경 파일: allowed_files 7개와 Codex 배정 커밋의 prompt·task 문서. 홈 절대경로·비밀값 없음.
- 가상환경: 이 worktree의 `.venv`. `card_condition.__file__`가 이 worktree를 가리킨다. torch는 설치돼 있지 않으며 필요하지 않다.
- 미실행:
  - 기존 ML 의존 테스트 55개(Codex 통합 후 실행 몫. 이 환경에는 torch가 없다)
  - 실제 inventory·snapshot 대상 실행
  - 학습·추론·사진 열람·외부 AI 호출·`review --auto`

## 8. 미해결·리스크·롤백

- 미해결(사람·Codex 결정):
  - sidecar 저장 위치·작성자·버전 정책
  - 한 사람 응답이 여러 사진을 다룰 때 사진별 대응
  - anchor·slot을 evidence에서 context로 분리할지
  - 충돌을 경고로 둘지 A3 차단으로 둘지
  - snapshot 밖 원본 참조 정책
- 리스크:
  - 구조·파일 일치 검증일 뿐 사람 의미나 독립성의 보증이 아니다. 수용 결과를 면 확정·편입 승인으로 읽으면 안 된다.
  - hardlink를 지원하지 않는 파일 시스템에서는 저장이 실패한다(종료코드 3, 파일 없음).
  - 강제 종료 시 `.<이름>.*.tmp` 임시 파일이 남을 수 있다.
  - 동시 파일 교체는 막지 않는다.
- 롤백: 미통합이면 반영하지 않는다. 통합 후에는 위 커밋을 역순으로 revert한다. 새 파일만 추가했으므로 기존 동작에는 영향이 없다. 실제 데이터·모델·진척률 30/100은 바뀌지 않는다.


## 9. Codex 통합 검토

전달 8개 커밋을 지정 순서로 cherry-pick -x했다. dispatch 7e61e15 이후의 변경은 허용 파일 7개이며, base 대비 추가 prompt는 Codex 배정 커밋에서 온 것이다. Claude worktree는 인계 HEAD에서 깨끗함을 확인했다. 실제 사용 경계는 표준 라이브러리의 선택 실행 검증기이며 기존 공용 CLI/모델 경로에는 연결하지 않았다.

### 검토 중 재현·수정

기존 cache는 realpath만 키로 사용했다. 같은 실제 파일을 both.json과 alias.jsonl symlink로 읽으면 JSON 파싱 결과가 JSONL 행 색인처럼 재사용됐다. 예를 들어 {"slot":{"statement":"synthetic"}}는 JSONL에 필수인 id가 없는데도 row_id=slot 참조로 수용됐다. 역순에서는 JSONL 내부 행 색인이 JSON 문서처럼 노출됐다.

회귀 검사 test_alias_cannot_reuse_json_cache_as_jsonl가 수정 전에 실패했음을 cache-before.log로 보존했다. 파일 cache에 읽은 형식을 함께 기록해, 동일 realpath에 다른 형식을 적용하면 J로 거절한다. 하나의 파일에 동일 형식의 별칭을 쓰는 기존 지원은 유지한다. 수정 커밋은 바로 앞 fix(side-evidence) 커밋이다.

### 실행 검증

- 최초 main 통합: 신규 48 + 기존 55 = 103 tests 통과.
- 캐시 우회 수정 후: 신규 49 + 기존 55 = 104 tests 통과. 신규 회귀는 JSON→JSONL/JSONL→JSON 양방향을 검사한다.
- compileall, git diff --check 통과. Claude의 mutation 14개 실행은 이번에 재수행하지 않았으며 자체 재검증 수치로 사용하지 않는다.
- 실제 supplemental inventory의 latest_supplements 6행에 not_reviewed만 기록한 로컬 임시 sidecar로 독립 CLI 실행 성공. side/image SHA/행 결합을 확인했지만 사람 면 증거를 추가하지 않았다.
- 기존 snapshot index의 바이트 동일 복사본을 search_scope로 검사했다. index SHA 대조만 실행했으며 snapshot 본문/source/origin의 실제 의미/참조를 확인한 것은 아니다. 실제 source/origin claim 검사 0개, snapshot payload 파일 검사 0개. 검색 완전성은 미확인이다.
- 실제 inventory와 원래 snapshot index 바이트 SHA 불변. development/live data-coverage JSON 전체도 이전 기준과 동일하다.
- 근거: artifacts/side-evidence-batch-integration-20261025/{tests-before.log,cache-before.log,tests-after.log,verification.json,inventory-smoke-report.json}.

원본 자료·사람 정답·면·수량·모델·공용 CLI 변경 없음. 학습·추론·외부 AI 호출 0회. 진척률 usable-card-analysis-v1.0 30/100 유지. 선택 실행 도구로 통합한 것이며 A3 판정 연결·primary 편입·면 확정은 아니다. 미해결 정책과 TOCTOU/강제 종료/hardlink 한계는 보존한다.

롤백은 검토 보정/수정 커밋과 위 통합 8개 커밋을 역순 revert한다. 작업 문서는 남기고 싶으면 소스·테스트 변경 커밋만 의존 관계를 확인해 되돌린다. 원격 push는 하지 않았다.
