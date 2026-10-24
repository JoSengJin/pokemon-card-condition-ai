# 데이터 부족표 출처·중복 감사 — 2026-10-25

task `data-coverage-provenance-20261025`. 감사 소스 기준은 `bdc8fa616d3da756524927c6a4bd6637a8f38b08`이고 시작점은 dispatch `91252d77b60e6de31b91a504daca5fadceaa9641`이다. 두 커밋 사이 변경은 task 문서뿐이다. 학습·추론·사진 열람·라벨 변경·외부 AI 호출은 0회다. 모델 성능과 개발 진척률은 바뀌지 않는다.

근거는 로컬 snapshot 46개 파일이다(Git 제외). index SHA 46/46 일치, 누락 0, 미등재 파일 0. 사진 경로는 문자열로만 다뤘다.

## (a) 근거 있는 발견 — 3개

### 1. 대상 구역 밖 종류별 점이 구역 단위에서 기록 없이 빠짐 (실제 1건)

- 코드: `card_condition/point_dataset.py:51-53`이 점을 3×3 칸에 배정한다. `card_condition/data_coverage.py:44-50`은 `REGION_TARGET_AREAS[question]` 칸만 순회한다. `data_coverage.py:60-67`은 같은 점을 `typed_points`에 보존한다. 대상 밖 칸에 배정된 점은 `skipped`와 `projection_skipped` 어디에도 남지 않는다.
- 실제 근거: `development-v2.json`의 train 뒷면 `corner_defect` 점 1개. 상대좌표가 middle_right 칸(모서리 대상 아님)이다. 같은 면의 upper_left 모서리 양성 단위가 이미 집계돼 있어서, 이번 snapshot의 양성 단위·실물 수 영향은 0이다. `live-v2.json`에는 0건이다.
- 최소 반례: `tests/test_data_coverage_provenance.py::test_off_target_typed_point_is_projected_or_traced`. box `[0,0,1,1]`, `corner_defect` 점 `(0.95, 0.4)` 1개다. 결과는 typed 1점/1실물, 양성 구역 0단위, skip 기록 0개다. 현재 코드에서 마지막 단언이 실패한다.
- 영향: `typed_positive_points`와 구역 양성 수가 설명 없이 어긋난다. 어떤 면의 유일한 점이 대상 밖이면, 그 실물은 구역 양성에서 빠지는데 이유를 추적할 수 없다. 점의 종류나 box가 틀렸다고 추정하지 않는다.

### 2. 최신 보완 6행의 `side=front`를 뒷받침하는 사람 근거가 snapshot에 없음 (면미확인)

- 근거: `supplemental-inventory.json`의 `latest_supplements` 6행은 모두 `side: "front"`이다(같은 group 하나, photo-1 3행, photo-3 3행). 2026-10-24 REPORT도 이 자료를 "앞면 1실물"로 기술한다.
- 이 group의 사람 응답 원문(`misdreavus-confirmed-local-intake-20261024/human-response.json`)에서 면을 직접 말한 부분은 "4번 뒷면"뿐이다. 이는 `full_back_anchor`인 photo-4에 해당한다. photo-1·photo-3을 앞면이라고 한 사람 진술은 snapshot에 없다. exact point 출처 `misdreavus-surface-exact-review-20261024/labels-review.jsonl`도 snapshot에 포함되지 않았다.
- 영향: 이 행들은 primary에 합산되지 않았으므로 현재 수치는 바뀌지 않는다. 다만 "뒷면 표면·모서리 부족을 해소하지 않는다"는 결론은 front 지정에 의존한다. 이 지정은 "anchor와 다른 사진 = 앞면" 추정일 수 있다. 근거 파일을 대조하기 전까지 면미확인으로 둔다. 앞면이 틀렸다고 주장하지 않는다.

### 3. 같은 디코딩 사진이 앞·뒤 두 셀에 동시에 집계됨 (실제 0건, 미방어 경계)

