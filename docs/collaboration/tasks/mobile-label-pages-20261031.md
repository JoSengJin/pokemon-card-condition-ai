# 모바일 전용 구역 라벨 입력 (review.html 대체 경로, 학습 자료 확충용)

- task_id: mobile-label-pages-20261031
- owner: Claude (Codex 토큰 만료 기간 대행)
- status: assigned
- branch: claude/mobile-label-pages-20261031
- approval: 사용자 "학습 자료 확충 시 모바일은 review 접근이 안되니 모바일 전용으로도 준비해줘"(2026-10-31). 새 정답 생성·학습·외부 호출 승인 아님.

## 배경
폰 뷰어는 로컬 서버(`review.html`)에 접근할 수 없고 클립보드 API·localStorage도 없다(붙여넣기 방식만 가능). 이전 g·h 모바일 답(`region-answers.txt` 등)은 `validate_annotations` 구조와 달라 학습 라벨로 바꿀 수 없었다. 그 간극을 없애는 것이 목표다.

## 목표
1. 정적 페이지 생성기: 면마다 카드 상자(네 모서리 끌기, 자동 제안에서 시작)와 8개 엣지 구역(탭: 미확인→정상→결함)을 입력하고 결과 텍스트를 복사한다.
2. 가져오기 도구: 붙여넣은 답을 기존 `labels-review.jsonl`의 `side_annotations`로 바꿔 **새 파일**에 쓴다. 반드시 `validate_annotations`를 통과해야 한다. 같은 `review.html` 저장 형식(box, box_reviewed, region_labels의 edge_defect, labels.edge_defect)이다.

## 계약
- 상자는 [l,t,r,b] 0~1. "상자 확인" 버튼을 눌러야 `box_reviewed=true`. 누르지 않으면 상자 값만 쓰고 확인은 false.
- 구역: 정상→`region_labels[area].edge_defect=0`, 결함→`1`, 미확인→기록하지 않음. 면 `labels.edge_defect`: 결함 구역이 있으면 1, 8구역 전부 정상이면 0, 그 외 null. `gradable`·표면·모서리·센터링은 건드리지 않는다.
- 출력은 항상 새 파일(존재하면 실패). 기존 라벨은 덮어쓰지 않고, 이미 값이 있는 면(박스확인/라벨 있음)은 충돌하면 실패.
- 답에 없는 면은 변경 없음. 알 수 없는 id·구역·상태는 실패.

## 구조
- `tools/mobile_label_pages.py`(함수 4개 이하), `tools/mobile_label_import.py`(함수 4개 이하, 호출 깊이 3 이하), 테스트 `tests/test_mobile_label.py`. 기존 도구·review.html·모델 코드 수정 없음.

## checks
단위 테스트(정상 변환, 거절 경로, validate 통과), 실제 k 배치로 페이지 생성과 가져오기 dry run(임시 답).

## 롤백
새 파일 4개 삭제/`git revert`.
