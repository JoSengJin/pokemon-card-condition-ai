# 요청 내 사진 디코딩 중복 제거 — 2026-10-28 KST

**개발 진척률 30/100(+0%p). context 추론의 입력 최적화를 반영했다. 선행 실측 중앙 처리시간은11.38%감소, 점수 차이는0이며 정확도 변화는 없다.** 두 모델 모두5%를 요구했던 전체 가설은 타일의1.89%감소 때문에 미수용이다. 그 판정은 유지하고 context 구성요소만 남겼다.

## 실제 변경과 적용 범위

기존 ListingAnalyzer와 infer_listings는 같은 사진의 구역마다 view_tensors를 새로 열었다. context 경로에서는 이제 한 면의 구역을 같은 스트림으로 순서대로 준비한다. 같은27구역/9면에서 사진 디코딩은27→9회로 줄었다. 요청·사진·모델 간 캐시나 전역 상태는 만들지 않았다.

crop floor/ceil, EXIF/RGB, padding·resize·정규화, 구역당 모델 forward shape/순서, pooling, checkpoint,0.5,지원범위, 관찰제한/glare·보류·입력SHA검사는 유지했다. 학습0·새라벨0·새백본/의존성다운로드0·외부AI0이며 Claude 데이터 확보/검토파일·새사진/정답·모든 Claude checkout을 수정하지 않았다.

외곽view/tiles/tiles-max는 실측 기준에 미달한 타일 일반화를 피하도록 원래 구역별 features_for 경로로 복원했다. 최종 회귀는 context일 때1회, 나머지는 구역 수만큼 디코딩하는지 검사한다. batch_views는 기존 선택 그대로다.

## 사전 기준과 실측 결과

- 공통 실행 record: **artifacts/experiments/20261027T225304-e0ad355a/record.json**, status=completed. timing_acceptance_passed=false, 기존 품질 전체 acceptance_passed=false다. 실행 완료와 가설 수용을 구분한다.
- 실측 source **fda342c**, 최종 source **71a4f9be197a79f034d32d5b5f6291a34e1ff1a4**. 최종 변경은 context의 동일 공유 경로를 보존하고 타일 진입만 기존 경로로 복원한 것이다. 실측·실패 plan/record/snapshot·결과를 덮어쓰지 않았다.
- 두 기존 연구 checkpoint(context/tiles)와 각 report의 같은27개 known·지원 엣지 구역(양성15/정상12)/9면을 고정했다. source report의 기존 정답과 box를 보존했으며 과거 다른26구역이나 표면147구역과 혼합하지 않았다.
- CPU2threads,동시성1,batch_views=False,모델로딩 제외. 각 경로1회warmup,7회씩 순서를 교대했다. 최소 median5%감소를 두 모델 각각에 요구했다. 7회 p95는 nearest rank=max이며 운영 지연 상한이나 통계적 우위를 뜻하지 않는다.

| 경로 | 중앙값 기존→실험후보 | 감소율 | 표본p95 기존→실험후보 | 최종 소스 |
|---|---:|---:|---:|---|
| context | 1.163→1.031초 | 11.38% 감소 | 1.428→1.060초 | 유지 |
| tiles | 4.936→4.843초 | 1.89% 감소 | 5.088→5.106초 | 기존 경로 복원 |

전체 timing 가설 실패를 통과로 바꾸지 않았다. 타일은 기존 경로로 복원했으며 같은 자료/조건을 다시 측정해 유리한 수치로 대체하지 않았다. context의 측정된 공유 처리 본문은 유지하되, 최종 fallback 분기의 별도 속도 실험은 실행하지 않았다. 이 측정은 장치·입력 크기·동시성을 바꾼 실사용 성능이나 MPS 속도를 증명하지 않는다.

## 같은 정답·분모의 모델 성능

두 checkpoint 각각 기존 단일구역 경로와 실험 공유 경로에서27개 모든 점수가 bitwise 동일했고 최대차0, 판정 변화0이다. 아래 두 checkpoint끼리는 품질 개선 비교를 하지 않는다. 각각 자신과 전후 비교한 수치다.

