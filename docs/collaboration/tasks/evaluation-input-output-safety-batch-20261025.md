# Claude 평가 입력·결과 저장 안전성 묶음

- task_id: evaluation-input-output-safety-batch-20261025
- owner: Claude
- status: implementing
- base_sha: 9369ea5ff2ea6f0a86181688afa27825658ded17
- branch: claude/evaluation-input-output-safety-batch-20261025
- worktree/dispatch: Codex 전달 메시지 참조. 완료된 최초 provenance worktree를 재사용하되 새 브랜치로 시작한다.

## 완료 목표

side/region 평가가 개발 이력에 오염되거나 변경된 입력으로 성공 보고서를 만들지 않는지 검증하고, 저장 실패 때 부분 보고서를 남기지 않도록 한다. 원본 모델·실제 사진·정답을 사용하지 않고 합성 fixture와 mock analyzer로 API 호출 경로를 검사한다. 실제 모델 추론이나 성능 실험이 아니다.

기존 소스에서 입력 SHA를 읽는 시점과 실제 해석·사용 시점, 결과 open(x)/json.dump 경로를 읽고 반례부터 만든다. 코드가 올바른 항목은 검사만 남기고, 재현된 결함만 최소 보완한다. Mastra·지표 계산·snapshot/sidecar 작업에는 손대지 않는다.

## allowed_files (정확히 11개)

- card_condition/evaluation_inputs.py (기존: 함수 정의4개)
- card_condition/region_evaluation.py (기존: 함수 정의1개)
- card_condition/side_evaluation.py (기존: 함수 정의1개)
- card_condition/evaluation_output.py (신규, 필요할 때만: 두 평가기의 공통 새 파일 공개 helper)
- tests/test_evaluation_provenance_contract.py (신규)
- tests/test_evaluation_consistency_contract.py (신규)
- tests/test_evaluation_output_safety.py (신규)
- tests/test_evaluation_identity_contract.py (신규)
- docs/collaboration/tasks/evaluation-input-output-safety-batch-20261025.md
- docs/collaboration/reports/evaluation-input-output-safety-batch-20261025.md (신규)
- docs/collaboration/reports/evaluation-input-output-safety-batch-20261025.html (신규, 필수)

그 밖의 추적 파일은 읽기 전용이다. 기존 test_evaluation_inputs.py와 test_pipeline.py의 합성 fixture는 읽어 재사용할 수 있으나 수정하지 않는다. point/data/region/side 모델·worker·실험 실행기·공용 CLI·PAIR_CODING/AGENTS·지표 소스·관제 파일 변경 금지. 다른 파일에서 해결해야 하는 결함은 재현/최소 제안만 인계한다.

## 현재 지침과 환경

사용자의 미커밋 AGENTS/PAIR_CODING 구조 지침은 기본 checkout에 보존돼 있다. 새 브랜치는 커밋된 기준에서 시작하므로 다음 제한을 이 계약으로 명시한다: 변경 파일별 함수 정의(일반/비동기/메서드/중첩) 최대7개, 주요 호출 전이 최대4회. 테스트도 정의 수를 기록한다. 정의 수를 맞추려고 서로 다른 책임을 합치거나 호출을 숨기지 않는다. 변경 전/후와 파일을 넘는 주요 경로를 기록하고, 동적/mock/프레임워크 경로가 미확인이면 통과로 간주하지 않는다. 기존 장거리 호출 경로는 사실대로 명시하고 새 변경 범위와 구분한다. 제한을 지키며 보완할 수 없는 수정은 해당 재현만 남긴다.

자체 .venv는 같은 worktree의 기존 환경이며 torch/torchvision/Pillow가 requirements-tested.txt 버전으로 설치돼 있다. 새 설치·가중치 다운로드·다른 venv symlink/공유 없음. card_condition import가 현재 worktree의 최신 브랜치를 가리키는지 확인한다. source 편집은 ./develop -- <실제 수정 명령> 안에서 수행한다.

이전 ignored artifacts에는 과거 근거가 있을 수 있으나 읽거나 재사용하지 않는다. 이번 합성 fixture·결과는 동명 artifacts 하위 새 경로에만 둔다. 사진은 Pillow로 생성한 작은 합성 이미지뿐이며 실제 사진 열람은 금지한다.

