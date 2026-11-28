# criteria-v-20261128: 판정 판본 V 조건부 채택 반영 (문서·R9 화면 문구)

브랜치 `claude/criteria-v-20261128` (기준 4e05418). merge·push·main 변경 없음.

## 변경
- `LABELING_PROTOCOL.md`: "판정 판본 V (2026-11-28 조건부 채택)" 절 추가(조건부 채택·후면 한정·호 접점 위치 경계 원문, 소급 없음, sha256 3개, 최종 버전·해시는 main 통합 시점 고정). 모서리 v2 개정 절의 "위치 경계 미정"·"판정 판본 V 확정은 별도 결정"·화면 설명 문장을 현재 상태로 고침. 엣지·표면 경계(G3 ②③), 앞면, D-1 표면·엣지 범위는 미정 유지. 11-24 절·D-1 원문은 수정 없음.
- `docs/collaboration/plans/accuracy-expert-chain-20261126/DECISIONS.md`: D-5 후속 문단 추가(기존 줄 유지).
- `tools/mobile_corner_label_pages_v2.py`: 안내문에 위치 경계 3문장 추가(옛 v1 화면 2개 무변경).
- `tests/test_label_criteria_source.py`: v2 문장 묶음에 위치 경계 문장 3개 추가, 정본 쪽 존재 확인, 기록된 sha256가 문장과 일치하는지 확인하는 시험 1개 추가.

## 검증
- test_label_* / test_mobile_corner* / test_corner_label* / test_corner_import_states / test_agent_document* / test_self_agreement*: 211개 통과(`PYTHONPATH=. python -m unittest discover -s tests -p <패턴>`).
- 결함 주입 3건(화면 쪽 위치 경계 문장의 글자 변경): 모두 시험 실패 확인 후 원복.
- 실제 라벨 화면 생성·발급, 사진 처리, 학습·추론·실험, 외부 AI 호출 없음.

## 롤백
`git revert <이 브랜치 커밋>` 또는 브랜치·worktree 삭제. main에 아무것도 반영되지 않았다.