| 연구 checkpoint | 누락 전→후 | 오탐 전→후 | 전후 변화 |
|---|---:|---:|---:|
| context |7/15 (46.67%)→7/15|5/12 (41.67%)→5/12|각0.00%p|
| tiles (최종 미채택 공유경로) |0/15 (0%)→0/15|12/12 (100%)→12/12|각0.00%p|

별도로 기존 보호147/11cohort는 동결된 checkpoint와 cache 특징으로 실제head 재생을 검산했다. 표면 누락16/94(17.02%),오탐18/53(33.96%),올바른종류 실제점 누락21/51(41.18%)은 동일(각0%p)이다. 이는 변경하지 않은 모델의 재생 보호이며 이번 속도 최적화로 표면 모델이 향상됐다는 뜻이 아니다. 품질 기준은 여전히 미통과이고 독립 일반화 개선도 미확인이다.

## 변경 파일과 핵심 diff

- `card_condition/edge_views.py`: context 구역 여러 개에 기존 view_tensors 스트림을 공유하고 순서대로 소비한다. 한 구역의 view만 tensor로 준비한 뒤 해제한다. 기존 단일구역 patch_features와 batched_patch_features의 기본 호출은 유지한다. 타일/외곽view는 원래 구역별 함수로 돌린다.
- `card_condition/region_model.py`: analyze_regions가 구역별 feature를 준비해 기존 analyze의 점수/지원/unknown 표시를 재사용한다. 기존 analyze의 위치 인자와 반환 필드는 유지하고 내부용 사전계산 feature만 선택적으로 받는다.
- `card_condition/listing_model.py`: 같은 관찰가능 구역 순서로 primary/recall을 묶어 호출한다. observation 모델·정답 선택·입력 SHA/race·readiness 정책 불변.
- `card_condition/listing_inference.py`: 같은 면의 기존 eligible patches를 묶어 같은 feature 경로로 전달한다. head 계산·출력 순서와 null/지원 조건 보존.
- `tests/test_region_decode_once.py`: 기존4정책×2해상도×2batch 선택에서 확률/geometry/null 완전동일, context1회·다른정책9회, 빈요청0회·다음요청 재읽기 검사2개.
- `tests/test_listing_model.py`, `tests/test_listing_coverage.py`: 기존 mock을 여러구역 호출에 연결. `tests/test_listing_inference.py`: 기존 OOM/입력변경 fault injection을 실제 이동한 호출 위치로 연결. 이 기존 검사 조건과 개수는 유지했다.
- `tools/experiments/region-photo-decode-once-20261028/worker.py`, `plan.json`: 변경 전 snapshot과 고정 입력·실측/판정·기존 checkpoint 재생·사진보고를 기록하는 이번 작업 전용 파일이다. 범용 benchmark 도구/제품 UI는 추가하지 않았다.
- task 문서와 이 MD/HTML: 사전 계약, 실측 전 분모 확인, 실측 뒤 실패/채택 범위, 검증·리스크·롤백.

## 실행 검증·구조·기록

최초 공유 구현은 격리24개 OK(28.208초), main24개 OK(29.300초). 타일 복원 뒤 최종 소스는 격리30개 OK(31.547초), main30개 OK(30.626초)다. 검사 증가분은 기존 recall/관측 세 checkpoint 연결 검사를 실행한 것이며 새 합성 검사를 성능 개선으로 세지 않았다.

명령: `PYTHONPATH=tests .venv/bin/python -m unittest test_region_decode_once test_region_api test_listing_model test_listing_inference test_listing_coverage test_edge_views test_release test_listing_loaded_checkpoint test_recall_review test_listing_review_evidence`.

실측 명령: `./experiment --plan tools/experiments/region-photo-decode-once-20261028/plan.json -- .venv/bin/python artifacts/region-photo-decode-once-20261028/worker.py`. 날짜 폴더는 UTC이며 실행은KST2026-10-28이다. 수정 전 snapshot은 base1a0c3c1의 Git blob과 일치했다. source 편집·통합은 ./develop, 공통 실행은 기본 checkout에서 한 번 직렬 실행했다.

