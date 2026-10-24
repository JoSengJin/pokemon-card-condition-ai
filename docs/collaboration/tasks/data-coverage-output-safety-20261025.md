# 감사 출력 실패 안전성

- task_id: data-coverage-output-safety-20261025
- owner: Codex
- status: assigned
- base_sha: df899e695fd48143d10797136025ca8f7551a454
- branch: codex/data-coverage-output-safety-20261025

## 목표

합성 OSError 재현에서 현재 data_coverage는 최종 경로에 부분 JSON을 남긴다. 완성된 JSON만 최종 경로에 공개하고, 저장 실패 시 재시도가 가능하며 이미 존재하거나 경쟁자가 만든 보고서는 덮어쓰지 않게 한다. 보고서 내용·집계·라벨은 보존한다.

## allowed_files

- card_condition/data_coverage.py
- tests/test_data_coverage_output_safety.py (신규)
- docs/collaboration/tasks/data-coverage-output-safety-20261025.md
- docs/collaboration/reports/data-coverage-output-safety-20261025.md (신규)

Claude의 side-evidence-contract 두 문서와 pair-control 작업은 수정하지 않는다. 다른 writer로 범위를 넓히지 않는다.

## checks와 계약

표준 라이브러리 tempfile와 동일 디렉터리 hardlink로 완성 파일을 덮어쓰기 없이 공개한다. 임시 파일 쓰기 실패/공개 실패/기존 출력/경쟁 출력/정상 출력을 합성 fixture로 검사한다. 소스 편집은 독립 worktree의 ./develop 안에서 수행한다. 통합 checkout에서 기존 49개 관련 테스트와 신규 테스트를 실행하고 기존 development/live 감사 JSON 전체와 비교한다. 학습·추론·외부 AI 0회. 독립 worktree는 표준 라이브러리 환경이므로 의존성 필요한 테스트는 main 통합 후 실행한다.

## 리스크와 롤백

hardlink 미지원 파일시스템은 안전하게 실패한다. 전원 상실까지의 내구성이나 SIGKILL 후 임시 파일 정리를 보장하지 않는다. 통합 소스 커밋 revert. 원본 데이터·모델·진척 점수 불변.
