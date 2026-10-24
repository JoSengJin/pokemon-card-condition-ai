# 근거 snapshot 무결성 검사와 미조사 sidecar 준비 — 2026-10-25

task `evidence-snapshot-preparation-batch-20261025`. 기준은 base `1a6fa8f5cf1a120c8b7cdd30abdf6041676a50c6`이고 시작 HEAD는 `acf1b6e57544ba4eb887a94738b6467bc89cdb06`이다.

이번 묶음은 두 도구를 더한다. 둘 다 독립·선택 실행 도구다.
- 파일 바이트의 무결성 검사기
- 모든 행을 `not_reviewed`로 둔 sidecar 준비기

source·origin의 의미, 사람 정답, 면, 검색 완전성, 근거 독립성은 검증하지 않는다. scaffold 생성은 자료 검토나 증거 확보가 아니다. 학습·추론·사진 열람·외부 AI 호출은 0회이며 진척률 30/100은 그대로다.

## 1. API·CLI·반례 기준 (구현 전 고정)

### snapshot 무결성 검사

- `card_condition.evidence_snapshot.audit_snapshot(index_path, evidence_root) -> dict`
  - `index_path`는 호출자가 지정한 index 파일이다. 한 번 읽은 바이트로 SHA256과 엄격한 JSON 파싱(기존 `parse_bytes`: 중복 키·NaN·깊은 중첩 거절)을 함께 수행한다.
  - payload는 `evidence_root` 아래로만 제한한다.
- index 호환 범위:
  - 최상위는 객체이고 `entries`는 비어 있지 않은 목록이다.
  - 각 entry는 정확히 `original_relative_path`, `snapshot_path`, `sha256`, `kind` 네 키를 가진다.
  - `kind`는 비어 있지 않은 문자열이며 개수만 센다. 승인 여부 등 의미로 해석하지 않는다.
  - `missing`이 있으면 목록이어야 한다. 그 개수는 payload 검증 결과와 분리해 `declared_missing`으로 보고한다. 누락 파일을 찾거나 채우지 않는다.
  - 그 밖의 최상위 키(`task_id`·`dispatch_sha`·`photos_copied`·`models_copied`·`keys_copied` 등)는 해석하거나 승인 정보로 쓰지 않는다. 이름만 `ignored_metadata_keys`로 보고한다.
- 경로:
  - `original_relative_path`와 `snapshot_path` 모두 기존 `relative_parts`의 정규형 안전 조건을 쓴다.
  - `original_relative_path`는 문자열로만 다루고 찾아가지 않는다.
  - `snapshot_path`는 realpath가 root 안의 일반 파일이어야 한다. 디렉터리·FIFO·root 밖 symlink는 거절한다.
- payload:
  - 확장자는 `.json`·`.jsonl`·`.md`만 허용한다. 그 밖(사진·모델·키 등)은 파일을 열기 전에 거절한다.
  - 내용은 파싱하지 않고 바이트 SHA만 대조한다. 형식이 깨진 JSON도 SHA가 맞으면 통과하며, 이는 형식 검증이 아니다.
- 중복·별칭은 조용히 지우지 않고 거절한다.
  - 같은 `original_relative_path`가 반복되거나(같은 내용의 반복 포함), 같은 `snapshot_path`가 여러 entry에 연결되면 거절한다.
  - 서로 다른 `snapshot_path`가 같은 realpath(symlink 별칭, `.json`↔`.jsonl` 별칭 포함)나 같은 `(st_dev, st_ino)`(hardlink)를 가리키면 거절한다.
  - index 파일 자신이 payload로 등재되어도 거절한다.
  - 바이트가 같은 별개 파일은 거절하지 않는다. 다만 독립 증거라고 주장하지도 않는다.
- 실패: 아래 경우는 모두 `ValueError`이며 성공 보고를 만들지 않는다. 파일 시스템 오류는 `OSError`다.
  - payload 없음
  - SHA 불일치
  - 안전하지 않은 경로
  - 미지원 형식
  - 중복·별칭
