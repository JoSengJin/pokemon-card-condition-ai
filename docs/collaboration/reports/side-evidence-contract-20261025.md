# 면 근거 sidecar 계약 검토 — 2026-10-25

task `side-evidence-contract-20261025`. 기준은 base `c7c4b8de9d6eeb751743367424729734c00e4b73`이고 시작은 `df899e695fd48143d10797136025ca8f7551a454`이다. 문서 계약 검토만 했다. 도구 구현·채택·라벨 변경·사진 열람·추론·학습·외부 AI 호출은 0회다. 진척률 30/100과 모델 성능은 바뀌지 않는다.

근거는 추적 보고서 두 개뿐이다. 이 worktree에는 원본 snapshot이 없다. 아래 사례는 그 두 보고서에 이미 기록된 사실을 합성 ID·합성 SHA로 바꾼 것이며, 새로운 면·날짜·정답은 만들지 않았다.
- `docs/collaboration/reports/data-coverage-provenance-20261025.md`
- `docs/collaboration/reports/provenance-source-followup-20261025.md`(Codex 인수 보정 포함)

## 1. 직전 제안의 문제

직전 제안은 행마다 값 하나(`human_statement` / `review_slot_only` / `missing_source` / `codex_anchor_eligibility`)를 붙이는 방식이었다. 그대로 구현하면 안 된다.

| 문제 | 근거 사례 | 계약 반영 |
|---|---|---|
| 유형이 배타적이지 않다 | photo-4는 사람 진술(back)과 Codex anchor 적격성(같은 사진)을 함께 가진다 | 단일 값 대신 `evidence` 목록. 유형별로 여러 항목 허용 |
| `missing_source`는 근거 유형이 아니다 | photo-1은 참조한 원본이 없는 것이 아니라, 면 근거를 snapshot에서 찾지 못한 것이다 | `evidence`와 분리. 참조됐는데 없는 원본만 `missing_sources`, 찾지 못한 것은 `searched_no_side_evidence` |
| 미조사와 원본 누락이 섞인다 | 조사하지 않은 행에 `missing_source`를 채우면 근거 부족처럼 보인다 | `review.status`를 `not_reviewed` / `reviewed`로 분리. `not_reviewed` 행에는 근거·누락·검색 결과를 쓸 수 없음 |
| 파생 기록이 독립 증거로 세어진다 | eevee Y는 사람 응답 1개와 그것을 반영한 후속 기록 4개가 일치했다(Codex 보정) | 근거 항목마다 `origin`(최초 사람 응답 위치)을 쓰고, 사람 응답 원본 위치 수는 서로 다른 `origin` 수로 계산 |
| 면 근거와 결함 정답·좌표·구역 근거가 섞인다 | photo-3 검토 manifest는 표면 결함 2점의 사람 근거지만 면 근거는 아니다(작업 슬롯 배치). raichu 품질 평가 한계는 면도 정답 철회도 아니다 | sidecar는 면만 다룬다. 항목의 `claim`은 `side`만 허용. 정답·좌표·구역 근거나 모델 평가는 거절 |
| 다른 inventory 버전에 잘못 적용될 수 있다 | inventory 행 id만으로는 파일 갱신 후 다른 행에 붙을 수 있다 | sidecar에 inventory 상대경로·SHA256과 행별 `row_id`·`image_sha256`·`side_claim`을 함께 고정. 하나라도 다르면 적용 거절 |

## 2. 최소 JSON 예시 (합성)

아래 값은 모두 합성이다. SHA는 반복 숫자이고 경로는 `example-` 접두사를 쓴다. 실제 파일에 적용하지 않는다.

