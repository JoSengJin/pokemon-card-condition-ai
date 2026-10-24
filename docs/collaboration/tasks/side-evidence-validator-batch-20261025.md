# Claude 장시간 작업: 면 근거 sidecar 검증기

- task_id: `side-evidence-validator-batch-20261025`
- owner: Claude
- status: ready_for_review
- base_sha: `357891e1435076378a85b695c7027c9769d871b0` (아래 기준 안내 참조)
- branch: `claude/side-evidence-validator-batch-20261025`
- worktree: Codex 전달 메시지에서만 로컬 경로 제공

## 목표와 범위

직전 side-evidence-contract 보고서를 실제로 재현 가능한 **독립·선택 실행 검증기**로 만든다. 장시간 작업 중 단계마다 커밋하며 이 문서의 작업 묶음을 끝까지 처리한다. 토큰을 소진하는 것이 목표가 아니다. 성공은 합성 입력의 문서 A1–A3/R1–R12와 아래 신뢰 경계를 실행 가능한 회귀 검사로 증명하는 것이다. 운영 채택·실제 라벨 감사·모델 성능 향상은 범위 밖이다.

시작 기준은 이 문서의 base_sha 전체 SHA이며, dispatch 커밋은 Codex 전달 메시지로 확인한다. 출처 감사·pair-control 등 완료 브랜치를 재사용하지 않는다.

## allowed_files (정확히 7개)

- `card_condition/side_evidence.py` (신규: 표준 라이브러리 검증 함수)
- `card_condition/side_evidence_cli.py` (신규: 독립 모듈 CLI)
- `tests/test_side_evidence.py` (신규: 구조·요약·보존)
- `tests/test_side_evidence_sources.py` (신규: SHA·파일·참조·경로)
- `tests/test_side_evidence_cli.py` (신규: 명령행·출력·오류)
- `docs/collaboration/tasks/side-evidence-validator-batch-20261025.md`
- `docs/collaboration/reports/side-evidence-validator-batch-20261025.md` (신규: 최종 계약·실행例·검사·인계)

그 밖의 추적 파일은 읽기 전용이다.기존 cli.py/data_coverage.py/point_dataset.py/pyproject.toml/PAIR_CODING.md/AGENTS.md/진척률/관제 UI는 변경하지 않는다. 기존 보고서와 prompt 문서도 덮어쓰지 않는다. 범위 안의 재현된 버그는 수정·검증을 계속하되, 범위 확대가 필요하면 그 항목만 blocked로 기록하고 독립 단계는 이어간다.

## 작업 묶음과 단계별 완료 조건

### 1. 검증 전용 기술 계약 고정

직전 초안과 Codex 보정을 읽고 최종 보고서에 최소 v0.1 계약을 먼저 적는다. 초안 예시는 합성이고 실행 가능한 원본이 아니다. 필드 변경은 diff와 이유를 남기며 과거 보고서는 보존한다.

- API: `validate_sidecar(sidecar_path, evidence_root)` -> JSON 직렬화 가능한 검증 보고 dict. 외부 입력 문제는 ValueError/OSError로 실패시키며 문서화한다. 코드 결함은 성공으로 숨기지 않는다.
- CLI: `.venv/bin/python -m card_condition.side_evidence_cli --sidecar INPUT --evidence-root ROOT --output NEW_JSON`. 기존 공용 CLI에 연결하지 않는다.
- schema는 `side_evidence_sidecar/v0.1`; 초안 자동 변환은 하지 않는다. 예시·fixture는 실제 파일 바이트의 SHA로 생성한다.
- root 아래 상대경로만 읽는다. 절대경로·..·root 밖으로 빠지는 symlink·특수 파일은 거절한다. 파일 경로를 셸/네트워크에 전달하지 않는다. 입력 파일은 한 번 읽은 바이트로 SHA와 파싱을 함께 수행한다. 적대적 동시 파일 교체까지 방어한다고 주장하지 않는다.
- inventory 행 목록은 명시된 rows_pointer로 선택한다. 행 식별자는 실제 inventory와 맞춰 `id`, 이미지 식별은 `image_sha256`, 기존 면은 `side`(없으면 null). sidecar의 row_id/image_sha256/side_claim과 대조한다. 중복 inventory ID와 sidecar ID, 잘못된 필드 타입·미지원 schema/type·예상 밖의 정답 변경 필드를 거절한다. `decoded_sha256`와 파일 SHA를 혼용하지 않는다. inventory 전체 행을 sidecar에 넣도록 강제하지 않는다.
- 참조는 JSON/JSONL만 지원한다. JSON은 문서 루트 기준 pointer, JSONL은 유일한 `id`와 일치하는 row_id 선택 후 pointer. JSONL 누락·중복 ID와 미지원 파일 형식은 명시적으로 실패한다. JSON Pointer의 ~0/~1, 배열 인덱스, 누락/잘못된 escape를 합성 검사한다. 빈 pointer의 루트 선택 여부도 명시한다. Markdown 사람 문장의 의미를 자동 추론하지 않는다.
- source/origin 둘 다 SHA와 참조 존재를 검증한다. 파생 관계는 선언 정보이며, 값 일치·해시 일치만으로 독립 사람 판단이나 원본의 진실성을 증명하지 않는다. 보고서에 `semantic_verification: false`를 고정하고 origins는 선언된 원본 위치의 중복 제거 수라고 명시한다. 검증기가 면 진술을 텍스트에서 자동 추출하거나 거짓 origin을 판별한다고 주장하지 않는다.
- missing_sources는 경로 참조가 실제 referenced_by 값에 있는지, 대상이 root 내부에 없음을 대조한다. snapshot 밖 파일을 찾아 나가지 않는다. source/origin이 없는데 missing_sources로 우회해 유효 근거로 세지 않는다. search_scope SHA를 검사하되 검색의 완전성은 증명하지 않는다.
- anchor/slot은 이번 버전에서 evidence 목록에 유지하되 슬롯은 asserts_side=false를 강제한다. 근거는 declared claims라는 경계를 보존한다.
- side 충돌/서로 다른 사람 진술은 그대로 보고하고 어떤 면도 고르지 않는다. A3/primary/수량 판정 경로에는 연결하지 않는다. 충돌 해결과 A3 정책은 사람 결정으로 남긴다.
- 출력은 별도 새 JSON만 작성한다. 원본 inventory/sidecar/근거/집계/라벨을 절대 수정하지 않는다. 저장 위치는 사용자가 명시하고 기존 파일은 덮어쓰지 않는다. inventory 변경 시 SHA 불일치로 거절하며 자동 마이그레이션/일괄 sidecar 생성은 하지 않는다. 작성자 신원 인증은 범위 밖이다.

