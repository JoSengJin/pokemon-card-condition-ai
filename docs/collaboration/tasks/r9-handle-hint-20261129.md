# R9 모서리 v2 화면: 끌기 점 위치·탭 안내 (2026-11-29)

```text
task_id: r9-handle-hint-20261129
owner: Claude Opus 5.5
branch: claude/r9-handle-hint-20261129 (기준 caeea93)
근거: 사용자 휴대폰 시험(합성 사진만, artifacts/phone-test-r9-20261129/)
실험·학습·추론·라벨 수집·실제 사진 화면: 없음
```

## 왜
- 사용자 휴대폰 시험에서 두 해상도 모두 0.1~0.8mm 흰 점이 확대로 보였다. 그러나 붙여넣은 결과는 24칸 모두 `미확인`이었다. 칸을 탭해 입력한다는 것을 몰랐다(사용자 확인).
- 데스크톱 Chromium 모바일 에뮬레이션(375×812)에서 상자 꼭짓점의 빨간 끌기 점(44px)이 카드 모서리 바로 위에 놓였다. 그래서 판정할 자리를 가렸고, 그 자리를 누르면 칸 대신 끌기 점이 잡혔다(elementFromPoint 확인).

## 변경 (`tools/mobile_corner_label_pages_v2.py`만, v1 화면 무변경)
- 끌기 점 4개를 상자 꼭짓점(lt·rt·rb·lb)에서 변 가운데(t·r·b·l)로 옮겼다. 점 하나는 변 하나만 움직인다. v1 스크립트 문자열을 정확히 1회씩 치환하고, 못 찾으면 import에서 멈춘다.
- `미확인` 칸에 "탭" 글자를 CSS로만 표시했다(답 문장·상태값 무변경). 사진마다 "점선 모서리 칸을 탭해 입력" 한 줄을 추가했다(`<p>`, INSTRUCTIONS 무변경 → criteria_sha256 불변).
- 함수 수: v2 4 → 4. 새 시험 파일 `tests/test_corner_label_side_dots.py` 함수 3개.

## 검증
- `PYTHONPATH=.:tests .venv/bin/python -m unittest test_corner_label_side_dots test_corner_label_four_state test_corner_label_round_trip test_label_criteria_source test_corner_import_states` → 각각 OK.
- 수정 전 코드로 새 시험 실행 → 2개 모두 FAIL(의도한 실패).
- 모바일 에뮬레이션: 네 카드 모서리 좌표의 elementFromPoint가 모두 해당 모서리 칸(`.c`)이었다. 끌기 점은 변 가운데에 있었다.
- 미검증: 실제 휴대폰에서 새 화면 조작(사용자 확인 대기), 변 가운데 점으로 상자를 맞추는 사용성.

## 리스크·롤백
- 변 가운데 점은 엣지 위에 놓인다. 이 화면은 모서리 전용이라 판정 대상을 가리지 않는다.
- 롤백: 이 커밋 revert. 기존 라벨·화면 파일은 바뀌지 않는다.

## 추가: 쪽을 사진 크기 상한으로 나누기 (사용자 지적 "사진 화질에 따라 장수가 달라진다")
- `split(sizes, per_page, max_bytes)`와 `main(..., max_mb=None)`을 추가했다. 쪽에 넣은 사진(base64) 합이 max_mb를 넘기 직전에 새 쪽을 시작한다. 상한보다 큰 사진 한 장은 혼자 한 쪽을 쓴다. per_page와 함께 쓰면 둘 중 먼저 닿는 쪽에서 자른다. 순서는 유지한다.
- 모든 사진의 해상도 규칙을 어떤 쪽보다 먼저 검사한다. 이전에는 조각별로 검사해서, 뒤 조각이 실패해도 앞 조각이 이미 쓰여 있을 수 있었다.
- CLI: `review ids out [per_page 또는 0] [max_mb]`. 함수 수 4 → 5.
- 시험: `tests/test_corner_label_page_size.py`(2개). 결함 주입(크기 상한 조건 제거) → 2개 FAIL, 원복 후 관련 6개 모듈 OK.
- 상한값은 아직 정하지 않았다. 휴대폰에서 연 최대 크기는 1.2MB이며, 큰 쪽(3·6MB 등)은 휴대폰 시험이 필요하다.