## 1. 입력·출력 계약과 기준 검사 고정

세 기존 소스·평가 호출자·기존 test_evaluation_inputs.py를 읽는다. region 평가와 side final/regression의 의도된 차이를 기록하고 임의로 통일하지 않는다. history 제공 범위 밖의 실물 독립성이나 사람 정답을 프로그램이 증명한다고 주장하지 않는다.

기존 보고서 schema/필드/threshold/분모/성공 입력 수치/production_ready=false/actual_calls_saved=0은 유지한다. 정상 입력의 dict와 저장 JSON이 수정 전후 같음을 비교한다. 실제 source 변경 전 정상 합성 결과와 대상 source SHA를 ignored artifacts에 보존한다.

테스트는 평가 모듈이 사용하는 RegionAnalyzer/SideAnalyzer를 반드시 patch해 고정 확률만 돌려준다. 실제 생성자·backbone·feature·fit가 실행되지 않음을 mock/assert로 확인한다. checkpoint는 torch.save한 작은 metadata dict일 뿐 가중치가 아니다.

## 2. 개발 이력·identity 반례

- 평가 ID, group, decoded image hash가 각각 checkpoint metadata 또는 제공 history와 겹치면 analyzer 생성 전에 거절되는지 확인한다.
- 파일명/ID/group을 바꾼 동일 decoded pixels와 재인코딩 이미지를 합성으로 만들어 중복 우회가 없는지 확인한다. 바이트 SHA와 decoded SHA의 역할을 구분한다.
- 서로 다른 group으로 같은 평가 사진을 복사한 경우 거절한다. 동일 group의 유효 앞뒤/여러 구역은 무조건 중복이라고 배제하지 않는다.
- final의 혼합 split·누락 history·잘못된 metadata·지원 정답 없음 등의 실제 계약 거절을 검사한다. history가 실제로 완전하다는 의미 검증은 하지 않는다.
- malformed checkpoint/schema가 지원 범위를 벗어난다면 기존 upstream 전제와 예외를 먼저 확인한다. 새 포맷이나 라벨 기준을 발명하지 않는다.

## 3. 읽기 단계 간 일관성 반례

model/manifest/history/photo가 실제 사용 단계와 SHA 기록 단계 사이에 바뀌는 경우를 side/region에서 각각 조사한다. 기존의 실행 중 mutation 검사와 중복하지 말고 더 이른/다른 읽기 경계의 빈틈을 재현한다.

패치된 loader/analyzer로 합성 파일만 특정 시점에 A→B 또는 A→B→A로 바꿔 본다. 실제로 관측한 내용과 기록된 SHA/identity가 불일치한 채 성공하는 경우를 정확히 기록한다. 단순 최종 digest 비교만으로 모든 순간의 불변성/TOCTOU 해결을 주장하지 않는다. 재현된 경우에만 허용 소스에서 관측된 snapshot 연결을 보완한다. 디렉터리 전체 잠금·파일 감시 daemon·generic snapshot framework는 추가하지 않는다.

PNG 바이트만 달라지고 decoded pixels는 같은 경우는 identity 중복 판정과 입력 바이트 변경 보호를 구분한다. 기존 byte snapshot 계약이 변경을 거절하는 것은 곧 오탐 버그가 아니다. 유효한 입력이 임의로 배제되지 않도록 계약을 먼저 확인한다.

## 4. 저장 실패 안전성 재현·최소 수정

두 평가기의 현재 open(x)→json.dump 경로에서 일부 쓰기 후 OSError, 직렬화 오류, flush/fsync/link 오류를 주입해 본다. 정상 결과만 최종 파일로 공개하고 실패 시 최종 파일 없음/재시도 가능인지 확인한다. 기존·경쟁 출력은 보존해야 한다.

재현되면 두 평가기가 공유하는 최소 evaluation_output.py helper를 둘 수 있다. 기존 data_coverage와 side_evidence_cli의 동일 폴더 임시 파일→flush/fsync→덮어쓰기 없는 공개 패턴을 참고하되 그 파일을 수정하거나 도메인 CLI 모듈에 평가기를 결합하지 않는다. 새 범용 writer framework·의존성은 만들지 않는다.