함수 수는 edge_views7/region_model3/listing_model3/listing_inference1, 신규검사2, 기존검사5/4/7,worker3으로 각7이하다. 주요 프로젝트 경로 Listing→analyze_regions→region_features→patch_features→fixed_tile_boxes, 또는 Listing→analyze_regions→region_features→view_tensors→prepared_image는 최대4전이다. view 전처리는 다음 feature 호출 전에 소비해 호출 깊이를 늘리지 않았다.

입력 사진·checkpoint·기존 report/manifest·cache·기존 head와 공통record.files SHA를 대조했다. 실측 뒤 의도한 소스 차이는 최종 타일 복원 edge_views.py뿐이며 실험 code snapshot은 원형으로 보존됐다. 새 자료나 model weight·학습/평가 split·사람 정답·진척/수용 기준 변경은0이다.

development-review.json session_id는 현재 세션과 달라 이번 자동 handoff/next_steps/token_report는 생성되지 않았다. development-cycle/latest.json의 이전 ai_calls_forbidden 기록을 이번 기록으로 바꾸지 않았다.

## 사진·보고·리스크·롤백

사진27구역의 원래 정답과 두 checkpoint의 전후 점수는 `artifacts/experiments/20261027T225304-e0ad355a/index.html`이다. 빨강/초록 테두리는 해당 구역의 사람 손상/정상이며 모델 위치 검출이 아니다. 정상점·전체손상범위가 없어 위치정확도/IoU를 주장하지 않는다. HTML 상단에 최종 context 한정/타일 복원과 원래 실험 실패를 따로 표시했다.

보고서와 사진 HTML 열기를 요청했고 두 도구 응답 모두 queued였다. 사진 구역 PNG 1개를 직접 확인했다. 파일/수치/MD·HTML 본문·record SHA는 검증했지만 HTML 실제 렌더는 미확인이다.

위험과 미검증: 한 면의 디코딩 RGB를 스트림 동안 보유하지만 요청 간 잔류 캐시는 없다. 실제 RSS/MPS 메모리 peak, MPS·448 실제 처리시간, 동시부하, 실사용p95는 측정하지 않았다. 두 연구 checkpoint의 품질은 낮으며 이 속도 변경이 Gemini 우회나 운영 모델 채택을 뜻하지 않는다. PokeCollector와 운영 fallback은 변경하지 않았다.

전체 코드 롤백은 `./develop -- git revert --no-edit 71a4f9b fda342c` 후 위 검사와 일반 push다. 71a4f9b만 되돌리면 미채택 타일 공유 경로가 다시 켜지므로 두 구현 커밋을 순서대로 되돌린다. 원본 사진·정답·모델 복구는 필요 없고 실험과 실패 이력은 보존한다.

## 원격·checkout 정리와 다음 의존

검증 source main/origin71a4f9b 일치를 확인하고 이전 Codex all-human-points checkout만 전달 커밋의 main 대응·clean·진행중Git없음·비차단개발잠금·고유lock증거SHA보존 후 일반 worktree remove로 정리했다. 최근 codex/region-photo-decode-once-20261028 checkout6064dcf는 롤백 확인용으로 유지하며 Claude 데이터/미통합/작성중 작업은 모두 보존했다. 감사: artifacts/region-photo-decode-once-20261028/worktree-cleanup/audit.json. 결과 문서는 후속 커밋으로 일반 push한다. force push/이력 재작성 없음.

새 정확도 개선 학습은 이전에 확인한 다양한 training 실물의 직접 확인 자료 의존을 유지한다. 이번에는 Claude 데이터 확보를 중복 실행하거나 val 자료를 학습으로 옮기지 않았다.

## 에튜 포인트

요청 안에서만 재사용하면 입력이 다음 요청에서 바뀌어도 낡은 사진을 쓰지 않는다. 이번에는9구역의 crop을 한 번 읽은 사진에서 순서대로 만들되, crop·모델 연산은 그대로 뒀다. 다만 타일 모델은 모델 계산이 대부분이라 디코딩을 줄여도1.9%에 그쳤다. 입력 최적화의 효과는 전체 처리시간에서 그 입력 작업이 차지하는 비중에 제한된다.