- 보고(`evidence_snapshot_audit/v0.1`):
  - 담는 것:
    - index SHA·entry 수·검증 수
    - `kind`·확장자별 개수
    - entry별 상대경로·SHA
    - `declared_missing` 개수
    - 무시한 메타데이터 키 이름
    - `integrity_only: true`, `payload_parsed: false`, `semantic_verification: false`, `independence_verified: false`
  - 담지 않는 것: 사람 응답·라벨 값·절대경로·키. 개수로 품질 점수를 만들지 않는다.

### 미조사 sidecar 준비

- `card_condition.side_evidence_prepare.prepare_sidecar(inventory_path, evidence_root, rows_pointer, search_index=None) -> dict`
  - 반환값은 `side_evidence_sidecar/v0.1` dict다.
  - 경로 인자는 root 기준 안전한 상대경로다. inventory는 `.json`만 허용한다.
  - 파일 읽기는 기존 `EvidenceFiles`, 행 선택은 기존 JSON Pointer 해석을 재사용한다.
- 행 결합에는 inventory SHA와 행의 `id`·`image_sha256`·`side`만 쓴다.
  - 거절 대상: 중복 id, 잘못된 이미지 SHA, 잘못된 side 값, 목록이 아니거나 비어 있는 pointer 대상.
  - `target`·`box`·`point`·`human_evidence` 등은 읽지도 출력하지도 않는다. 이미지·참조 파일도 열지 않는다.
- 모든 행은 다음 값으로 고정한다. 입력에 `side`나 사람 근거가 있어도 `reviewed`로 승격하지 않는다.
  - `review.status=not_reviewed`
  - `evidence=[]`, `missing_sources=[]`, `searched_no_side_evidence=false`
  - `summary={human_side_origins: 0, side_basis: not_reviewed}`
  - `side_claim`은 기존 `side` 값을 그대로 복사하고, 없으면 null이다.
- `search_index`를 지정하면 그 상대경로와 SHA만 `search_scope`에 기록한다. 검색·근거 자동 채움·버전 마이그레이션·기존 sidecar 병합은 하지 않는다.
- 반환 전에 기존 `check_structure`로 호환성을 확인한다. 테스트에서는 기존 `validate_sidecar`와 `side_evidence_cli`로도 검증한다. 기존 모듈은 수정하지 않는다.

### CLI

```text
python -m card_condition.evidence_snapshot_cli --index INDEX --evidence-root ROOT --output NEW
python -m card_condition.side_evidence_prepare --inventory REL --evidence-root ROOT --rows-pointer POINTER [--search-index REL] --output NEW
```

- 공용 `card-condition` CLI에 연결하지 않는다.
- 출력은 기존 `side_evidence_cli.write_new`를 그대로 재사용한다. 같은 폴더 임시 파일 → `fsync` → `os.link`로 공개해 덮어쓰지 않는다. 복사나 새 추상화는 만들지 않는다.
- 종료코드는 기존 검증기 CLI와 같다: 0 수용 / 1 거절(`ValueError`) / 2 사용 오류 / 3 파일 시스템 오류(출력 파일 이미 있음 포함).
- stderr는 한 줄이다. 파일 이름·원문을 노출하지 않는다.

### 오류 코드

| 코드 | 뜻 |
|---|---|
| `F` | index·inventory 형식, 타입, 키 |
| `J` | JSON 파싱, pointer 형식 |
| `P` | 경로 안전성, 파일 종류 |
| `U` | 미지원 payload 형식(파일을 열지 않음) |
| `D` | 중복이거나 모호한 entry 연결 |
| `A` | symlink·hardlink·형식 별칭, index 자기 등재 |
| `M` | payload 없음 |
| `S` | payload SHA 불일치 |
| `R1` / `R2` / `R11` | 준비기에서 기존 검증기와 같은 뜻: inventory 선택 실패 / 행 id 중복 / search index 없음 |

### 한계 (그대로 밝힘)

- 검사 당시 한 번 읽은 바이트와 정적 경로 검사에 근거한다. 검사 뒤의 파일 교체(TOCTOU)는 막지 않는다.
- hardlink를 지원하지 않는 파일 시스템에서는 출력 저장이 실패한다. 강제 종료하면 임시 파일이 남을 수 있다.
- 무결성 통과는 원본 정답·검색 완전성·59개 파일의 독립성을 증명하지 않는다.

## 2–6단계 결과

### 커밋 순서

