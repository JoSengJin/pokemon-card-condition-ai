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

(단계별 커밋 후 기록한다.)