- 코드: `card_condition/data.py:72-73`은 `gradable == 1`일 때만 서로 다른 앞뒤 사진을 요구한다. `card_condition/data_coverage.py:38`의 `owners`는 사진→group만 검사한다. 단위 identity(`data_coverage.py:58`)에 side가 들어 있어서, 같은 사진이 front 단위와 back 단위로 각각 남는다.
- 최소 반례: `test_one_decoded_photo_counts_on_one_side_only`. gradable 0인 레코드의 back을 front와 같은 파일로 두고, 양면에 `visibility_issues=['blur']`를 준다. 관찰 제한 양성이 앞 1 + 뒤 1 = 2단위가 된다. 현재 코드에서 실패한다.
- 실제 영향: development-v2·live-v2 모두 양면에 쓰인 사진 0개, 여러 card_id가 공유한 사진 0개다. 현재 부족표의 수치는 왜곡되지 않았다. 사진 하나가 한 실물의 양면일 수는 없으므로 결함 후보로 남긴다. 수정 우선순위는 1번보다 낮다.

## 확인했지만 결함이 아닌 범위

- `region_reviews`는 검토 완료 표시일 뿐 정상 라벨을 만들지 않는다. `data_coverage`도 이를 읽지 않아 UI(`review.html` reviewed-unknown 회귀)와 일치한다.
- `visibility_issues` 키가 없으면 관찰 제한은 unknown이다. 빈 목록이면서 면 gradable=1일 때만 음성이다. 기존 회귀가 있다.
- `perspective`인데 box 미확인이거나 glare 위치가 없으면 구역 정상을 제외한다(`point_dataset.py:76-79`). 오래된 box는 `unreviewed_box_units`로 공개된다.
- 여러 점·구역은 실물 수를 부풀리지 않는다. 같은 사진의 다른 group, split 누출은 거절한다. 기존 회귀가 있다.
- 3×3 경계선 위의 점: grid 모드에서 인접 칸 정상과 겹치면 감사가 중단된다(포함 경계, 보수적 동작). 두 snapshot 모두 경계선 위 점은 0개라 결함으로 보고하지 않는다.
- `duplicate_crop` 56건(development)은 grid 패치 병합용 skip이다. typed point 보존과는 별개이며 수량 왜곡이 없다.

## 국소자료 12출처 대조

30행은 위치(디코딩 사진·ROI box·종류) 기준 고유 23개다. 4개 위치가 4개 출처에 걸쳐 12행으로 중복된다(confirmed-detail-intake, eevee, raichu, workflow-review). 13개 group은 모두 primary 70실물과 live 69목록에 없다. 행에 side 필드가 없고, 사진 해시도 manifest 단위와 하나도 일치하지 않는다. 따라서 manifest로 면을 확정할 수 있는 행은 없다. `full_back_anchor`의 뒷면 판정은 `Codex visual photo eligibility, not condition truth`로 기록돼 있어 사람 면 근거가 아니다.

| 출처 | 행 | 분류 | 근거 |
|---|---:|---|---|
| charmeleon-normal-edge-20261020 | 1 | 면미확인 | anchor와 같은 사진이지만 anchor 면 판정은 Codex 시각 판정 |
| confirmed-detail-intake-20261018 | 1 | 역사적 중복 | 같은 위치가 eevee·raichu·workflow에 반복됨. anchor와 다른 사진이며 앞면으로 추정하지 않음 |
| edge-contrast-confirmed-20261021 | 3 | 면미확인 | anchor 동일, 사람 면 진술 없음 |
| eevee-normal-edge-training-20261019 detail-rows | 5 | 역사적 | W 엣지 정상은 `label-clarification-pending`에서 철회(null)됨. 되살리지 않음 |
| eevee current-effective | (5) | 정정대기 | Y 모서리 행을 추가했고 pending 기록도 Y=1인데, `clarification-verification`은 `Y_unknown: true`. 기록 간 모순 |
| golisopod-bottom-normal-20261021 | 1 | 면미확인 | anchor 동일, 사람 면 진술 없음 |
| golisopod-normal-edge-20261021 | 1 | 면미확인 | 위와 같은 group, 범위는 끝선 한정 |
| misdreavus-confirmed-local-intake-20261024 | 2 | photo-4 엣지: 면 확정(back), photo-3 표면: 면미확인 | "4번 뒷면" 사람 진술 + anchor 일치 / photo-3은 진술 없음 |
| mixed-edge-batch-20261020 | 4 | 면미확인 | 1행은 anchor와 다른 사진이며 앞면으로 추정하지 않음 |
| raichu-corner-seed-20261019 detail-rows | 7 | 역사적 | `clarified-detail-rows`가 대체함(엣지 2행 추가). 모서리 2·4는 `clarified-readiness`에서 human truth unknown |
| raichu corner-1/-3 정상 | (2) | 정정대기(근거 누락) | 사람 응답 원문은 정상이지만, task가 언급한 모서리 정상 감사 실패 기록이 snapshot에 없음. 정상 확정으로 되살리지 않음 |
| raichu-edge-normal5-20261020 | 1 | 면미확인 | raichu와 같은 group |
| same-photo-damage45-20261021 | 2 | 면미확인 | edge-contrast와 같은 group, 다른 ROI |
| workflow-review-20261019 | 3 | 역사적 중복 | eevee·raichu 행의 부분집합. `resolved-human-tasks` A/B와 일치 |

