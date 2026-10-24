# Claude 다음 묶음: 근거 snapshot 무결성 및 sidecar 준비

- task_id: `evidence-snapshot-preparation-batch-20261025`
- owner: Claude
- status: implementing
- base_sha: `1a6fa8f5cf1a120c8b7cdd30abdf6041676a50c6`
- branch: `claude/evidence-snapshot-preparation-batch-20261025`
- worktree: 로컬 경로와 dispatch SHA는 Codex 메시지에서 제공

## 완료 목표

이미 통합된 v0.1 검증기에 **검사 가능한 근거 묶음과 미조사 입력을 준비하는 도구**를 추가한다. 실제 source 의미 검증을 했다고 주장하지 않는다. 파일 무결성 검사·선택한 inventory의 미조사 sidecar 준비·기존 검증기 연결·실제 59파일 읽기 전용 실행을 한 묶음으로 끝낸다. 단계마다 커밋 후 다음 독립 단계를 계속한다.

기존 코드의 source/origin/면 판단/집계 계약은 유지한다. 과거 작업의 자동 생성 금지는 기존 검증기의 범위 제한이었다. 이번 계약은 사용자가 명시한 단일 inventory에서 모든 행을 not_reviewed로 준비하는 별도 선택 실행 도구만 허용한다. 기존 sidecar 자동 변환·덮어쓰기·일괄 근거 추론은 허용하지 않는다.

## allowed_files (정확히 9개)

- `card_condition/evidence_snapshot.py` (신규: index 및 payload 바이트 무결성 검사)
- `card_condition/evidence_snapshot_cli.py` (신규: 독립 검사 CLI)
- `card_condition/side_evidence_prepare.py` (신규: 미조사 scaffold API와 독립 CLI)
- `tests/test_evidence_snapshot.py` (신규)
- `tests/test_evidence_snapshot_cli.py` (신규)
- `tests/test_side_evidence_prepare.py` (신규)
- `tests/test_evidence_preparation_flow.py` (신규)
- `docs/collaboration/tasks/evidence-snapshot-preparation-batch-20261025.md`
- `docs/collaboration/reports/evidence-snapshot-preparation-batch-20261025.md` (신규)

그 외 추적 파일은 읽기 전용이다. 특히 side_evidence.py/side_evidence_cli.py/기존 테스트/공용 CLI/pyproject/관제 UI/데이터/진척률은 수정하지 않는다. 기존 코드의 결함이 새 반례로 확인되면 재현과 최소 제안만 보고하고 그 항목만 보류한다. 다른 worktree·브랜치·원본 자료는 조작하지 않는다.

## 근거와 환경

자체 .venv는 표준 라이브러리만 사용한다. card_condition import가 현재 worktree인지 확인한다. source 편집은 ./develop -- <실제 수정 명령> 안에서 한다. 새 의존성/모델 설치/다른 환경 공유 없음.

Codex가 `artifacts/collaboration/evidence-snapshot-preparation-batch-20261025/evidence/`에 직전 source-followup의 index.json 및 payload 59개를 물리 복사·SHA 대조해 제공한다. 전체는 Git 제외·읽기 전용이며 사진·모델·키가 없다. 로컬 절대경로가 파일 안에 있어도 문자열로만 취급한다. SHA 검사를 위해 payload 바이트만 읽으며 사진을 열거나 라벨 정답을 해석하지 않는다. 테스트는 합성 fixture만 사용하고 실자료는 최종 smoke 실행에서만 사용한다.

## 1. 최소 API·출력 계약 고정

최종 보고서에 구현 전에 API·CLI·반례 기준을 적는다.

