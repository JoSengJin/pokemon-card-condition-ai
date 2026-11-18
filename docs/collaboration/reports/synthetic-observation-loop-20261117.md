# 합성 표시·4상태·관찰조건/원답 저장 루프 결과

개발 진척 **78/100 유지** (`usable-card-analysis-v1.13`). 기존 합성12개 + 새14개 = **26개 통과**. 이번 성과는 합성 도구 연결이며 누락률·오탐률·독립 평가·일반화 개선은 미평가다.

- 상태: `synthetic_observation_loop_implemented_collection_not_executable`.
- 실제 수집: `not_executable_pending_collection_contract_approval` 유지.
- 브랜치: `codex/synthetic-observation-loop-20261117`.
- 기준: `be453f7c4f056d902458531e62b7210fe1b33a17` (기존 bytes 대조기).
- 최종 검증 코드 SHA: `36fdf5ad3511119adbca6ea0c8fc573be6f1ca80`. 이후 보고서/task 커밋은 기록 보완이며 검증 코드와 구분한다.

## 변경 파일·핵심 diff

|파일|책임|
|---|---|
|[observation_page.py](../../../card_condition/observation_page.py)|기존 verify_assets 재사용, 공개 packet/검증 bytes만 안전하게 내장하는 offline HTML 문자열 반환.|
|[observation_display.js](../../../card_condition/observation_display.js)|실제 내장 bytes SHA→동일 bytes Blob→decode/크기→입력 gate. 초기부터 DOM 감시, 내부 src 변경 구별, 무효화 latch·기대 ref/요소/자산 집합 검사.|
|[observation_response.js](../../../card_condition/observation_response.js)|명시적4상태·그대로인 메모·관측 로그/버전/해시 결합 및 명시적 JSON 내보내기.|
|[observation_response.py](../../../card_condition/observation_response.py)|독립 수신 schema/ID/photoSHA/profile/H-A/시각/자산 증거 검사. invalidate·최종 상태/마지막change·관측 가능한 금지 확대 모순을 보류.|
|[observation_receipt.py](../../../card_condition/observation_receipt.py)|원문/해시/수신 문맥·거부/충돌 보존, 정확한 재접수만 멱등, 생성 전용 저장/부분 저장 식별/무결성 재검사.|
|[pyproject.toml](../../../pyproject.toml)|기존 package-data에 새 JS2개만 추가. 다른 의존성/CLI 변경 없음.|
|[observation_loop_fixture.py](../../../tests/observation_loop_fixture.py)|메모리 합성 PNG·가짜 ID/시각·관측 body 생성.|
|[observation_browser_fixture.cjs](../../../tests/observation_browser_fixture.cjs)|Node VM의 DOM/decode stub. 실제 브라우저/기기와 구분.|
|[observation_display.test.cjs](../../../tests/observation_display.test.cjs)|실제 crypto/Blob bytes 대조, hash/decode/API 실패·초기 제거/재삽입·ref 변경·초기 A확대 gate 검사.|
|[observation_response.test.cjs](../../../tests/observation_response.test.cjs)|4상태/원문 메모/이벤트/JSON 내보내기와 무효화 후 답 보존.|
|[test_observation_page.py](../../../tests/test_observation_page.py)|공개 payload·escape·같은 bytes·profile/변조 거부·Node 연결3검사.|
|[test_observation_response.py](../../../tests/test_observation_response.py)|4상태/누락 구분/연결/타입/모순·Node→Python 연결5검사.|
|[test_observation_receipt.py](../../../tests/test_observation_receipt.py)|원문/해시/거부/중복 키/세션/AI/충돌/멱등/부분 저장/변조·끝단 연결6검사.|
|[task](../tasks/synthetic-observation-loop-20261117.md)|소유권·설계/계획·판단·단계별 검사/보완·로컬 인계.|
|이 보고서|실제 실행/검토/한계/소스 SHA·롤백 기록.|