기존 출력에 대한 정상 early rejection과 경쟁 파일 생성 시 no-clobber를 유지한다. 원본 manifest/checkpoint/history/photo를 출력 경로로 덮어쓸 수 없게 한다. 새 파일 권한 변화·hardlink 미지원·강제 종료 temp 잔존·전원 상실 내구성의 한계를 기록한다. 실패 후 기존 출력이나 경쟁자의 파일을 cleanup하면서 지우지 않는다.

## 5. mock 종단 검증과 반례 검토

side final/regression, region 및 합성 point-grid 경로에서 해당 구현 범위의 정상 결과 보존을 확인한다. geometry·unknown·supported label이 결과 분모를 어떻게 제한하는지 검사하고 이번에 지표 알고리즘을 수정하지 않는다. 실제 모델 출력 생성은 금지하며 목업으로 반환한 확률만 쓴다.

새 source 결함은 먼저 실패하는 검사를 커밋하고 최소 수정한다. 검사 자체의 손계산 실수·미지원 입력·API 전제 위반을 source 결함과 구별한다. 무작위 대량 fuzz나 성공 수 채우기는 하지 않는다. 위험한 몇 분기의 mutation 대조가 필요하면 임시 복사본에서만 수행한다.

## 6. 전체 검사·HTML 열기·인계

안전한 기존 기준 검사는 아래 test_evaluation_inputs뿐이다. test_side_evaluation/test_region_evaluation/test_point_final_evaluation/test_pipeline 전체 모듈은 실제 학습·추론이 들어 있으므로 실행하지 않는다. fixture 함수를 import하는 것과 test 모듈 전체 실행을 구분한다.

```sh
PYTHONPATH=tests .venv/bin/python -m unittest test_evaluation_inputs test_evaluation_provenance_contract test_evaluation_consistency_contract test_evaluation_output_safety test_evaluation_identity_contract -v
.venv/bin/python -m compileall -q card_condition/evaluation_inputs.py card_condition/region_evaluation.py card_condition/side_evaluation.py
# evaluation_output.py가 생겼으면 이 파일도 compileall 대상에 추가
git diff --check
```

문서에 실제 test 명령/개수·변경 source와 실패 재현 SHA·정상 결과 동일 비교·함수 수/주요 경로·미검증·리스크·롤백을 기록한다. Codex가 main에서 관련 통합 검사를 추가 실행한다.

HTML_REPORTING.md를 반드시 따른다. allowed_files의 정적 HTML에 고정 기준 진척률·이번 성과·실제 검사·미실행·구조·근거·리스크·롤백을 담는다. PROGRESS_CRITERIA/development-progress.json을 읽고 30/100의 의미를 표시한다. mock/API 보호 검증이지 모델 성능 평가가 아님을 명시한다. 성과가 없는데 정확도 그래프를 만들지 않는다. 개인 경로·실자료·외부 CDN/스크립트 없음. HTML을 내용 검증하고 실제 브라우저로 연다. 열기 요청 성공과 렌더 확인을 구분하며 차단 시 오류·절대경로 링크를 인계한다. 링크만 주고 열기 단계를 생략하지 않는다.

status ready_for_review, 전체 SHA 순서/부모/변경 파일/검사/HTML 경로·열기 결과/미검증/리스크/롤백/깨끗한 worktree로 인계한다. source 변경이 없어도 유효한 결과이며 의미 없는 코드를 추가하지 않는다.

## 금지·종료·롤백

실제 학습·모델 추론·실자료·사람 라벨 변경·외부 AI/Codex CLI/review --auto·API 호출·자동 수집·Mastra·main 통합/push 금지. 이 작업은 mock 소프트웨어 검증이므로 새 성능 실험을 시작하지 않는다. 실제 모델 실험이 필요하면 별도 계약/공통 실행기 계획이 필요하다.

6단계 완료 또는 실제 근거/권한/컨텍스트 한계에서 체크포인트를 남긴다. 한 항목만 막히면 독립 단계를 계속한다. 임의 기능으로 범위를 늘리지 않는다. 롤백은 미통합 또는 전달 커밋 역순 revert이며 실제 모델·라벨 변경은 없어야 한다. 진척 점수·배점·수치 기준 불변. main 통합·관련 검증·일반 push는 Codex가 담당한다.
