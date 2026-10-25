# 협력자 기준 예제 후보 (2026-10-25, 사용자 승인 전)

- 입력: d 채택본 `coverage.json`(SHA256 `143164a4…`, manifest `ad021468…`). 읽기만 했다.
- 목적: 협력자의 기준 예제 검사, 그리고 지침 초안 C절 "예제" 칸에 쓸 후보다.
- **새 질문이 아니다.** 사용자가 이미 저장한 정답을 그대로 쓴다. 사용자는 "예제로 써도 되는지"만 고르며, 정답을 다시 판정하지 않는다. 사진을 보고 예제로 부적절하면(애매함, 너무 쉬움) 빼면 된다.
- 선별 규칙(결정적, 모델 점수 미사용):
  - 정답이 0 또는 1이고, 영역 확인(box_reviewed)이 끝났고, 근거가 unknown이 아니고, 검토자 기록이 있는 단위만 고른다.
  - train을 먼저 쓴다. val 평가 자료는 노출하지 않으려고 train에 후보가 없을 때만 쓰도록 했다. 결과적으로 val은 0건이다.
  - 구역 양성은 같은 카드·같은 면에 같은 종류의 결함점이 있는 경우만 고른다.
  - 셀당 최대 2개, 서로 다른 실물을 고르고, 덜 쓰인 실물을 먼저 고른다.
  - D1 자료는 d manifest에 없다(train 56·val 14만 있음).
- 결과: 후보 34개, 실물 22개(모두 train). 경로가 포함된 원본 목록은 Claude worktree의 ignored `artifacts/data-acquisition-followup-20261025/gold-example-candidates.json`(SHA256 `11b5a36d…`)에 있다. 이 문서에는 개인 경로와 사진을 넣지 않았다.

## 후보

