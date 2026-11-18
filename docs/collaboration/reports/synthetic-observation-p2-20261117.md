# 합성 관찰 루프 P2 세 경계 보완 결과

개발 진척 **78/100 유지** (`usable-card-analysis-v1.13`). 기존26개 + 새5개 = **합성 검사31개 통과**. 모델 누락·오탐·독립 평가·일반화 개선은 미평가다.

- 상태: `synthetic_observation_p2_fixed_collection_not_executable`.
- 실제 수집: `not_executable_pending_collection_contract_approval` 유지.
- 브랜치: `codex/synthetic-observation-p2-20261117`.
- 기준: `cf53d5ea314a34a6d702a449ac0d20effd9ed1d9` (기존 루프 기록).
- 검사 당시 HEAD: 계약 커밋 `858de45c85a455085c34e9bddc0823d161e57651`와 아래 미커밋 소스/테스트. 실제 검증 내용은 파일 SHA로 고정하고 최종 로컬 커밋은 Git 이력/세션 인계와 구분한다.

## 변경 파일·핵심 diff

|파일|변경|
|---|---|
|[observation_display.js](../../../card_condition/observation_display.js)|공통 displayReady에서 명시 viewport/DPR/CSS·natural size·양수 표시 크기를 대조. 환경 변경도 같은 gate를 사용하고 실패를 latch.|
|[observation_response.py](../../../card_condition/observation_response.py)|명시 profile을 관측과 비교하는 leaf 추가. presented/change/export의 필요한 자산 상태를 검사하고 변경 시점 오류를 최종까지 유지.|
|[observation_receipt.py](../../../card_condition/observation_receipt.py)|생성·read_records·load/멱등 경로에 공유 status/reasons 규칙 적용. rejected 이유도 실제 원문 검증 실패와 대조. raw/생성 전용 저장 API는 보존.|
|[observation_receipt_status.py](../../../card_condition/observation_receipt_status.py)|출처/관측 요약/선언된 conflicts/오류에서 상태·사유를 결정하는 순수 leaf.|
|[test_observation_p2.py](../../../tests/test_observation_p2.py)|기존 합성 fixture 재사용, 명시 조건/변경 시점/재해시 manifest 변조/정상 상태 보존5검사.|
|[observation_profile.test.cjs](../../../tests/observation_profile.test.cjs)|Node DOM stub으로 초기 조건·환경 변경·변경 당시 CSS 실패의 latch·기존 메모/상태 보존 검사.|
|[task](../tasks/synthetic-observation-p2-20261117.md)|세 P2 소유권·계획·유지 조건·인계.|
|이 보고서|실제 검사·검토·리스크·소스 SHA·롤백.|

기존 packet/assets와 고정 기준/진척 파일은 기준 커밋과 bytes 동일함을 확인했다. 이전 루프 task/보고서·기존 검사/fixture·운영/모델/worker·라벨·원본·다른 worktree는 변경하지 않았다.

## 세 P2의 실제 보완

1. **명시 profile 대조**: profile.viewport_css/device_pixel_ratio/image_css가 null이 아닐 때만 실제 관측과 정확 비교한다. null은 승인/기본 숫자로 대체하지 않는다. JS는 초기 표시·입력·내보내기·환경 변경 경로에서 공통 gate를 쓴다. Python도 관측된 선언 불일치를 영구 미검증으로 유지한다. 합성 fixture 숫자는 시험 입력이며 기기/표본/허용 오차의 새 승인 기준이 아니다.
2. **변경 당시 오류 유지**: Python은 change의 해당 entry context/region에 필요한 모든 자산의 누락·current_src_matches·natural size·양수 CSS·명시 CSS를 확인한다. presented/export에서는 전체 자산을 확인한다. 실패를 누적하므로 나중 export가 정상이더라도 display_verified=false다. JS도 잘못된 표시 상태에서 입력이 변경되면 latch로 잠그고 이미 들어온 상태/메모를 삭제·정상 보충하지 않는다.
3. **status/출처 정합성**: 순수 분류기를 생성과 read_records에서 공유하고 load/멱등 진입점 모두 이 검사를 거친다. AI/unknown은 pending_provenance이고 synthetic_only로 올리지 않는다. 누락/미검증은 pending_observation이며 기존 conflicts 우선순위는 유지한다. 상태·정해진 사유가 맞지 않는 재해시 manifest는 거부한다. rejected는 raw 재검증의 실제 오류 사유도 대조한다. 사람 정답/수집 적격 false와 실행 불가 상수는 그대로다.

## 실제 검사·교차 검토

Superpowers receiving-code-review/TDD 절차를 적용했다. 모든 수정과 합성 검사는 ./develop 잠금 안에서 수행했다.

- red.log: 새5개 중4검사에서14실패(하위 사례 포함)로 세 허점을 재현했다. 정상 분류/기존 raw 보존 검사는 수정 전에도 통과했다.
- green.log: 수정 후 새5개 통과. Node는 명시 조건 일치, viewport/DPR/CSS 불일치, 이후 resize, 변경 당시 CSS0의6시나리오를 실행한다. 실제 crypto/Blob과 기존 DOM/decode stub을 사용한다.
- final-green.log: 기존 packet6/assets6/page3/response5/receipt6 + P2신규5 =31개, 모두 exit0. 다음 명령을 각각 정확한 파일명으로 실행했다:

```text
.venv/bin/python -m unittest discover -s tests -p test_observation_packet.py -v
.venv/bin/python -m unittest discover -s tests -p test_observation_assets.py -v
.venv/bin/python -m unittest discover -s tests -p test_observation_page.py -v
.venv/bin/python -m unittest discover -s tests -p test_observation_response.py -v
.venv/bin/python -m unittest discover -s tests -p test_observation_receipt.py -v
.venv/bin/python -m unittest discover -s tests -p test_observation_p2.py -v
```

명령은 잠금 내부 subprocess에 PYTHONDONTWRITEBYTECODE=1과 함께 전달하고 출력/exit를 보존했다. wildcard/전체 suite는 실행하지 않았다. 새 의존성 설치·실제 모델 관련 import/실행은 없다.

독립 읽기 전용 reviewer는 이번 세 P2 범위에서 중요한 잔여 결함을 발견하지 못했다. reviewer는 코드/기존·신규 테스트만 읽었고 실행/수정/실제 자료 접근은 하지 않았다. 이 검토와 합성 통과를 실제 브라우저·기기·사람 판정·모델 성능 검증으로 확대하지 않는다.

Python AST·JS named function/익명 callback 부재로 정의 수를 확인하고 node --check로 문법을 확인했다. 소스는 display7/response5/receipt7/status1정의, 새 테스트6/2정의다. 최장 프로젝트 전이는4회로 유지:

- capture_receipt/load_receipts→validate_response→validate_observations→validate_event→exact_keys.
- capture_receipt/load_receipts→validate_response→validate_packet→validate_profile→exact_keys.
- 새 event_display_matches는 validate_observations에서 직접 부르는 leaf라 capture 시작3전이.
- capture_receipt→read_records→receipt_classification은2전이, read_records→validate_context→exact_keys를 합쳐도 capture 시작3전이. 새 분류기를 기존 receipt 파일에 억지로 추가하거나 검증 wrapper로 호출 깊이를 늘리지 않았다.
- JS displayReady/handleEnvironment는 명시 함수 참조로 연결되며 순환 호출을 만들지 않는다. 라이브러리 내부 호출은 별도 제외한다.

## 미정·미실행·리스크

- 실제 수집 실행 불가 사유는 해소하지 않았다. 기기·사진 출처·표본 수·독립 판정/관찰·접근 통제·수용 수치와 절차 미정은 그대로다. 별도 인력/비용 확보를 필수로 추가하지 않았다. AI를 사람 정답으로 취급하지 않는다.
- profile null은 미정 그대로다. 명시된 값이 있는 경우의 내부 불일치만 보완했고 새로운 수치·허용 오차를 정하지 않았다. 실제 기기에서의 CSS/DPR/확대 관측·브라우저 표시와 decode는 미검증이다.
- display_verified는 브라우저 자기 보고의 내부 일치 여부다. 실제 사람의 관찰/주의/외부 정보 비열람·원본→파생 이미지 의미를 입증하지 않는다. Node DOM/decode stub은 실브라우저 시험이 아니다.
- status 검사는 기존 context·관측 요약·선언된 conflicts의 내부 분류 규칙이다. conflicts의 전체 과거 관계 재산정·서명/사람 인증·악의적 전체 재작성 방지 기능은 추가하지 않았다.
- 새 규칙과 모순되는 과거 파생 metadata는 재읽기에서 거부할 수 있다. 기존 원문/manifest를 자동 수정·정상 승격·삭제하거나 마이그레이션하지 않는다. raw/SHA/중복 키 거부·부분 저장·lone surrogate 보존 검사는 기존 검사로 회귀 확인했다.
- 실제 자료 사용·사람 판정 수집/재요청·모델 검증·학습·추론·main 통합·push·worktree 정리는 미실행이다. 인터랙티브 판정 페이지를 사람에게 열지 않았고 최종 열기는 정적 합성 결과 보고서만 한다.

## 검증 소스 SHA-256

- `card_condition/observation_display.js`: `47b5b17ade763d265ffdeff73b86f4aceaddcb60809f07e87895d455e21a4ded` · 7정의
- `card_condition/observation_response.py`: `b2e1b2734f3b0e3595e869fc3cbcb3f030ef96ccb0be4b952fa5030439b958a8` · 5정의
- `card_condition/observation_receipt.py`: `3d9b551cd2fb417d0ec838d513d50e210accdfd2472c3f8cbd2f97d9cb145fd9` · 7정의
- `card_condition/observation_receipt_status.py`: `89b52df0f358be920afc5d0408170c0c7c08ddee2aeb200cdfc0f29fb5529497` · 1정의
- `tests/test_observation_p2.py`: `97860f5766688bb5de303ff1639f02978f4663340a1600a0648d1f4f46ddef40` · 6정의
- `tests/observation_profile.test.cjs`: `ccd6b8c3e57dfdcf8ccebbac87407e21ebaddc2eb593e9668907923c019d5ce1` · 2정의

## 인계·HTML·롤백

Git 제외 근거: artifacts/synthetic-observation-p2-20261117/{red.log,green.log,final-green.log,execution.json,report.html}. 진척 근거 PROGRESS_CRITERIA.md/development-progress.json은 수정하지 않았다. HTML은 외부 CDN/API/실제 사진/사람 답 없이 합성 결과와 한계만 담는다.

로컬 결과 커밋만 남긴다. 구현 철회는 이번 결과 커밋을 git revert한다. 계약까지 철회하면 결과 다음858de45 순서로 revert한다. cf53d5e 이전 루프/bytes 구현과 기존 원본·.claude/·D-LOC·다른 worktree는 삭제/복원하지 않는다. 실제 롤백은 이번 요청에 포함되지 않는다.

HTML 확인: 열기 요청 성공(exit0), 실제 렌더 미확인.