```json
{
  "schema": "side_evidence_sidecar/v0-draft",
  "inventory": {"path": "artifacts/example-inventory/supplemental-inventory.json", "sha256": "1111111111111111111111111111111111111111111111111111111111111111", "rows_pointer": "/latest_supplements"},
  "search_scope": {"path": "artifacts/example-evidence/index.json", "sha256": "2222222222222222222222222222222222222222222222222222222222222222"},
  "rows": [
    {
      "row_id": "syn-card-a/photo-3/exact-1",
      "image_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
      "side_claim": "front",
      "review": {"status": "reviewed"},
      "evidence": [
        {"type": "review_slot", "claim": "side", "value": "front", "asserts_side": false,
         "source": {"path": "artifacts/example-exact-review/labels-review.jsonl", "sha256": "4444444444444444444444444444444444444444444444444444444444444444", "row_id": "syn-card-a/surface-photo3-exact", "pointer": "/front"},
         "origin": {"path": "artifacts/example-exact-review/labels-review.jsonl", "sha256": "4444444444444444444444444444444444444444444444444444444444444444", "row_id": "syn-card-a/surface-photo3-exact", "pointer": "/front"},
         "note": "single-photo task slot; pair_verified false"}
      ],
      "missing_sources": [],
      "searched_no_side_evidence": false,
      "summary": {"human_side_origins": 0, "side_basis": "no_human_statement"}
    },
    {
      "row_id": "syn-card-a/photo-1/reviewed-1",
      "image_sha256": "5555555555555555555555555555555555555555555555555555555555555555",
      "side_claim": "front",
      "review": {"status": "reviewed"},
      "evidence": [],
      "missing_sources": [],
      "searched_no_side_evidence": true,
      "summary": {"human_side_origins": 0, "side_basis": "no_human_statement"}
    },
    {
      "row_id": "syn-card-a/photo-4/edge",
      "image_sha256": "6666666666666666666666666666666666666666666666666666666666666666",
      "side_claim": null,
      "review": {"status": "reviewed"},
      "evidence": [
        {"type": "human_statement", "claim": "side", "value": "back", "asserts_side": true,
         "source": {"path": "artifacts/example-intake/human-response.json", "sha256": "7777777777777777777777777777777777777777777777777777777777777777", "row_id": "syn-card-a/photo-4/edge", "pointer": "/user_quote"},
         "origin": {"path": "artifacts/example-intake/human-response.json", "sha256": "7777777777777777777777777777777777777777777777777777777777777777", "row_id": "syn-card-a/photo-4/edge", "pointer": "/user_quote"}},
        {"type": "human_statement", "claim": "side", "value": "back", "asserts_side": true,
         "source": {"path": "artifacts/example-intake/detail-rows.jsonl", "sha256": "8888888888888888888888888888888888888888888888888888888888888888", "row_id": "syn-card-a/photo-4/edge", "pointer": "/human_evidence/user_quote"},
         "origin": {"path": "artifacts/example-intake/human-response.json", "sha256": "7777777777777777777777777777777777777777777777777777777777777777", "row_id": "syn-card-a/photo-4/edge", "pointer": "/user_quote"},
         "note": "derived copy of the same reply"},
        {"type": "codex_anchor_eligibility", "claim": "side", "value": "back", "asserts_side": true,
         "source": {"path": "artifacts/example-intake/effective-proposals.json", "sha256": "9999999999999999999999999999999999999999999999999999999999999999", "row_id": "syn-card-a/photo-4/edge", "pointer": "/full_back_eligibility"},
         "origin": {"path": "artifacts/example-intake/effective-proposals.json", "sha256": "9999999999999999999999999999999999999999999999999999999999999999", "row_id": "syn-card-a/photo-4/edge", "pointer": "/full_back_eligibility"}}
      ],
      "missing_sources": [],
      "searched_no_side_evidence": false,
      "summary": {"human_side_origins": 1, "side_basis": "human_statement_without_claim"}
    },
    {
      "row_id": "syn-card-b/corner-1",
      "image_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "side_claim": null,
      "review": {"status": "not_reviewed"},
      "evidence": [],
      "missing_sources": [],
      "searched_no_side_evidence": false,
      "summary": {"human_side_origins": 0, "side_basis": "not_reviewed"}
    }
  ]
}
```