| 단계 | 커밋 | 내용 |
|---|---|---|
| 1 | `437e5211394a4201f61d9d93d55e2d378623c112` | 이 보고서 1절 계약 고정, task status `implementing` |
| 2 | `012a05471a51187ba040986190c4036e9f6f79d3` | `card_condition/evidence_snapshot.py`, `tests/test_evidence_snapshot.py` |
| 3 | `1c12cc87e5650f2801616157dd936b085841429a` | `card_condition/side_evidence_prepare.py`(API·CLI), `tests/test_side_evidence_prepare.py` |
| 4 | `c1f9b6df6521bc14696f15f63a542105db672848` | `card_condition/evidence_snapshot_cli.py`, `tests/test_evidence_snapshot_cli.py` |
| 5 | `848f405f48e630101ed5a289f26a43ec77a1885f` | `tests/test_evidence_preparation_flow.py`(합성 end-to-end). 실자료 smoke 결과는 아래에 기록 |
| 6a | `711bbf85424c26f82896b89e13907513ddb908e5` | 별칭 메시지 정정("hard link" → "same file"), 대소문자 별칭 회귀 추가. 동작 변화 없음 |
| 6b | `bae1a52e5719400cab901e856996ddd40cf1d4b4` | 중복 분기(realpath 별칭·index 자기 등재)를 inode 대조 하나로 정리, 준비기 승격 시도 입력 검사 강화. 동작 변화 없음 |
| 6c | 이 문서 커밋 | 최종 보고·task 기록, status `ready_for_review` |

기존 `side_evidence.py`·`side_evidence_cli.py`·기존 테스트·공용 CLI·`pyproject.toml`·관제 UI는 변경하지 않았다. 두 CLI의 출력 공개는 `side_evidence_cli.write_new`를 import해 그대로 쓴다.

### 합성 검사 (2–5단계)

- **2단계 감사기**(`test_evidence_snapshot`, 15개):
  - 정상 묶음에서 내용·절대경로를 복사하지 않고, 입력이 불변인지 확인
  - payload 없음 `M`, stale index·변조 `S`
  - 형식이 깨진 JSON도 SHA가 맞으면 통과: 해시만 검사하며 파싱하지 않음을 고정
  - 반복 entry·같은 snapshot 경로·같은 원본 경로 `D`
  - symlink·hardlink·`.json`↔`.jsonl`·대소문자 별칭과 index 자기 등재 `A`
  - 바이트가 같은 별개 파일은 허용하되 `independence_verified: false`
  - `..`·절대경로·root 밖 symlink(파일·디렉터리)·비정규형 `P`, 디렉터리·FIFO `P`
  - 사진·모델·키·확장자 없음 `U`: FIFO `.jpg`로 파일을 열지 않음을 확인
  - index 형식 `F`/`J`, `missing` 비목록 `F`, 파일·root 없음 `OSError`
- **3단계 준비기**(`test_side_evidence_prepare`, 10개):
  - 모든 행 `not_reviewed`, inventory·index SHA 결합
  - 기존 `side`·`human_evidence`, 승격 시도 필드(`status`·`review`·`summary`)가 있어도 승격하지 않음. `target`·`box`·사람 근거를 출력하지 않음
  - `side` 없음·null → null
  - 기존 `validate_sidecar` 통과
  - 중복 id `R2`, 잘못된 SHA·side·id·목록 `F`, pointer `R1`/`J`, 경로 `P`, 없는 index `R11`, 중복 키 `J`, 루트 목록과 빈 pointer
  - CLI 종료코드 0·1·2·3, 기존 출력 보존
- **4단계 CLI**(`test_evidence_snapshot_cli`, 7개):
  - 출력이 API 결과와 같고 입력 불변
  - 거절 시 종료코드 1과 stderr 한 줄, 사용 오류 2
  - 기존·경쟁 출력 보존, stderr에 절대경로 없음
  - `json.dump`·`fsync`·`os.link` 실패마다 파일·임시 파일이 남지 않고 재시도 성공
  - 준비기 CLI도 같은 writer를 쓰는지 확인, 모듈 실행 진입점
