# 원본 출처·정정 이력 후속 감사 — 2026-10-25

task `provenance-source-followup-20261025`. 소스 기준은 `fccc7099f027918fb4b718d70c6f6c09a3db8f32`이고 시작점은 dispatch `9379ed1c69b5bae1db002bcddf282e59b191ab7e`이다. 두 커밋 사이 변경은 task 문서뿐이다. 이번 감사는 표준 라이브러리로 JSON·JSONL·Markdown만 읽었다. 사진 열람·추론·학습·외부 AI 호출·라벨 변경·자료 합산은 0회다. 기준, 진척률 30%, 모델 성능은 바뀌지 않는다.

## SHA 대조

`evidence/index.json` 59개 중 59개 일치(누락 0, 미등재 0). 내역은 `previous_snapshot` 46개와 `additional_original` 13개다. 사진·모델·키 복사본은 0개다. 아래 경로는 모두 `artifacts/` 기준 상대경로다.

SHA 일치는 복사본이 원본 파일과 같다는 뜻일 뿐이다. 정답·면·실물·분할이 입증됐다는 뜻은 아니다. 아래 결론은 각 파일 필드가 무엇을 기록하는지에 한정한다.

## 1. 보완 6행의 면 근거 — photo-4 확인 가능, photo-3·photo-1 근거 부족

대상은 `data-coverage-20261024/supplemental-inventory.json`의 `latest_supplements` 6행이다. 모두 `side: "front"`이며 photo-3 3행, photo-1 3행이다.

| 사진 | 결론 | 근거 |
|---|---|---|
| photo-4 | 확인 가능: back | `misdreavus-confirmed-local-intake-20261024/human-response.json`의 사람 응답에 "4번 뒷면"이 있고, 해당 observation id가 photo-4다. `full_back_anchor`도 photo-4다. 단, 보완 6행에는 photo-4가 없다 |
| photo-3 | 근거 부족 | 아래 참고 |
| photo-1 | 근거 부족 | photo-1 행의 사람 응답 인용에 면 진술이 없다. photo-1을 담은 라벨 원본·검토 manifest는 snapshot에 없다 |

photo-3에 대해 새로 확인한 원본은 `misdreavus-surface-exact-review-20261024/labels-review.jsonl`이다. SHA `f0a002df…`가 보완 행의 `human_evidence.sha256`과 일치한다. 이 파일은 단일 사진 정확점 검토용 manifest다.
- photo-3을 `front` 칸에 두고 `back: null`이다.
- 면 라벨은 `surface_defect` 외에 모두 null이다.
- `pair_verified: false`, `box_reviewed: false`이고, `notes`에 "Task display crop only, NOT whole-card geometry approval"이라고 적혀 있다.

검토 도구의 슬롯 구조상 한 장짜리 작업도 `front`나 `back` 칸 중 하나에 넣어야 한다. 따라서 `front` 칸 배치는 작업 구성을 기록한 것이다. 사람이 면을 판정했다는 기록이 이 파일에는 없다. 같은 디렉터리의 `verification.json`은 UI 저장·표시만 검증한다. `misdreavus-exact-followup-20261024`의 REPORT·pending·verification에도 photo-3·photo-1의 면 진술이 없다.

- 입증 범위: photo-3의 표면 결함 존재와 저장 2점은 사람이 확인했다. 면은 입증되지 않았다.
- 미해결: photo-1·photo-3의 면. "anchor(photo-4)와 다른 사진이므로 앞면"이라는 추정은 쓰지 않는다. 따라서 2026-10-24 REPORT의 "앞면 1실물" 표현은 근거가 확인되지 않은 기술이다. 앞면이 틀렸다고 판정하지는 않는다.
- 참고: pending의 photo3 첫 기술 제목 구간은 `status: completed`, `confirmed_target: 0`이다. 그러나 그 근거 파일 `misdreavus-same-photo-normal-20261024/human-response.json`은 snapshot에 없다. 이 감사에서는 정답이 아니라 출처 존재만 기록한다.

## 2. eevee Y 정정·검증 기록 — 정정은 확인 가능, `Y_unknown`은 현재 파일과 맞지 않는 역사적 기록

| 기록 | 내용 | 판정 |
|---|---|---|
| `label-correction-wy-20261019/human-observation.json` | 사람 응답 원문. W edge null(제외), X corner 1 유지, Y corner 1. Y는 표시한 우측 상단 모서리 존재만이고 exact point는 없다 | 정정 원본 |
| `label-correction-wy-20261019/effective-detail-rows.jsonl` = `eevee-normal-edge-training-20261019/current-effective-detail-rows.jsonl` | 두 파일이 바이트 단위로 동일하다(SHA `09c63e24…`). corner 1이 5행이고 Y를 포함하며, W 행은 없다 | 현재 유효 rows |
| `label-correction-wy-20261019/readiness.json`, `verification.json` | 5행, `effective_corner_positive_details: 5`, `effective_normal_W_rows: 0`, W만 human truth unknown으로 skip한다 | 현재 rows와 일치 |
| `eevee-normal-edge-training-20261019/label-clarification-pending.json` | 같은 사람 응답 원문으로 W null, X 1, Y 1을 기록한다 | 현재 rows와 일치 |
| `eevee-normal-edge-training-20261019/clarification-verification.json` | `effective_corner_positive_detail_rows: 4`, `Y_unknown: true`. 검증 대상으로 역사적 파일 3개의 SHA만 담고 있고, current-effective의 SHA는 없다 | 현재 rows(5행, Y 포함)와 불일치 |