기존 observation_packet/assets 소스와 테스트, PROGRESS_CRITERIA.md/development-progress.json은 기준 커밋과 bytes 동일함을 확인했다. 기존 라벨·원본·모델·worker·운영 코드·.claude/·D-LOC·다른 worktree를 수정하지 않았다.

## 완성한 합성 경로

1. Python renderer는 기존 packet/assets 검사를 통과한 bytes만 내장한다. 이미지 자산을 파일 경로로 다시 읽거나 공개 payload에 private metadata를 넣지 않는다. 지시문은 HTML escape, 내장 JSON의 `<`는 escape한다. 실제 자료 선정/이미지 생성기는 추가하지 않았다.
2. 브라우저 코드가 base64에서 복원한 동일 bytes를 해시하고 Blob URL로 img에 연결하여 decode/load 크기를 대조한다. 정상 내부 src 설정만 구별해 초기부터 observer를 유지한다. 제거·교체·data-ref/src/srcset 변경·연결 불일치 시 입력을 잠그고 원응답 값은 남긴다. A 등 확대 금지 profile은 관측 가능한 non-1 visualViewport.scale도 gate에서 거부한다.
3. 각 구역을 unreviewed로 시작하고 normal/defect/unassessable과 구분한다. 일괄 정상·정상 기본 보충·메모 trim/AI 보충이 없다. 누락 entries와 명시적 unreviewed는 다르게 수신한다. 원문·상태·관측/해시를 명시적 내보내기로 결합한다.
4. 관측은 packet/profile/instructions/renderer와 연결하며 시각/UTC offset·viewport/DPR·CSS/natural size·visibility/scroll/관측 가능한 scale·기대/실측 자산 SHA와 표시 요소 ID를 기록한다. `display_verified`는 **브라우저 자기 보고의 내부 일치 검사**이며 실제 사람 관찰/기기 증명이 아니다. 세션/수신 담당/received_at은 별도 보관자 context로 분리한다.
5. capture_receipt는 strict_json_loads를 사용한다. 같은 값·중첩/배열 내부의 중복 키·파싱/연결 오류도 raw.bin과 SHA·거부 이유로 보존한다. 정상 원문과 같은 JSON의 다른 공백 bytes는 다른 원문이다. 파생 manifest/digest는 ASCII escape를 사용해 lone surrogate도 원문 bytes를 잃지 않고 저장한다.
6. 수신 identity는 packet/rawSHA/수신 context를 결합한다. 정확한 재접수만 기존 bytes/기록과 대조해 반환한다. 별개 reviewer/session/time을 병합하지 않는다. 상충 답은 두 원문을 유지하고 conflict로 표시하며 정상 정답을 선택하지 않는다.
7. ledger별 잠금 아래 raw.bin과 receipt.pending을 생성 전용·fsync로 기록한 후 마지막에 receipt.json을 atomic link한다. 최종 manifest 없는 디렉터리는 incomplete로 반환하며 삭제/덮어쓰기/자동 복구하지 않는다. load와 멱등 재수신 모두 원문/해시·파생 응답/요약과 잘못된 rejected 재분류를 재검사한다.
8. packet/response/receipt는 합성 전용·실행 불가 상수를 유지한다. receipt의 `eligible_for_collection=false`, `human_truth=false`는 항상 고정이다. human 출처 수집 context는 거부하고 ai/unknown은 pending_provenance다. AI를 사람 정답으로 만들거나 라벨/학습 export에 연결하지 않는다.

## 실제 검사·교차 검토·보완

명령은 ./develop 잠금 안에서 각각 정확한 파일명으로 실행했다:

```text
.venv/bin/python -m unittest discover -s tests -p test_observation_packet.py -v
.venv/bin/python -m unittest discover -s tests -p test_observation_assets.py -v
.venv/bin/python -m unittest discover -s tests -p test_observation_page.py -v
.venv/bin/python -m unittest discover -s tests -p test_observation_response.py -v
.venv/bin/python -m unittest discover -s tests -p test_observation_receipt.py -v
```