필드 의미:
- `side_claim`: inventory 행의 기존 `side`를 그대로 복사한 값이다. 없으면 null이다. sidecar가 면을 정하는 값이 아니고, 적용 대상 행이 맞는지 확인하는 결합 키다.
- `evidence[].asserts_side`: 그 항목이 면을 주장하는지 여부다. `review_slot`은 항상 false다. 슬롯 배치는 작업 구성 기록이다.
- `origin`: 그 근거가 처음 기록된 위치다. 파생 사본은 `source`만 다르고 `origin`은 원본과 같다. 이는 작성자가 선언한 연결이며, 위치가 다르다는 것만으로 독립적인 사람 판단을 입증하지 않는다. 실제 구현은 source와 origin 양쪽의 SHA·참조 대상 및 파생 연결 근거를 확인해야 한다. 연결을 입증할 수 없으면 검증 미완료로 남긴다.
- `summary`: 사람이 손으로 쓰지 않는다. 도구가 `evidence`에서 다시 계산할 수 있어야 하며, 저장값과 다르면 거절한다. 이 재계산은 선언된 origin의 중복만 제거하며, 허위 origin이나 잘못된 파생 연결 자체를 판별하는 검사는 아니다.
  - `human_side_origins`: `type=human_statement`이면서 `asserts_side=true`인 항목의 서로 다른 `origin` 수.
  - `side_basis`: 다음 중 하나.
    - `not_reviewed`
    - `no_human_statement`
    - `human_statement_matches_claim`
    - `human_statement_conflicts_claim`
    - `human_statement_without_claim`
    - `human_statements_disagree`
- `missing_sources`: 근거 원본이 다른 기록에 경로로 참조됐는데 snapshot에 없는 경우다. 원소는 `{"path", "referenced_by": {"path", "sha256", "pointer"}}`이다. 참조 없이 찾지 못한 경우는 `searched_no_side_evidence: true`로 쓰고, 탐색 범위는 `search_scope`의 SHA로 고정한다.

사례 대응:
- photo-3 → 첫째 행(`review_slot`만, 사람 면 근거 0).
- photo-1 → 둘째 행(조사했지만 면 근거 없음, 참조된 누락 원본 없음).
- photo-4 → 셋째 행. 사람 응답과 그 파생 사본 2개 항목이 있지만 `origin`은 1개이고, Codex anchor 항목은 별도 유형이다. 실제 photo-4는 보완 6행에 없다. 예시는 소속 inventory를 합성으로 가정했다.
- raichu → 넷째 행(아직 sidecar 조사를 하지 않은 상태 예시). 기존 보고서상 raichu의 면 근거는 Codex anchor뿐이다. 그 품질 평가 한계(단일 정상 group, RGB 지름길)는 면 근거가 아니므로 조사하더라도 `evidence`에 넣지 않는다.
- eevee Y는 면 사례가 아니다. 결함 정답의 정정 이력이라 sidecar 대상이 아니다. 거기서 얻은 원칙(파생 기록은 독립 증거가 아님)만 `origin` 규칙으로 반영했다.

## 3. 수용·거절 조건 (구현용)

공통 보존 조건: sidecar를 읽거나 적용해도 다음 셋이 바이트·값 단위로 같아야 한다.
- inventory 원본
- 각 행의 `side`·`target`·box·point
- data-coverage 집계 셀

sidecar는 면 확인이나 정답 변경을 자동으로 뜻하지 않는다. `human_statement_matches_claim`이어도 primary 편입·수량 합산·`side` 수정을 일으키지 않는다.

| # | 입력 | 기대 |
|---|---|---|
| A1 | 위 예시 그대로, inventory·근거 SHA 일치 | 수용. 행 4개 보고, inventory·집계 불변 |
| A2 | 같은 사람 응답의 파생 사본을 근거 2개로 추가 | 수용. `human_side_origins`는 1 유지 |
| A3 | 한 행에 `human_statement`와 `codex_anchor_eligibility` 공존 | 수용. 유형은 배타적이지 않다 |
| R1 | `inventory.sha256`이 실제 inventory와 다름 | 전체 거절. 다른 버전 적용 금지 |
| R2 | `row_id`가 inventory에 없음, 또는 `image_sha256`·`side_claim`이 그 행과 다름 | 전체 거절 |
| R3 | 같은 `row_id`가 두 번 나옴 | 전체 거절 |
| R4 | `not_reviewed` 행에 `evidence`·`missing_sources`가 있거나 `searched_no_side_evidence: true` | 거절. 미조사를 누락으로 채우지 않는다 |
| R5 | `reviewed` 행인데 `evidence`·`missing_sources`가 비어 있고 `searched_no_side_evidence: false` | 거절. 결과가 불명확하다 |
| R6 | 항목의 `claim`이 `side`가 아님(`target`, `point`, `region`, `model_eval` 등), 또는 행에 `side`·`target`·`box`·`point` 필드를 씀 | 거절. 면 근거와 정답·좌표·구역 근거를 섞지 않는다 |
| R7 | `review_slot` 항목이 `asserts_side: true` | 거절 |
| R8 | 저장된 `summary`가 `evidence`로 다시 계산한 값과 다름(파생 사본을 별도 origin으로 센 경우 포함) | 거절 |
| R9 | `source` 또는 `origin`의 SHA가 실제 파일과 다르거나 참조 값이 없음(원본이 있는 경우) | 거절 |
| R10 | `missing_sources`의 `referenced_by`가 해당 경로를 실제로 참조하지 않음 | 거절. 참조 없는 누락은 `searched_no_side_evidence`로만 표시한다 |
| R11 | `search_scope.sha256`이 실제 index와 다름 | 거절. 다른 탐색 범위의 "찾지 못함"을 재사용하지 않는다 |
| R12 | 알 수 없는 `type`·`side_basis`·`schema` | 거절 |

