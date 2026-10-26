task_id: pilot-review-conflicts-20261026
owner: Codex
status: implementing
base_sha: beb532a77261b0bd5ba41d034362e969d7145cc1
branch: codex/pilot-review-conflicts-20261026
goal: 같은 결과 SHA의 완료 검토가 서로 다를 때 입력 순서로 수정 수량을 선택하지 않고, 음수/bool/누락 correction 수량을 거절한다.
allowed_files:
- card_condition/pilot_summary.py
- tests/test_pilot_review_conflicts.py
- docs/collaboration/tasks/pilot-review-conflicts-20261026.md
- docs/collaboration/reports/pilot-review-conflicts-20261026.md
- ignored artifacts/pilot-review-conflicts-20261026/index.html
forbidden_files: 그 외 소스·실제 사용/검토 로그·모델·정답·진척/조건·Claude 소유 파일
contract:
- counts에 corrected_defect와 corrected_normal이 명시되어야 하며 모든 제공 count는 bool 아닌 비음수 정수여야 한다. report SHA는 nonempty string, review_completed는 명시 bool이어야 한다. missing을 0으로 추정하지 않는다.
- 같은 SHA 완료 검토 counts가 같으면 한 번만 반영한다. 다르면 양쪽 입력 순서 모두 ValueError. 미완료는 별도 카운트하고 완료를 덮지 않는다. 사람 정답/우선순위는 추정하지 않는다.
- F2 조건·release/config 분리·region review 의미·pilot_certified=false 유지. face_counts는 별도 의미이며 region 수정 수량에 합치지 않는다. 검토시간/정확도 개선 주장 금지.
structure: pilot_summary 7→7, 새 test<=7. summarize 내 기존 입력 루프를 수정하며 새 helper/wrapper/호출깊이 증가 없음.
checks: old forward corrected_cells=-1, reverse=2 재현. 동일검토 중복/상충검토 양방향/미완료+완료/잘못된count·flag/CLI 오류 + 기존108회귀, AST/compile/diff/HTML/main push.
experiment: 없음. 합성 JSON 검증만, 실사진 추론·학습·외부AI 없음.
handoff: 파일·diff·실검사·미검증·리스크·롤백·HTML·원격 기록. 고정진척30/100 유지.