### 2. 구조·요약 검증기와 단위 테스트

not_reviewed/reviewed·missing/search 결과 분리, 근거 유형 혼합, summary 재계산, slot 제약, side 충돌/복수 진술, 파생 사본 중복 계산을 구현한다. 타입 검사는 Python bool과 int 혼동을 막고 null/빈 목록/잘못된 side 값을 검사한다. 원본의 결함 정답·point·box를 해석하거나 바꾸지 않는다. 테스트는 임시 디렉터리와 합성 JSON/JSONL만 쓴다.

### 3. 외부 참조 검증과 반례 테스트

A1–A3와 R1–R12 각각을 실제 합성 파일로 검증한다. 이전에 미검증이던 R1/R2/R9/R10/R11도 fixture의 파일 바이트·SHA·실제 참조로 실행한다. source는 맞고 origin만 틀린 경우, origin pointer 누락, row ID 중복, 다른 inventory 이미지/side 결합, 참조 안 된 missing 경로, 존재하는 원본을 missing으로 선언, stale search index, ..·절대경로·symlink 이탈을 포함한다. SHA가 같아도 인간 의미 검증이 아니라는 예시도 기록한다. 통계적 독립성은 테스트로 입증했다고 쓰지 않는다.

### 4. 독립 CLI와 파일 보존·실패 회귀

입출력 정상 동작, 오류 종료코드와 간결한 stderr, 기존 출력 보존, 경쟁 출력 보존, 부분 쓰기 오류 후 최종 파일 없음/재시도 가능을 검사한다. 기존 data_coverage의 저장 방식은 읽어 참고하되 수정하지 않는다. 표준 라이브러리의 같은 폴더 임시 파일과 덮어쓰기 없는 공개를 이용한다. 범용 writer 추상화나 새 의존성을 추가하지 않는다. 원본 모든 fixture의 전후 바이트/SHA가 같은 것을 확인한다. 보고 JSON에는 원문 사람 답변·비밀값·홈 절대경로를 복사하지 않는다.

### 5. 자체 반례 검토·최종 인계

구현을 읽고 규칙 우회를 시도한다. 각 재현된 결함은 먼저 실패하는 검사로 남긴 뒤 최소 수정한다. 검토 횟수 채우기·같은 성공 검사 반복·허용 범위 밖 개선은 하지 않는다. 반례가 없으면 그대로 기록한다.

최종 보고서에는 최종 schema/API/CLI·합성 실행例·A/R 사례별 실제 test 이름/결과·미구현 의미 경계·변경 파일·리스크·롤백을 적는다. status ready_for_review로 바꾸고 단계별 전체 SHA 순서·부모·검사 명령·통과 개수·미실행 항목을 인계한다. main merge/push는 Codex가 한다.

## 실행 환경·검사

자체 .venv는 표준 라이브러리만으로 충분하다. import card_condition 경로가 자기 worktree인지 확인한다. torch/Pillow/모델 다운로드·다른 worktree 환경 공유·editable 공용 설치 없음. 모든 소스 편집은 `./develop -- <실제 수정 명령>` 안에서 한다.