- **5단계 흐름**(`test_evidence_preparation_flow`, 5개):
  - audit → prepare → 기존 `side_evidence_cli`가 모두 0
  - scaffold의 `search_scope` SHA와 감사한 index SHA가 일치
  - payload 변경은 audit에서 `S`, 준비 후 inventory 변경은 검증기에서 `R1`, index 변경은 `R11`
  - 손으로 reviewed로 바꾼 빈 행은 `R5`
  - 아무 값이나 인용한 선언적 사람 진술은 구조·바이트가 맞아 수용되지만 `semantic_verification: false`. 출처 선언과 사람이 검증한 의미가 다르다는 것을 고정한다.

### 실자료 smoke (5단계)

실행 위치: root `artifacts/collaboration/evidence-snapshot-preparation-batch-20261025/evidence`. 출력은 Git 제외 경로인 `artifacts/collaboration/evidence-snapshot-preparation-batch-20261025/runs/`에 저장했다. 6b 이후의 최종 코드로 `runs/smoke-20261025-final/`에 다시 실행했다.

| 단계 | 명령 | 결과 |
|---|---|---|
| 감사 | `python -m card_condition.evidence_snapshot_cli --index <root>/index.json --evidence-root <root> --output .../snapshot-audit.json` | 종료 0. 59/59 검증 |
| 준비 | `python -m card_condition.side_evidence_prepare --inventory sources/artifacts/data-coverage-20261024/supplemental-inventory.json --evidence-root <root> --rows-pointer /latest_supplements --search-index index.json --output .../sidecar-not-reviewed.json` | 종료 0. 6행 |
| 검증 | `python -m card_condition.side_evidence_cli --sidecar .../sidecar-not-reviewed.json --evidence-root <root> --output .../sidecar-validation.json` | 종료 0. 6행 수용 |

- **감사 결과:**
  - index SHA `b1c3574738e9…`
  - kind: `previous_snapshot` 46 / `additional_original` 13
  - 확장자: `.json` 33 / `.jsonl` 16 / `.md` 10
  - `declared_missing` 0
  - 무시한 메타데이터 키: `dispatch_sha`, `keys_copied`, `models_copied`, `photos_copied`, `task_id`
- **준비 결과:**
  - inventory SHA `82a5b5269f02…`. 첫 감사 보고서에 기록된 같은 inventory SHA와 일치한다.
  - 6행 모두 `not_reviewed`이고, `evidence`·`missing_sources`가 비어 있으며 `searched_no_side_evidence: false`다.
  - 행 키는 v0.1 행 키 8개뿐이다. `target`·`human_evidence`·절대경로가 없다.
  - `search_scope` SHA는 감사한 index SHA와 같다.
- **검증 결과:** `side_basis_counts` = `not_reviewed` 6, `rows_total` 6 / `rows_described` 6, `semantic_verification: false`, `modifies_sources: false`.
- **사전 기대값과의 차이:** 없다(59개, 6행).
- **입력 보존:** root 아래 60개 파일(index 1 + payload 59)의 SHA와 권한 비트가 첫 실행 전과 최종 실행 후 동일하다. chmod·덮어쓰기는 없었다.
- **최종 코드 재실행:** 세 산출물이 첫 실행과 동일했다(감사 dict 동일, sidecar·검증 파일 바이트 동일).
- **`side_claim`의 의미:** 6행 모두 `front`다. 이는 inventory의 기존 `side` 값을 결합 키로 복사한 것일 뿐이며 면 확인이 아니다. 이전 출처 감사에서 photo-1·photo-3의 front는 근거 부족으로 판정됐고, 이번 작업은 그 판정을 바꾸지 않는다.
- 실제 source·origin 의미 검증 0, 새 사람 라벨 0, 면·정답·수량 변경 0.

### 반례 검토 (6단계)

**새 결함:** 이번 신규 코드에서는 재현되지 않았다.

