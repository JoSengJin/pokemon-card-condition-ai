# 합성 표시 자산 bytes 대조기 결과

개발 진척 **78/100 유지**, 기준 `usable-card-analysis-v1.13`. 새 자산 합성6개 + 기존 packet 합성6개 통과. 모델 품질·누락/오탐·일반화 개선은 미평가다.

- 상태: `synthetic_asset_verifier_implemented_collection_not_executable`.
- 실제 수집: `not_executable_pending_collection_contract_approval` 유지.
- 기준 main: `3eb813a3f24284f13ee4eb55b0fed798787007d5`.
- 전용 브랜치: `codex/synthetic-observation-assets-20261117`. 검사 당시 HEAD는 계약 커밋 `d510036ff134aa904e34533c6ea2edace855b319`이며 소스/테스트는 신규 미커밋 상태였다. 최종 로컬 커밋은 Git 이력/세션 인계로 구분한다.

## 변경 파일·핵심 diff

|파일|변경|
|---|---|
|[observation_assets.py](../../../card_condition/observation_assets.py)|verify_assets와 decoded_size 신규2정의. 기존 packet 검사 후 메모리 bytes의 SHA·정적 PNG/JPEG 해독·크기·정확한 자산 집합 검사, 동일 bytes 반환.|
|[test_observation_assets.py](../../../tests/test_observation_assets.py)|메모리에서 생성한 합성 PNG/JPEG만 사용한6검사, 준비 메서드 포함7정의.|
|[task](../tasks/synthetic-observation-assets-20261117.md)|소유 파일·명세·TDD 계획/ledger·최초 검사 선택 오류와 수정·단일 프레임 거부 결정·인계.|
|이 보고서|검사·검토·한계·소스 SHA·리스크·롤백.|

기존 packet 소스/테스트·진척/기준 파일은 기준 main과 bytes 동일함을 확인했다. 기존 모델/worker/CLI/화면/원본 기록을 수정하거나 연결하지 않았다.

## 구현 경계·재사용

1. validate_packet을 먼저 재사용하므로 금지 필드·packet SHA·H/A·합성 전용·실행 불가 조건은 그대로 적용된다. JSON 원문 입력은 기존 strict_json_loads를 호출자가 선행해야 한다. 이 API는 dict만 받으며 새 JSON 파서나 파일 입력을 추가하지 않았다.
2. 공개 ref→bytes dict를 스냅샷하고 packet의 ref 집합과 정확 일치시킨다. 공유 context는 하나로 처리하며 누락/추가 자산·비bytes/mutable 값은 거부한다. ref는 식별 키로만 쓰고 경로/URL을 열지 않는다.
3. SHA-256은 실제 표시 자산 bytes와 asset.sha256을 대조한다. photo_sha256은 원사진의 선언이며 이 검사에서 읽거나 재해시하지 않는다. Pillow verify 후 동일 bytes에서 다시 열어 load하여 구조/픽셀 해독과 size를 확인한다. PNG/JPEG 실제 형식과 확장자 일치, 단일 프레임도 검사한다. Pillow 전역 허용/제한 설정은 완화하지 않는다.
4. 모든 자산 통과 후 새 dict를 반환하되 각 값은 해시/해독한 불변 bytes 객체와 동일하다(is 검사). bytes 재인코딩·원본 파일 재읽기·입력 변경·부분 성공 반환·실행 상태 승격은 없다.

## 실제 검사·발생한 실패

모든 코드/테스트 편집 및 합성 실행은 ./develop 잠금 안에서 수행했다. 독립 .venv의 Python3.12.14와 requirements-tested.txt 기존 고정 Pillow12.3.0을 사용했다. 다른 worktree의 site-packages를 공유하지 않았으며 Torch 등 모델 패키지는 설치하지 않았다.

