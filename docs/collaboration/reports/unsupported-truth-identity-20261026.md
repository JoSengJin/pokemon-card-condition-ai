# 미지원 질문 source 중복 보호

진척 30/100(usable-card-analysis-v1.0), 이번 +0점. 모델 미지원 질문의 정답 수량에도 사진·면·구역·질문 중복 방지를 적용했다. 모델 품질 미측정.

검증 코드 maincc376c9, 원본계약0e09750/구현ee3dcc0.

## 변경 파일·diff
- card_condition/evaluation_suite_inputs.py: known truth 중복 키 검사 loop의 supported를 고정 QUESTIONS로 변경. 점수 지원 범위 검사는 기존 supported 유지. 미지원이라도 D1 source 정답 수량에 쓰는 단위는 중복 불가.
- tests/test_unsupported_truth_identity.py: 동일·상충truth alias/source 사진SHA 우선/unknown 보존/다른사진·구역·질문/점수지원 검사5개. task/이보고서 추가.

## 실제 검증
- 수정 전 corner만 지원하는 모델에서 known edge alias2행 accepted 재현.
- 수정 후 known 미지원 alias와 상충 truth 모두 거절, 자동 dedup/truth수정0. unknown alias는 unknown 유지, known양성1/unavailable1로 보존.
- worktree stdlib unit5 PASS0.001s.
- base PYTHONPATH=tests .venv/bin/python runner: 기존121+신규5=126 PASS24.336s, torch threads1. 기존합성 랜덤 모델forward/mock외 실사진 추론·새학습·외부AI0.
- AST source2/test5, compile/diff 확인. 기존루프만 변경하여 호출깊이 증가 없음.
- 실제 FN/FP·독립 일반화·운영 절감은 미측정. 진척/기준/원본사진·정답/기존기록 불변.

## 리스크·롤백
미지원known 중복을 포함한 과거 source projection은 이제 assessment에서 거절한다. 기존 보고서는 변경하지 않고 원본 identity를 검토해야 한다. 임의로 정답을 삭제/변경하지 않는다. 같은 source mapping과 다른 unit들은 기존대로 허용한다.
롤백: git revert cc376c9, 관련회귀 재실행 후 일반push.
HTML artifacts/unsupported-truth-identity-20261026/index.html, 열기와 렌더 구분.

compile/AST/diff PASS. 열기도구queued, 요청전달·렌더미확인.
