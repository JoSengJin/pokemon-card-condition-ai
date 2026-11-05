task_id: unsupported-truth-identity-20261026
owner: Codex
status: integrated
base_sha: b293080b1f0c7c798c7564bed5ba2d895d111b33
branch: codex/unsupported-truth-identity-20261026
goal: 모델 미지원 질문의 source 수량에도 동일사진/면/구역/질문 known truth 중복을 거절해 D1 분모 팽창을 방지한다.
allowed_files:
- card_condition/evaluation_suite_inputs.py
- tests/test_unsupported_truth_identity.py
- docs/collaboration/tasks/unsupported-truth-identity-20261026.md
- docs/collaboration/reports/unsupported-truth-identity-20261026.md
- ignored artifacts/unsupported-truth-identity-20261026/index.html
forbidden_files: 다른 소스/사진·정답/기존 sealed 기록/모델/진척·기준/Claude 파일
contract: checked_predictions의 known truth 중복 키 검사 대상을 supported에서 고정 QUESTIONS 전체로 확장한다. 실제 score 지원 검사는 기존대로 supported만 허용한다. unknown은 정상이나 중복known으로 바꾸지 않는다. 같은 source ID 중복과 사진 양면충돌은 기존 거절 유지. 다른 사진/구역/질문은 별개다. 사진 SHA는 caller의 검증 source mapping 우선. 자동 dedup·truth 수정 없음.
structure: evaluation_suite_inputs2→2, 새 test<=7. 기존 루프 대상만 변경하여 호출깊이 증가 없음.
checks: 수정 전 unsupported edge known alias2행 accepted 재현. 미지원known alias·상충truth·source photo mapping·unknown·다른질문·다른사진·score지원 유지 회귀 + 기존121; AST/compile/diff/HTML/main push.
experiment: 없음. 합성 JSON/projection 검사이며 모델 학습·실사진 추론·외부 AI 호출 없음.
handoff: 파일/diff/실검사/미검증/리스크/롤백/HTML/원격.진척30/100 유지.

완료:cc376c9.126합성회귀PASS24.336s.진척30/100. 보고서에리스크·롤백.