`human_statement_conflicts_claim`과 `human_statements_disagree`는 거절 사유가 아니다. 면을 고르지 않고 그대로 보고만 한다.

## 4. 결정이 필요한 항목 (미해결)

1. sidecar 저장 위치·작성자·버전 정책: Codex 소유 경로, inventory 갱신 시 새 sidecar를 낼지 여부.
2. `pointer` 형식: JSON Pointer(RFC 6901)로 할지, JSONL은 `row_id`+필드명으로 할지. 사람 응답이 문장 하나에 여러 사진을 다룰 때 사진별 대응(예: "4번"→photo-4)을 무엇으로 고정할지. 현재 근거에서 이 대응은 intake 기록의 observation id에만 있다.
3. `codex_anchor_eligibility`·`review_slot`을 `evidence`에 둘지, 면 주장이 아닌 별도 `context` 목록으로 뺄지.
4. 충돌(`human_statement_conflicts_claim`)을 감사 출력에서 경고로 둘지, A3 판정 차단 조건으로 둘지. 사람 판단 영역이므로 이 문서에서 정하지 않는다.
5. 원본이 있는 근거만 R9로 검증할 수 있다. snapshot 밖 원본을 참조하는 행을 어떻게 다룰지는 R10과 함께 정해야 한다.

## 검사

- JSON 예시: 표준 라이브러리 `json`으로 파싱했다. 같은 스크립트로 다음을 확인했다(스크립트는 커밋하지 않음).
  - `summary` 재계산 일치
  - `not_reviewed` 행 제약
  - `review_slot`의 `asserts_side=false`
  - `row_id` 중복 없음
  - `claim=side`
  - 파생 사본의 origin 중복 계산 방지
- 변형 대조: A2(파생 사본 추가)는 수용되고 `human_side_origins` 1이 유지됐다. R3, R4, R5, R6(claim·행 필드 두 경우), R7, R8, R12는 각각 거절됐다.
- 미검증: R1·R2·R9·R10·R11은 실제 inventory·원본 파일과의 SHA·참조 대조가 필요하다. 이 worktree에는 원본이 없어 검사하지 않았다. 구현 시 회귀로 확인해야 한다.
- 미해결·리스크·롤백은 task 문서 실행 결과에 기록했다.

## Codex 인수 검증

부모 SHA·base 대비 허용 파일 2개·diff 공백 검사를 확인했다. JSON 4행의 요약을 재계산했고 파생 사본 추가 시 원본 위치 수 1이 유지됐다. R3–R8·R12에 해당하는 10개 변형을 독립 검사하여 모두 거절했다. 재실행 스크립트와 결과는 artifacts/side-evidence-contract-review-20261025/check_example.py 및 verification.json에 보존했다. 이 검사는 합성 예시의 내부 일관성만 검증하며 실제 validator 구현이나 원본 연결의 진실성을 증명하지 않는다.

R1·R2·R9–R11의 실제 inventory/원본 대조는 이번에 실행하지 않았다. origin 검증 경계는 위와 같이 보정했으며 pointer·사진 대응·snapshot 밖 참조 정책은 여전히 미해결이다. 문서를 초안 기록으로 통합했으며 실행 계약 확정·구현 채택·면 정답 확정과 구분한다. 코드·원본 자료·진척률 변경 없음.