실제 실행은 위 명령과 PYTHONDONTWRITEBYTECODE=1을 잠금 내부 subprocess에 전달하고 전체 stdout/stderr를 저장했다. wildcard discovery·전체 suite는 사용하지 않았다. Python3.12.14/Pillow12.3.0과 기존 Node24.21.0 사용, 새 의존성 설치 없음.

|단계|RED·독립 읽기 전용 검토·보완 근거|최종|
|---|---|---|
|표시|page-red.log 미구현3실패. reviewer의 초기 제거/재삽입·data-ref2건을 page-review-red.log에서 재현하고 observer/latch/ref·proof 집합 보완.|page-green.log3통과|
|4상태|response-red.log 미구현4실패. 자체 타입 회귀 response-types-red.log의 bool/int·비hashable ID 보완. reviewer의 invalidate·마지막change 모순2건을 response-review-red.log3case로 재현/보완.|response-green.log page3+response5통과|
|저장|receipt-red.log 미구현6실패. reviewer의 lone surrogate 원문 유실·거부 후 stale summary·멱등 summary 미검사3건을 receipt-review-red.log3실패로 재현/보완.|receipt-green.log6통과|
|최종 전체 흐름|추가 reviewer의 초기 A확대·정상→거부 재분류 replay2건을 final-review-red.log의3파일 실패로 재현. gate/관측/재접수 검사를 보완.|final-green.log 기존12+새14=26통과|

각 reviewer는 소스/문서만 읽었다. 모든 중요한 지적9건은 회귀 RED→GREEN으로 보완했으며 미해결 중요 지적을 완료로 숨기지 않았다. 이 합의/합성 통과는 실제 브라우저·사람 판정 독립성·모델 성능 검증이 아니다. 이 루프 턴에서 범위 밖 검사/모델 import 시도는 없었다(이전 bytes 작업의 scope-error는 그 보고서에 별도 보존).

node --check로 새 JS/CJS 문법, Python AST와 named-function/익명 callback 부재로 구조를 확인했다. 새 파일의 최대 정의7개, 프로젝트 최장 전이4회:

- render_page→verify_assets→validate_packet→validate_profile→exact_keys.
- capture_receipt/load_receipts→validate_response→validate_observations→validate_event→exact_keys.
- capture_receipt/load_receipts→validate_response→validate_packet→validate_profile→exact_keys.
- JS initialize→verifyAssets→invalidate→observe는3전이, exportResponse→buildResponse→invalidate→observe는3전이. Observer와 이벤트 listener는 명시 함수 참조이고 순환 프로젝트 호출 없음. 라이브러리 내부 호출은 제외한다.

## 미실행·리스크·남은 의존

- **실제 수집 실행 불가 상태는 해소하지 않았다.** 기기·사진 출처·사람 판정 경로·표본 수·구체 수치/절차·독립성/접근 통제는 미정/미확인이다. 별도 인력/비용을 필수로 추가하지 않았다.
- Node VM의 DOM/decode stub은 실제 브라우저·CSS 레이아웃·기기·package 설치/배포 검증이 아니다. 실제 브라우저의 decode/Blob 동작, 확대 감지 한계, 화면 표시 및 EXIF 적용·실기기 조건은 미확인이다. package-data는 정적 연결 확인만 했고 package build/설치는 하지 않았다.
- 관찰/원답 저장은 암호학적 사람 인증·독립 평가·정답성 보증이 아니다. 자유문장/이미지 의미·점수 기반 선정 여부를 schema/SHA로 판정하지 않는다. 합성 출처 표시는 신뢰할 수 있는 실제 출처 증명이 아니다.
- 최종 manifest link 실패 뒤 raw 보존은 합성 검사했다. raw 쓰기 전의 디스크 불능까지 저장을 보증하지 않으며 저장 실패를 예외로 반환한다. 부분 저장은 완료가 아니다. 파일 해시는 내용 연결 검사이며 쓰기 권한자의 악의적 전체 재작성까지 인증하는 서명이 아니다.
- ledger는 합성 전용 임시 디렉터리에서만 검사했다. 다른 checkout과 전역 잠금을 공유하지 않는다. 실제 운영 스토리지/동시 다중 writer/복구·배포를 검증했다고 주장하지 않는다.
- 실제 자료 사용·사람 판정 수집/재요청·모델 검증·학습·추론·외부 provider 호출·main 통합·push·다른 worktree 정리는 하지 않았다. 테스트가 생성한 합성 이미지와 가짜 문맥만 사용했다. 인터랙티브 판정 화면을 사람에게 열거나 판정을 요청하지 않았으며 최종 열기는 정적 성과 보고서뿐이다.