현재 국소자료를 primary 표에 합치려면 행마다 다음 넷을 먼저 증명해야 한다.
1. 면: 사람 진술, 또는 사람이 면을 지정한 manifest 사진과의 해시 일치.
2. 범위: ROI를 카드 box 기준 3×3 칸에 대응시키는 근거. 대응이 없으면 별도 분모로 둔다.
3. 정정 이력: 최신 유효 파일과 철회 기록.
4. 실물 관계: 새 group이라면 같은 실물 확인과 split 일관성.

이 넷을 갖춘 행은 misdreavus photo-4 엣지 1행뿐이다. 그마저 카드 box가 없는 ROI이고 뒷면 엣지 양성은 이미 충족(72/30)이라 부족표 영향이 0이다. 그래서 매핑 제안 대상에서 뺐다.

## (b) 다음 수정 1개 — 사람 입력 불필요

`data_coverage.coverage_report`에서, 3×3 칸이 `REGION_TARGET_AREAS[label]`에 없는 typed point마다 `skipped`에 `dict(card_id, side, label, area, reason='point_outside_target_area')`를 추가한다. 수량 셀·units·typed_points는 바꾸지 않는다. 점 배정 규칙은 `point_dataset.py:51-53`과 같아야 한다.

## (c) 최소 회귀와 판정 기준

- 성공 조건 셋:
  - `test_data_coverage_provenance.test_off_target_typed_point_is_projected_or_traced`가 통과한다.
  - 기존 `test_data_coverage test_point_dataset test_region_dataset test_regions test_review`가 모두 통과한다.
  - 기본 checkout에서 개발 snapshot manifest로 새 경로에 감사를 다시 냈을 때 `cells`·`units`·`typed_points`가 development-v2와 같고, `skipped` 증가분이 `point_outside_target_area` 정확히 1건이다.
- 실패 조건: 셀 수치가 하나라도 바뀌거나, 대상 안 점이 skip으로 기록되거나, 기존 회귀가 실패하는 경우.
- `test_one_decoded_photo_counts_on_one_side_only`(발견 3)는 이 수정 범위 밖이므로 계속 실패하는 것이 정상이다. 거절할지 skip할지는 별도 계약에서 정한다.

## (d) Codex용 구현 프롬프트

> `card_condition/data_coverage.py`만 수정한다. typed point 루프(`for point in annotation.get('defect_points', [])`)에서, 면 양성 확인을 통과한 점의 3×3 칸을 `point_dataset.py:51-53`과 같은 규칙으로 계산한다. 그 칸이 `REGION_TARGET_AREAS[label]`에 없으면 `skipped.append(dict(card_id=..., side=..., label=..., area=..., reason='point_outside_target_area'))`를 추가한다. typed point 보존과 셀 집계는 그대로 둔다. `PYTHONPATH=tests .venv/bin/python -m unittest test_data_coverage test_point_dataset test_region_dataset test_regions test_review test_data_coverage_provenance -q`에서 provenance의 off-target 테스트만 새로 통과하고 one-photo 테스트는 실패한 채 남는지 확인한다. 실제 개발 manifest 재감사는 새 출력 경로로만 낸다.

## 미검증·리스크·롤백

- 미검증: Codex 통합 후의 `test_review`(이 worktree에서는 실행하지 않음). 기본 checkout manifest로 재감사하는 일. 발견 2의 원 출처 `labels-review.jsonl`과 eevee Y 기록 모순의 원인. raichu 모서리 정상 감사 실패 기록.
- 리스크: 발견 1은 1건만 근거로 했다. 합성 테스트 통과가 원본 국소자료의 정답·면 매핑을 입증하지 않는다. 발견 2를 "앞면 오류"로 읽으면 안 된다. 근거가 없다는 뜻이다.
- 롤백: 이 브랜치는 문서 2개와 신규 테스트 1개만 추가한다. 통합 커밋만 revert하면 된다. 원본 데이터·모델·artifacts는 건드리지 않았다.