**신규 코드에서 확인하고 손본 것**
- 대소문자만 다른 경로: macOS 기본 파일 시스템은 대소문자를 구분하지 않는다. `REPORT.md`와 `report.md`는 realpath 문자열은 다르지만 같은 파일이다. 감사기는 inode 대조로 `A` 거절한다. 메시지가 "hard link"로 부정확해 6a에서 고쳤다.
- mutation 대조: 임시 복사본에서 위험 분기 10개를 바꿔 돌렸다.
  - 7개는 처음부터 검출됐다: inode 별칭, root 포함, 원본 중복, 확장자 선검사, SHA 비교, 준비기 면 누락, 준비기 id 중복.
  - realpath 별칭 검사와 index 자기 등재 검사 제거는 살아남았다. 둘 다 inode 대조가 이미 같은 경우를 거절하는 중복 분기였으므로 6b에서 제거했다.
  - 준비기의 상태 복사 변형은 테스트 입력에 그 필드가 없어서 살아남았다. 6b에서 입력에 승격 시도 필드를 넣었고, 이후 상태·요약 복사 변형 2개와 inode 제거가 모두 검출됐다.

**기존 검증기의 반례 (보류: 수정 금지 범위)**
- 재현: `side_evidence.check_files`는 origin 위치를 realpath 문자열로 센다. 대소문자를 구분하지 않는 파일 시스템에서는 origin을 `intake/REPLY.json`처럼 대소문자만 바꿔 적으면 같은 파일이 origin 2개로 수용된다. symlink 별칭은 R8로 거절된다.
  - 합성 재현: `test_side_evidence_sources.Fixture`의 photo-4 행에 origin 경로만 대문자로 바꾼 사람 진술을 추가하고 요약을 재계산하면 `validate_sidecar`가 `human_side_origins = 2`로 수용했다(이 worktree, macOS).
- 같은 이유로 `EvidenceFiles.cache`도 대소문자 별칭을 다른 항목으로 보관한다. 현재 확인한 영향은 origin 수 부풀림이다.
- 최소 제안(Codex 판단):
  - origin 위치 키와 캐시 키를 realpath 대신 `os.stat(real)`의 `(st_dev, st_ino)`로 바꾼다.
  - 회귀로 같은 시나리오가 `^(R8|R9):`로 거절되는지 검사한다. 대소문자를 구분하는 파일 시스템에서는 파일이 없어 R9가 된다.
  - 기존 파일은 이 task에서 변경하지 않았다.

### 검사 결과

- `PYTHONPATH=tests .venv/bin/python -m unittest test_evidence_snapshot test_evidence_snapshot_cli test_side_evidence_prepare test_evidence_preparation_flow test_side_evidence test_side_evidence_sources test_side_evidence_cli -v` → 86개 통과, 종료코드 0.
  - 신규 37개: 15 / 7 / 10 / 5
  - 기존 49개: 16 / 24 / 9
- `.venv/bin/python -m compileall -q card_condition/evidence_snapshot.py card_condition/evidence_snapshot_cli.py card_condition/side_evidence_prepare.py` → 종료코드 0.
- `git diff --check 1a6fa8f… HEAD` → 통과.
- base 이후 변경 파일: allowed_files 9개와 Codex 배정 커밋의 prompt·task 문서. 신규 코드·테스트에 홈 절대경로가 없다.
- 가상환경: 이 worktree의 `.venv`, 표준 라이브러리만 사용. `card_condition.__file__`가 이 worktree를 가리킨다.
- 미실행:
  - 기존 ML 의존 테스트 55개(Codex 통합 후. 이 venv에는 torch가 없다)
  - 학습·추론·사진 열람·외부 AI·`review --auto`

### 미해결·리스크·롤백

- 미해결:
  - 기존 검증기의 대소문자 별칭 origin 수 부풀림: 수정 여부는 Codex 결정
  - 6행의 실제 면(사람 근거 필요, 이번 범위 밖)
  - 이전 작업에서 남은 sidecar 저장 위치·충돌 정책 등
- 리스크:
  - 무결성 통과는 원본의 진실성·검색 완전성·59개 파일의 독립성 증명이 아니다.
  - scaffold의 `side_claim`을 면 확정으로 읽으면 안 된다.
  - 정적 경로 검사와 한 번 읽은 바이트에 근거하므로 TOCTOU는 막지 않는다.
  - hardlink를 지원하지 않는 파일 시스템에서는 저장이 실패한다(종료코드 3, 파일 없음).
  - 강제 종료 시 임시 파일이 남을 수 있다.
- 롤백: 미통합이면 반영하지 않는다. 통합 후에는 위 커밋을 역순으로 revert한다. 신규 파일만 추가했으므로 기존 동작·데이터·모델 복구는 필요 없다. 진척률 30/100은 그대로다.