- `audit_snapshot(index_path, evidence_root)` -> JSON 직렬화 가능한 보고 dict. `index_path`는 호출자가 명시한 index 파일이며 payload는 evidence_root 아래로만 제한한다. index를 한 번 읽은 바이트의 SHA와 파싱 결과로 검사한다.
- index의 `entries` 각 항목은 `original_relative_path`, `snapshot_path`, `sha256`, `kind`를 가진다. 실제 제공 index와 합성 fixture의 호환 범위를 명시한다. top-level task_id/dispatch_sha/missing/photos_copied/models_copied/keys_copied의 기존 메타데이터를 임의 해석·승인 정보로 사용하지 않는다.
- 각 경로는 기존 relative_parts의 정규형 안전 조건을 재사용한다. snapshot payload는 root 아래 일반 파일만 읽는다. 밖으로 나가는 symlink·디렉터리·특수 파일·..·절대경로를 거절한다. 기존 원본 경로를 찾아 나가지 않는다.
- payload는 .json/.jsonl/.md의 바이트 SHA만 검사한다. JSONL의 id 유무나 Markdown 내용은 검사하지 않는다. 원본 의미나 test split의 정답을 해석하지 않는다. 사진·모델·키 등 미지원 파일은 읽지 않고 거절한다.
- 동일 original_relative_path 중복·서로 다른 SHA/경로 연결·동일 snapshot_path의 모호한 다중 연결을 거절한다. 같은 root 안 symlink 별칭과 hardlink의 중복 여부도 식별하여 동일 payload를 별개 원본처럼 세지 않는다. 반복 항목을 조용히 set으로 지워 통과시키지 않는다. 바이트가 같은 별개 파일이 독립 증거라고 주장하지 않는다.
- 누락·SHA 불일치·안전하지 않은 경로는 성공 보고로 삼지 않는다. 알려진 index.missing은 payload 검증 성공과 분리해 보고한다. 이를 파일을 찾아 채웠다고 해석하지 않는다. 무결성 통과는 원본 정답/검색 완전성/59개 독립성 증명이 아니다.
- 보고서는 상대경로·SHA·개수·index가 선언한 missing 항목의 요약만 포함한다. 사람 응답·라벨 값·절대경로·키를 복사하지 않는다. 오류 코드와 CLI 종료코드를 간결히 명시한다. 수치 개수로 의미 품질 점수를 만들지 않는다.

## 2. snapshot 감사 및 변조 회귀 구현

실제 임시 파일의 바이트로 정상 묶음·payload 없음·index stale SHA·payload 변조·중복·별칭·경로 이탈·FIFO를 검사한다. 한 파일을 JSON/JSONL 별칭으로 바꿔 검사 우회가 생기지 않는지 검증한다. payload는 내용 파싱 대신 해시만 검사하므로 형식 파싱 지원으로 오해하지 않게 문서화한다. 미래 TOCTOU 방어 프레임워크는 추가하지 않는다. 검사 당시 한 번 읽은 바이트와 정적 경로 검증이라는 한계를 기록한다.

## 3. 미조사 sidecar 준비 API·CLI

- API: `prepare_sidecar(inventory_path, evidence_root, rows_pointer, search_index=None)` -> v0.1 sidecar dict. 경로 인자는 root 아래 안전한 상대경로이고 rows_pointer는 기존 JSON Pointer 해석을 재사용한다.
- 선택한 inventory의 SHA·id·image_sha256·side만 결합에 사용한다. 결함 target/box/point를 출력하거나 의미를 해석하지 않는다. 중복 id·잘못된 이미지 SHA/side·목록 아닌 pointer를 거절한다. 이미지·원본 참조 파일을 열지 않는다.
- 모든 행은 status=not_reviewed, evidence=[], missing_sources=[], searched_no_side_evidence=false, human_side_origins=0/side_basis=not_reviewed다. 입력의 기존 human_evidence/side를 읽고 reviewed로 승격하지 않는다. side_claim은 기존 side 또는 null만 복사한다.
- schema는 기존 side_evidence_sidecar/v0.1. search_index가 명시되면 그 상대경로/SHA만 search_scope에 기록한다. payload 검색이나 근거 자동 채움은 하지 않는다. 자동 버전 마이그레이션·기존 sidecar 합치기 없음.
- 반환 sidecar를 기존 check_structure/validate_sidecar와 대조해 호환성을 확인한다. 기존 API 수정 없음. scaffold 생성 자체를 자료 검토나 증거 확보로 보고하지 않는다.
- 독립 CLI: python -m card_condition.side_evidence_prepare --inventory REL --evidence-root ROOT --rows-pointer POINTER [--search-index REL] --output NEW. 공용 CLI에 연결하지 않는다.

## 4. 독립 CLI·입력 보존·실패 검사

snapshot CLI: python -m card_condition.evidence_snapshot_cli --index INDEX --evidence-root ROOT --output NEW.