## 소스 SHA-256·구조

- `card_condition/observation_display.js`: `23f21caa0d63babb8e7a4cea7fce9ad8590e10b1eba4acc680e4d4da54df3531` · 7정의
- `card_condition/observation_page.py`: `389ba78770167cf079a4a8ab784fc82cb47b9a698bf5dba64a51bbd43b2709f9` · 1정의
- `card_condition/observation_receipt.py`: `12dd6cc5acacdf94b803898829e7f221121e29e2341311946dcac46352532a43` · 7정의
- `card_condition/observation_response.js`: `d70ae956dafc0b7c0fa171f6007cb380467ede17bc825a9d66f51ccc7a3c9175` · 4정의
- `card_condition/observation_response.py`: `792a90d2228f374f340d72586e1e563979cd4a9316444d8913b1c12913d06556` · 4정의
- `tests/observation_browser_fixture.cjs`: `31e9ab4fe3e06a775e73c34bd39ab808257f59931a46a451c4a2ac4fab0bdb61` · 7정의
- `tests/observation_display.test.cjs`: `eabba8faab8c47b6707b514c695ef8a602b0950729844261aba7b4594088bf2b` · 3정의
- `tests/observation_loop_fixture.py`: `3130272937bf2baa6449fba3161e4ad3e4d343afa95a2e7b35174cd48df41eec` · 2정의
- `tests/observation_response.test.cjs`: `b857ab25fef6c6b65f3e36e981aac3bf501a062e4268506b6085f00a6ed28830` · 2정의
- `tests/test_observation_page.py`: `c63acba5b07417e6d6cfb05d9c1c372d7eb0f73b568aae06fd0ffe75e714f059` · 4정의
- `tests/test_observation_receipt.py`: `03b5ef58e3ea64fbba8695604e9313bc2a5984db47448fb17b3f1851a3f6f65a` · 7정의
- `tests/test_observation_response.py`: `20bb25f5bc4f1e8d3b94b36c6e0e875a94765b36c1ec23cdbe699a104921bfec` · 6정의

## 로컬 커밋·롤백·HTML

로컬 커밋 순서: 6f5dbcb(계약)→51e2a60(표시)→c56e80a(4상태)→be29a34(원답 저장)→36fdf5a(최종 보완)→이 결과 기록 커밋. main/push는 하지 않는다.

롤백은 이 결과 기록 커밋부터 위 구현/계약 커밋을 역순 git revert한다. 기존 bytes 대조기의 be453f7·계약d510036은 이번 루프 롤백 대상이 아니다. 실제 롤백은 하지 않았다. 기존 원본·.claude/·D-LOC·다른 worktree를 삭제/복원하지 않는다.

HTML: artifacts/synthetic-observation-loop-20261117/report.html. 외부 CDN/API/실제 이미지/사람 응답 없이 진척/성과/한계/근거만 표시한다. 실행 메타데이터와 소스 SHA는 같은 폴더 execution.json, 전체 검사 출력은 final-green.log다.

HTML 확인: 열기 요청 성공(exit0), 실제 렌더 미확인.
