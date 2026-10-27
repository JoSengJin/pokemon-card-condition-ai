task_id: listing-coverage-assessment-20261027
owner: Codex
status: implementing
base_sha: 692f7666bc703495e688856bbd32af7487e98683
branch: codex/listing-coverage-assessment-20261027

goal: 동결 사람 정답과 같은 릴리스의 저장 listing-predict 결과를 연결해 E2의 알려진 관찰가능 필수셀 비보류 coverage를 실제 집계하는 읽기 전용 경로를 제공한다.

allowed_files:
- card_condition/listing_coverage.py
- card_condition/listing_coverage_inputs.py
- tests/test_listing_coverage.py
- docs/collaboration/tasks/listing-coverage-assessment-20261027.md
- docs/collaboration/reports/listing-coverage-assessment-20261027.md
- docs/collaboration/reports/listing-coverage-assessment-20261027.html
ignored: artifacts/listing-coverage-assessment-20261027/ 합성 CLI 시연·검사·HTML만.
forbidden: 기존 모델·학습/실험·listing/평가/라벨/coverage UI 소스, Claude의 모든 checkout/신규데이터·사진·정답, PokeCollector, 비밀설정, 진척점수/완료조건, 외부AI 호출. 다른 task의 파일은 읽기 전용.

입력: val 또는 test 단일split의 manifest, 기존 pinned release, 외부 SHA로 고정한 bundle. bundle에는 manifest/release SHA와 사례id별 request/report 경로·원래 SHA를 둔다. 기존 정답/사진/box와 요청이 맞아야 한다. report/release/model SHA·필수셀·score/state/hold 이유는 현재 listing_readiness 정책으로 재계산해 일치 대조. 실제 모델을 로드해 forward하거나 정답으로 구역을 선택하지 않는다.

분모: 필수46셀(각면 corner4/edge8/surface9/centering1/observability1) 중 명시적 정답과 사람이 확인한 관찰가능 영역만. box_reviewed=true와 visibility_issues 명시 확인을 요구한다. 구역 정답/같은 종류 사람점은 기존 point_rows(grid=True) 투영을 사용한다. 전체면 정상을 구역 정상으로 옮기지 않는다. 부분glare는 해당구역만 제외하며 전체면 질문은 전체 관찰가능할 때만 포함. unknown/미검토/제외사유를 보고하고 임의0으로 만들지 않는다.

분자: 현재 API state normal/defect인 분모셀. unknown/미지원/결과미제공/누락사진은 분모에서 빼지 않는다. 사람이 관찰가능한 원본 사진을 요청에서 빼도 coverage를 올릴 수 없다. 현API에 없는 전체면 모델질문은 보류. review_record의 ground_truth=false를 정답으로 승격하지 않는다. 숫자>=70%와 E2실제완료는 분리하며 e2_verified/production_ready=false를 유지한다. 기존C FN/FP 분모/기준 변경 없음.

구조: 입력검사 모듈3함수 이내,집계 모듈3함수 이내. assess→checked_case→listing_readiness/photo_request→validate_annotations→validate_defect_points = 최대4전이. CLI는 모듈guard에서 assess를 직접 호출한다. fit/추론 호출 없음.
checks: 작은 합성 자료의 실제 ListingAnalyzer 생산 결과로 입출력 연결, known/unknown/부분glare/누락report/누락사진/미지원 분모 보존, SHA·geometry·중복·잘못된 점수/정책 거절, 기존출력/원본보존, CLI. 실제품질/독립평가/운영시나리오완료 아님.
HTML: 동명reports HTML과 ignored 합성 CLI보고서를 생성·내용대조·열기요청. 실제렌더가차단되면 구체적으로기록. 진척30/100유지(고정완료조건이실제충족되지않는한).
rollback: 통합코드커밋을 ./develop -- git revert 후관련검사/일반push. 원본데이터/모델/기존결과를수정하지않아복구불필요.

## 구현 인계

- 상태: ready_for_review. 신규 집계모듈2함수/입력모듈3함수/검사7함수(AST실측). assess→checked_case→listing_readiness/photo_request→validate_annotations→validate_defect_points 최대4전이. CLI는모듈guard직접호출.
- 신규5검사와기존매물/보류/전체면검토/릴리스회귀합계23검사통과(격리checkout,8.433초),git diff --check와컴파일통과.
- 합성테스트는기존ListingAnalyzer 생산코드에Mock구역점수를주입해저장결과를만든다.집계호출중RegionAnalyzer생성이없음을검사했다.실제모델정확도/독립평가를측정하지않았다.
- manifest의box_reviewed/명시적visibility/지역정답은분모준비요건이며미준비셀을제외사유별공개한다.부분집계가A3/E2완료를증명하지않는다.각질문/면집계와누락사례도보존한다.
- 공개API: python -m card_condition.listing_coverage MANIFEST RELEASE BUNDLE OUTPUT --bundle-sha256 SHA. bundle은 schema_version1/manifest_sha256/release_sha256/cases,각case는id와request/report의path/sha256이다.기존cli.py수정없음.
- 실제자료집계는Claude데이터보완후동결정답과같은릴리스의원래요청/결과SHA가필요하다.새정답/실제coverage를만들거나과거미동결자료를독립으로재명명하지않는다.
- main통합후동일관련검사/합성CLI시연/HTML생성·열기결과를동명보고서에기록한다.
