# 동결 평가 JSON과 SHA의 동일 바이트 해석

진척30/100(usable-card-analysis-v1.0), 이번+0점. candidate/report/receipt의 SHA를 검사한 바이트로 JSON을 해석한다. 모델 성능 실험은 수행하지 않았다.

검증 소스 main ddd93db + 검사보완 c3c6025. 원본계약2cd676b/구현48cfe73/계약추가a04f141/검사보완bc24616.

## 변경 파일·핵심 diff
- card_condition/evaluation_suite_inputs.py: candidate/report/receipt 각각 read_bytes snapshot을 SHA검사와 json.loads에 재사용. hash 뒤 read_text로 다시 여는 경로 제거. 기존 필드검사/입력최종불변/점수·정답/one-use 의미 유지.
- tests/test_frozen_report_loaded_bytes.py: original SHA 뒤 다른 JSON의 marker가 반영되던 반례, 세 JSON재개방차단, 실제변경pin거절 3검사.
- tests/test_evaluation_output_safety.py: NaN mock을 정상복구 후 ENOSPC주입; json.dump가 실제호출됐는지 검증. publisher에 NaN부분쓰기 실패를 직접주입해 임시파일정리 확인. 함수추가 없음.
- task 및 이 보고서.

## 실제 검증
- 수정 전 기존 source에서 SHA뒤 read_text 대체로 unpinned race_marker accepted 재현. 수정 후 원래snapshot만 found에 남음.
- worktree 신규3 PASS0.344s, output safety5 PASS0.139s.
- main 기존126+신규3=129 PASS24.427s. 추가 release/listing/API/input consistency/provenance/identity/output safety/point compatibility/benchmark mock 10모듈34검사 최초2오류(점수NaN을 복구하지 않고 ENOSPC로 진입하려던 fixture). guard완화 없이 fixture독립화 후34 PASS2.069s. 서로 다른163검사 통과, 단일163개 runner 실행을 주장하지 않는다.
- AST source2/newtest5/outputtest7, compileall/diff PASS. 기존함수/호출깊이 유지.
- 합성 랜덤 모델 forward·mock만 포함, 실제사진 추론·새학습·외부AI0. 실제 FN/FP/일반화/독립성/절감 미측정.

## 리스크·한계
JSON 원본 snapshot을 해석 동안 메모리에 보유한다. 대형 실보고서 메모리 실측은 하지 않았다. JSON/필드계약은 동일하며 과거보고서/원본사진/정답/모델은 변경하지 않았다. 같은 byte snapshot은 파일 무결성의 근거이며 사람 정답/실물그룹/선택독립성을 보증하지 않는다. progress/verified/운영routing 불변.

## 롤백
기능 git revert ddd93db. 검사보완도 원복하려면 git revert c3c6025(이 경우 넓힌 NaN/ENOSPC 회귀의 기존 실패가 돌아옴). 관련 검사 후 일반push. history재작성/force 없음.
HTML artifacts/frozen-report-loaded-bytes-20261026/index.html. 열기요청/렌더 구분.

열기도구queued, 요청전달·실제렌더미확인.