```sh
PYTHONPATH=tests .venv/bin/python -m unittest test_side_evidence test_side_evidence_sources test_side_evidence_cli -v
.venv/bin/python -m compileall -q card_condition/side_evidence.py card_condition/side_evidence_cli.py
git diff --check
```

기존 55개 ML 의존 테스트는 Codex가 main 통합 후 실행한다. Claude는 실행하지 않은 것을 통과로 기록하지 않는다. 실제 사진·라벨·snapshot·test split·수집기·학습·모델 추론·Gemini/Codex CLI/외부 AI 호출·review --auto는 모두 금지한다. 사용자는 수면 중이므로 새 사람 라벨/승인을 요청하거나 임의로 채우지 않는다. 필요 결정이 있으면 해당 항목만 보류하고 나머지를 끝낸다.

## 커밋·종료·롤백

단계별 의미 단위로 feat/test/fix/docs(scope): 내용 형식으로 커밋한다. task/result 문서만 갱신하며 같은 파일의 타 작업 변경을 덮어쓰지 않는다. 전체 git add . 금지. 깨끗한 작업 트리로 인계한다. 이 5개 단계의 수용 조건 충족 또는 실제 권한/근거/컨텍스트 한계에서 체크포인트를 남긴다. 작업을 늘리려고 모델 실험·임의 기능을 시작하지 않는다. 장시간 상시 실행·자동 깨우기를 설정하지 않는다.

리스크: 도구는 구조·파일 일치 검증이지 사람 의미/독립성 보증이 아니다. hardlink 미지원 저장 실패·강제 종료 임시 파일 잔존은 명시한다. 롤백은 미통합 또는 전달 커밋을 역순 revert. 실제 데이터·모델은 바뀌지 않는다. 진척 점수 30/100/배점/기준 불변.

## Claude 실행 결과

2026-10-25, 배정 worktree에서 실행. 상세: `docs/collaboration/reports/side-evidence-validator-batch-20261025.md`.

- 기준:
  - 브랜치 `claude/side-evidence-validator-batch-20261025`, 시작 HEAD `7e61e150696432e83c730899e8e889185552ae4a`.
  - `merge-base --is-ancestor 357891e… HEAD` 종료코드 0. 시작 시 작업 트리가 깨끗했다.
  - base 이후 Codex 변경은 prompt·task 문서뿐이었다.
- 단계별 커밋(순서대로):
  1. `aa0c95093c60ff623d006e58d60dc12159945f4f` docs: v0.1 계약
  2. `f42aca44babab59b5f20afbee346a77429d0087c` feat: 구조·요약 검증
  3. `a3da1d84dece21f644f03f3d3ba39d42e926637e` feat: 원본 SHA·참조·경로 대조
  4. `662c34850bef5d816d7eee2f04afd2a6b4be46f8` feat: 독립 CLI·출력 보존
  5. `1bc6303d7d9b2d45c26ed78e96b1dc3b17d88128` test: 자체 반례 3건(당시 실패 3·오류 1)
  6. `b45349e15a8cac767133c08ad652669160a8de21` fix: 반례 최소 수정
  7. 이 문서 커밋(docs: 최종 보고·인계)
- 검사:
  - `PYTHONPATH=tests .venv/bin/python -m unittest test_side_evidence test_side_evidence_sources test_side_evidence_cli -v` → 48개 통과(구조 16, 원본 대조 23, CLI 9), 종료코드 0.
  - `compileall` 종료코드 0. `git diff --check` 통과.
  - mutation 14가지 모두 검출(살아남은 변형 0).
- 미실행:
  - 기존 ML 의존 테스트 55개(Codex 통합 후. 이 venv에는 torch가 없다)
  - 실제 inventory·snapshot 대상 실행
  - 학습·추론·사진 열람·외부 AI 호출
- 미해결(사람·Codex 결정):
  - sidecar 저장 위치·작성자·버전 정책
  - 한 응답이 여러 사진을 다룰 때 사진별 대응
  - anchor·slot을 evidence에서 context로 분리할지
  - 충돌을 경고로 둘지 A3 차단으로 둘지
  - snapshot 밖 원본 참조 정책
- 리스크:
  - 구조·파일 일치 검증일 뿐 의미·독립성 보증이 아니다(`semantic_verification: false`).
  - hardlink 미지원 파일 시스템에서는 저장이 실패한다.
  - 강제 종료 시 임시 파일이 남을 수 있다.
  - TOCTOU(검사와 open 사이의 파일 교체)는 막지 않는다.
- 롤백: 미통합이면 반영하지 않는다. 통합 후에는 위 커밋을 역순으로 revert한다. 신규 파일만 추가했으며 데이터·모델·진척률 30/100은 바뀌지 않는다.