둘 다 출력은 사용자가 명시한 새 JSON 한 개다. 기존 side_evidence_cli.write_new를 그대로 재사용할 수 있는지 확인하고, 재사용 가능하면 복사·범용 abstraction 추가를 피한다. 기존 모듈을 수정하지 않는다. 기존/경쟁 출력 보존·부분 쓰기/flush/link 실패·임시 파일 정리·재시도를 검증한다. 새 wrapper 동작과 연결을 검사하되 기존 writer 구현을 그대로 베끼는 무의미한 검사만 늘리지 않는다. 입력 inventory/index/payload 전후 SHA/바이트 동일 확인. stderr는 원문·홈 절대경로를 노출하지 않는 짧은 메시지다.

## 5. end-to-end 및 실제 묶음 smoke

합성 fixture로 audit → prepare → 기존 side_evidence_cli 검증을 실제 파일/CLI로 이어 실행한다. 변경 입력을 넣으면 올바른 단계에서 거절되는지 확인한다. schema·코드의 출처 선언과 사람이 검증한 의미를 구분한다.

실제 root: artifacts/collaboration/evidence-snapshot-preparation-batch-20261025/evidence. index.json의 59 entries를 검사하고, `sources/artifacts/data-coverage-20261024/supplemental-inventory.json`의 `/latest_supplements`로 scaffold를 만든 뒤 기존 검증기로 검증한다. search_index는 index.json을 명시한다. 59개와 6행은 사전 기대값일 뿐이며 실제가 다르면 성공으로 보정하지 말고 차이를 기록한다. 기존 면·정답·수량 변경 0, 모두 not_reviewed여야 한다.

실자료 산출물은 동명 작업의 artifacts 하위 새 경로에 저장하고 Git에 넣지 않는다. 원본 snapshot은 chmod를 바꾸거나 덮어쓰지 않는다. 입력 모두 SHA 불변을 확인한다. 실제 source/origin 의미 검증·새 사람 라벨은 0이다. 준비·검사 경로가 바뀌었다고 모델 품질 개선을 주장하지 않는다.

## 6. 반례 검토·최종 인계

최소 한 번 코드를 읽고 우회 입력을 시도한다. 재현된 결함은 실패 검사부터 남기고 최소 수정한다. mutation은 위험한 분기 몇 개에 한해 임시 복사본에서만 가능하며 성공 수 채우기를 위해 반복하지 않는다. 원본 checkout이나 범위 밖 파일은 바꾸지 않는다.

표준 검증:

```sh
PYTHONPATH=tests .venv/bin/python -m unittest test_evidence_snapshot test_evidence_snapshot_cli test_side_evidence_prepare test_evidence_preparation_flow test_side_evidence test_side_evidence_sources test_side_evidence_cli -v
.venv/bin/python -m compileall -q card_condition/evidence_snapshot.py card_condition/evidence_snapshot_cli.py card_condition/side_evidence_prepare.py
git diff --check
```

기존 ML 의존 55개는 main 통합 후 Codex 몫이다. Claude는 실행한 테스트 명령/개수·실제59파일/6행 결과·미검증·리스크·롤백·전체 커밋 순서를 보고서와 task에 적고 ready_for_review로 인계한다. raw 사람 원문·개인 경로·실제 데이터·키를 Git에 추가하지 않는다.

## 금지·종료·롤백

학습/사진 추론/외부 AI/Codex CLI/review --auto/라벨 변경/완료 라벨 재질문/모델 다운로드/자동 수집/관제 UI/main merge/push 금지. 진척 30/100·배점 불변. 의미 결정에 막힌 항목만 기록하고 독립 단계를 계속한다. 6단계 완료 또는 실제 권한·컨텍스트 한계에서 체크포인트를 남긴다. 단계가 끝났다는 이유로 임의 기능을 추가하지 않는다.

커밋은 feat/test/fix/docs(scope): 내용. 전체 git add . 금지. 롤백은 미통합 또는 전달 커밋 역순 revert이며 입력 데이터·모델 복구는 필요 없어야 한다. 파일 무결성 검사는 원본 진실성·독립성 검증이 아니다. hardlink/강제 종료/정적 경로 검사 한계를 그대로 밝힌다.