| 질문 | 면 | 정답 | 실물(card_id) | 구역 | 분할 | 근거 종류 | 사진 SHA 앞 12자 |
|---|---|---|---|---|---|---|---|
| 센터링 | 앞 | 양성 | `ebay-pair-7d40cc3db5bdef` | face | train | explicit_side_label | `b7f61c086c57` |
| 센터링 | 앞 | 양성 | `ebay-pair-d22bdf80807677` | face | train | explicit_side_label | `e07c1669d376` |
| 센터링 | 앞 | 정상 | `ebay-pair-9f1ce9c8ad88f2` | face | train | explicit_side_label | `151ca980240e` |
| 센터링 | 앞 | 정상 | `f` | face | train | explicit_side_label | `4948f1220379` |
| 센터링 | 뒤 | 양성 | `ebay-pair-2b07106aaa11a4` | face | train | explicit_side_label | `4ac710c099d7` |
| 센터링 | 뒤 | 양성 | `ebay-pair-cbf990a712e9ef` | face | train | explicit_side_label | `b8ed24eee5b7` |
| 센터링 | 뒤 | 정상 | `h` | face | train | explicit_side_label | `55b66df8488b` |
| 센터링 | 뒤 | 정상 | `ㅋ-1` | face | train | explicit_side_label | `34bad8227bbd` |
| 모서리 | 앞 | 양성 | `ebay-pair-6051e594d7c282` | lower_left | train | explicit_region_or_same_kind_point | `e9ad762c0e67` |
| 모서리 | 앞 | 양성 | `ebay-pair-a20ca70073dcbc` | upper_left | train | explicit_region_or_same_kind_point | `2eb9237c7f6b` |
| 모서리 | 뒤 | 양성 | `ebay-pair-a1c1362ea21fc3` | upper_left | train | explicit_region_or_same_kind_point | `c711634affdf` |
| 모서리 | 뒤 | 양성 | `ㅋ-3` | lower_right | train | explicit_region_or_same_kind_point | `f7c576555bc9` |
| 엣지 | 앞 | 양성 | `ㅋ-2` | lower_right | train | explicit_region_or_same_kind_point | `e6cac4f2a7e9` |
| 엣지 | 앞 | 양성 | `ㅋ-4` | lower_center | train | explicit_region_or_same_kind_point | `6f7ea100bdb7` |
| 엣지 | 앞 | 정상 | `ebay-pair-cbf990a712e9ef` | lower_center | train | explicit_region_or_same_kind_point | `fa46831fd559` |
| 엣지 | 뒤 | 양성 | `ebay-pair-7efc0745c15362` | lower_right | train | explicit_region_or_same_kind_point | `d162c075b252` |
| 엣지 | 뒤 | 양성 | `ㅋ-10` | lower_right | train | explicit_region_or_same_kind_point | `7c2904bd6556` |
| 엣지 | 뒤 | 정상 | `ㅋ-8` | lower_right | train | explicit_region_or_same_kind_point | `1cfbd3563fdd` |
| 엣지 | 뒤 | 정상 | `ebay-pair-2b07106aaa11a4` | lower_center | train | explicit_region_or_same_kind_point | `4ac710c099d7` |
| 표면 | 앞 | 양성 | `ㅋ-7` | upper_left | train | explicit_region_or_same_kind_point | `6d7344a9f8c9` |
| 표면 | 앞 | 양성 | `ebay-pair-7efc0745c15362` | lower_center | train | explicit_region_or_same_kind_point | `db43365e08b2` |
| 표면 | 앞 | 정상 | `ebay-pair-9f1ce9c8ad88f2` | lower_center | train | explicit_region_or_same_kind_point | `151ca980240e` |
| 표면 | 앞 | 정상 | `ebay-pair-7efc0745c15362` | middle_left | train | explicit_region_or_same_kind_point | `db43365e08b2` |
| 표면 | 뒤 | 양성 | `ebay-pair-66adf76412177b` | lower_left | train | explicit_region_or_same_kind_point | `2834672e6762` |
| 표면 | 뒤 | 양성 | `z` | lower_center | train | explicit_region_or_same_kind_point | `52f16aaf0fdd` |
| 표면 | 뒤 | 정상 | `ebay-pair-6051e594d7c282` | center | train | explicit_region_or_same_kind_point | `f1f787ca57e3` |
| 표면 | 뒤 | 정상 | `ebay-pair-a20ca70073dcbc` | center | train | explicit_region_or_same_kind_point | `8cbea9b772d7` |
| 관찰제한 | 앞 | 양성 | `ㅋ-12` | face | train | explicit_visibility_issues | `717c1859964d` |
| 관찰제한 | 앞 | 정상 | `f` | face | train | explicit_visibility_issues | `4948f1220379` |
| 관찰제한 | 앞 | 정상 | `h` | face | train | explicit_visibility_issues | `a71bdad8573d` |
| 관찰제한 | 뒤 | 양성 | `ㅋ-9` | face | train | explicit_visibility_issues | `fd2b68af6176` |
| 관찰제한 | 뒤 | 양성 | `ㅋ-4` | face | train | explicit_visibility_issues | `1f7d27df7e00` |
| 관찰제한 | 뒤 | 정상 | `z` | face | train | explicit_visibility_issues | `52f16aaf0fdd` |
| 관찰제한 | 뒤 | 정상 | `f` | face | train | explicit_visibility_issues | `3115a981b574` |

## 비어 있는 셀

| 질문 | 면 | 정답 | 찾은 수 |
|---|---|---|---|
| 모서리 | 앞 | 정상 | 0/2 |
| 모서리 | 뒤 | 정상 | 0/2 |
| 엣지 | 앞 | 정상 | 1/2 |
| 관찰제한 | 앞 | 양성 | 1/2 |

- **모서리 정상(앞·뒤)이 0개인 이유:** 모서리 정상 단위는 있지만 모두 영역 확인 전이다. 지금은 예제로 쓸 수 없다. 해결하려면 해당 사진의 영역 확인(geometry)만 하면 된다. 정답을 다시 묻는 것이 아니다. 이 일은 A3 round2의 영역 확인 단계와 겹치므로, 새 질문을 따로 만들지 않고 그 결과를 기다린다.
- 엣지 앞 정상과 관찰제한 앞 양성은 1개씩만 있다.

## 리스크

- 많은 후보가 eBay 판매 사진이다. 같은 장소에서 협력자에게 화면으로 보여 주는 정도는 내부 검토 용도이지만, 사진 파일을 외부로 전달하지 않는다.
- 예제가 train에서만 나와 촬영 조건이 실제 파일럿 사진(직접 촬영)과 다를 수 있다. 그래서 기준 예제 검사의 통과율은 파일럿 품질을 보증하지 않는다.