- 결론: Y=corner 1이 우측 상단 모서리 존재로 정정됐다는 사실은 확인 가능하다. 사람 응답 원문과 서로 독립된 기록 4개가 일치한다.
- `clarification-verification.json`의 수치(4행, Y unknown)는 Y 행이 추가되기 전 상태를 기술한 것으로 판단한다. `LABEL_CORRECTION_WY_20261019.md`의 변경 목록에는 eevee의 pending·current-effective·clearance가 있지만 이 verification 파일은 없다. 즉 정정 때 갱신되지 않았다. 이 판단은 수정시각을 쓰지 않고 내용 불일치와 변경 목록만으로 내렸다.
- 미해결: 이 verification이 작성된 정확한 시점과, 당시 current-effective가 4행이었다는 직접 증거(그 시점 파일 SHA)는 snapshot에 없다.
- 범위 주의: Y는 해당 crop의 모서리 존재 양성일 뿐이다. 실제점·다른 부위·면 전체 정답이 아니다. W는 unknown이며 정상이나 손상으로 바꾸지 않는다.

## 3. raichu 모서리 정상 후보 — 사람 정답 철회 없음, 품질 평가 한계만 확인

대상은 `raichu-corner-seed-20261019`의 corner-1·corner-3이다.
- 사람 응답 `human-observation.json`의 `corner_labels`는 1:0, 3:0, 2:null, 4:null이다.
- 이후 정정 `clarification-2-4.json`(`resolved: true`)은 edge 2·4를 1로 바꿨다. `corner_targets`는 1:0, 3:0을 그대로 두고 2·4를 null로 남겼다.
- `readiness.json`(7행)과 `clarified-readiness.json`(9행) 모두 corner 0을 2로 센다. skip은 W, corner-2, corner-4(human truth unknown)뿐이다. corner-1·corner-3을 무효화한 파일은 snapshot에 없다.

"후속 감사 실패"로 기록된 것은 다음 두 가지이며, 둘 다 학습·평가 품질의 한계다(`RAICHU_LEARNING_VALIDATION_20261019.md`, 추가 원본 `raichu-corner-seed-20261019/verification.json`).
1. 정상 group이 1개뿐이어서 heldout group 평가가 불가능하다(`normal_source_groups: 1`, `grouped_quality_evaluation_possible: false`).
2. 평균 RGB 3값만으로 같은 21 crop을 19/21 맞혔다. 색·배경 지름길 위험이 있다.

이는 모델·자료 구성의 실패이고, 사람 정답을 철회한 것이 아니다.

- 결론: corner-1·3의 corner 0은 사람 정답으로 유지된 역사적·현재 기록이다. 확인 가능한 범위는 "표시한 모서리 crop에 모서리 결함 없음"이다.
- 아래는 입증되지 않았다:
  - 면: `full_back_anchor`가 같은 사진이지만, anchor 판정은 Codex 시각 적격성 판정이다.
  - 3×3 구역 대응: crop box만 있고 카드 box 기준 대응은 없다.
  - 다른 종류·구역의 정상, 모서리 정상 품질 평가의 대표성.
- 미해결: 직전 계약이 말한 "실패한 모서리 정상 감사"가 위 두 품질 한계 말고 다른 기록(예: 소비 TODO의 별도 감사)을 가리키는지는 snapshot으로 확인할 수 없다. 그런 기록이 있더라도, 모델 실패를 사람 정답 철회로 해석하지 않는다는 원칙은 유지한다.

## 사람 입력 없이 가능한 다음 조치 1개

보완 6행과 국소자료 inventory에 면 근거 종류를 따로 기록하는 필드(예: `side_evidence`)를 추가한다.
- photo-4: `human_statement`
- photo-3: `review_slot_only`
- photo-1: `missing_source`
- anchor와 같은 사진: `codex_anchor_eligibility`

`side` 값과 정답·수량은 바꾸지 않는다. 판정 기준은 두 가지다. 기존 `side`·`target`·집계 셀이 전후로 같아야 하고, 사람 진술이 없는 행이 `human_statement`로 표시되지 않아야 한다. Codex 소유의 inventory·감사 코드 변경이므로 별도 계약으로 진행한다.

## 미검증·리스크·롤백

- 미검증 항목:
  - photo-1 라벨 원본과 `misdreavus-same-photo-normal-20261024/human-response.json`.
  - eevee clarification-verification 작성 시점의 current-effective SHA.
  - 소비 프로젝트 TODO의 raichu 관련 원문.
- 리스크: "근거 부족"은 front가 틀렸다는 뜻이 아니다. 근거가 확인되지 않았다는 뜻이다. 이 보고서를 근거로 면을 back으로 바꾸거나 primary에 편입하면 안 된다.
- 롤백: 이 브랜치는 문서 2개만 바꾼다. 미통합이면 반영하지 않고, 통합 후에는 해당 커밋만 revert한다. 원본 데이터·모델은 건드리지 않았다.