- baseline.log: 기존 packet6개 통과.
- red.log: 새6개가 대조기 미구현 assertion으로 실패 후 구현했다.
- scope-error.log: 최초 `test_observation_[pa]*.py` 패턴이 observation_audit/prototypes도 선택했다. 허용12개 검사는 통과했지만 observation_audit→point_probe:7의 import torch 및 observation_prototypes 검사파일:3의 import torch에서 ModuleNotFoundError2건으로 실패했다. 첫 실행을 성공으로 보고하지 않는다. 소스/traceback상 실제 자료 읽기·모델 검증/학습/추론 이전의 import 실패다. 실패를 보존하고 추가 모델 의존성을 설치하지 않았다.
- 이후 실행 범위를 정확히 두 파일로 수정했다. 명령은 각각 `./develop -- env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p test_observation_packet.py -v`, 같은 명령의 `-p test_observation_assets.py -v`다. 실제로는 잠금 내부 subprocess에서 동일 명령을 실행하며 출력/exit를 저장했다.
- animation-red.log: 합성 APNG2프레임의 잘못된 통과를 재현(1검사 실패). 첫 프레임만 검사한 것을 전체 지원으로 오인하지 않도록 단일 프레임 거부 조건을 추가했다.
- 최종 green.log: packet6 + assets6, 각각 exit0/OK. 자산 검사는 PNG/JPEG·H/A, 동일 bytes/is·입력 보존, 변조·잘못된 SHA·mutable/비bytes, SHA 일치 손상/잘린 PNG·CRC 유효하나 픽셀 부족 PNG, 크기·형식·다중 프레임, 자산 누락/추가·공유 context, packet 금지 필드/실행 상태 변조 거부를 포함한다.
- 구조: 소스2정의, 테스트7정의. 최대 프로젝트 전이 verify_assets→validate_packet→validate_profile→exact_keys=3회(라이브러리 내부 제외), decoder helper로의 경로는1회. 기존 packet7정의 유지. AST 집계와 읽기 전용 교차 검토에서 확인했다.
- Superpowers 독립 검토 및 단일 프레임 보완 delta 검토: 중요한 결함 없음. 검토자는 코드/문서만 읽고 검사·실제 자료 접근·수정은 하지 않았다.
- 전체 suite는 미실행이다. 실제 자료 사용·수집·모델 검증·학습·추론·사람 판정 요청·외부 provider 호출·main 통합·push는 하지 않았다. 초기 범위 오류의 모델 관련 import 시도/실패는 위와 같이 별도 기록한다.

## 미구현·리스크·실행 불가 상태

- 반환 bytes를 브라우저가 실제 표시했는지, decode/load 이후 표시 요소가 교체되지 않았는지까지 확인하지 않는다. 이후 renderer/브라우저는 검증한 동일 bytes를 사용하고 별도 표시 대조를 해야 한다.
- size는 Pillow가 해독한 자산의 픽셀 크기다. CSS 표시 크기·기기·EXIF 방향의 실제 브라우저 적용·H/A 관찰 이력은 검증하지 않는다. 이미지 의미/숨은 기존 표시·선정 독립성·사람 관찰·판정 출처는 SHA나 synthetic_fixture 자기 선언으로 증명하지 않는다.
- 실제 사진/라벨이나 원사진→파생 자산 생성 경로를 연결하지 않았다. 단일 프레임 PNG/JPEG만 지원하고 애니메이션/다른 형식은 거부한다. renderer·4상태 응답·receipt·원문/해시/거부 이유 영속 저장도 후속 범위다.
- 표시/수집 계약의 미정 기기·출처·표본 수·실제 절차·수용 수치 등은 그대로다. 별도 인력/비용 확보를 필수로 추가하지 않고 AI를 사람 정답으로 대체하지 않는다. 합성 검사 통과는 실제 수집 승인이나 모델 성능 근거가 아니다.
- 기존 원본 기록·.claude/·D-LOC·다른 worktree는 보존한다. 작업 브랜치/자체 환경만 사용하며 main은 변경하지 않는다.

## 검증 소스 SHA-256

- `card_condition/observation_assets.py`: `b8b470c8b27254552e431a625d0054defb53f61a3143a921595a2884e2e84c23`
- `tests/test_observation_assets.py`: `8a66e01eb1ea476718712811e4ab9fcebd005388bd45eed6252fd7ae24820de3`

## 인계·HTML·롤백

Git 제외 검사 로그/HTML: artifacts/synthetic-observation-assets-20261117/. HTML의 정확한 경로는 report.html이며 외부 CDN/API/실제 사진/사람 응답 없이 합성 결과만 담는다. 진척/기준 파일은 변경하지 않았다.

로컬 결과 커밋만 남긴다. 구현 철회는 결과 커밋만 git revert한다. 계약까지 철회하면 결과 다음 계약 커밋을 역순 revert하며 원본 기록·.claude/·D-LOC·다른 worktree를 삭제/복원하지 않는다. 실제 롤백·main 통합·push는 이번에 수행하지 않는다.

HTML: 열기 요청 성공(exit0), 실제 렌더 미확인.
