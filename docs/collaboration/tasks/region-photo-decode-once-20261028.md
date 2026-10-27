# 같은 면의 구역 추론에서 사진 1회 디코딩

- task_id: region-photo-decode-once-20271028
- owner: Codex
- status: implementing
- base_sha: 1a0c3c1c85a01a5f15c989a888ee0856532a8d53
- branch: codex/region-photo-decode-once-20271028
- worktree: 로컬 전용
- goal: 같은 사진의 여러 기존 구역을 추론할 때 출력/판정은 유지하고 중복 디코딩과 실제 처리시간을 줄인다. Claude 자료 확보·검토와 독립이다.

## 근거·변경 변수·보존

ListingAnalyzer.analyze와 infer_listings는 같은 면의 각 구역마다 patch_features를 호출하고, patch_features가 매번 view_tensors에서 사진을 연다. 기존 view_tensors는 한 구역의 여러 view만 1회 디코딩하며 여러 구역 간에는 공유하지 않는다.

동일 면의 정해진 구역 순서를 묶어 단일 view_tensors 스트림을 소비한다. crop floor/ceil, EXIF/RGB, padding/resize/정규화, 한 구역당 모델 forward/순서와 pooling·batch_views 선택·checkpoint·threshold/지원영역·관찰제한·보류·입력SHA/완전성검사는 유지한다. 요청 간·모델 간·사진 간 캐시나 전역상태는 추가하지 않는다. pretrained 다운로드·학습·신규데이터 사용·외부AI 0.

## allowed_files

- card_condition/edge_views.py
- card_condition/region_model.py
- card_condition/listing_model.py
- card_condition/listing_inference.py
- tests/test_region_decode_once.py
- tests/test_listing_model.py
- tests/test_listing_coverage.py
- tests/test_listing_inference.py
- tools/experiments/region-photo-decode-once-20271028/worker.py
- tools/experiments/region-photo-decode-once-20271028/plan.json
- docs/collaboration/tasks/region-photo-decode-once-20271028.md
- docs/collaboration/reports/region-photo-decode-once-20271028.md
- docs/collaboration/reports/region-photo-decode-once-20271028.html

ignored artifacts/region-photo-decode-once-20271028/ (수정 전 Python snapshot/후속 인계·감사), 공통 실행기의 새 artifacts/experiments/<run>/record·speed·사진 HTML.
금지: Claude 모든checkout/수집·검토/새사진·라벨/manifest/cache/head/과거실험, 기준·점수, PokeCollector·운영 Gemini 경로, provider호출. side_experiment.py와 학습 경로의 기본 동작은 변경하지 않는다.

## 구조·관련 경로

edge_views 함수6→7, RegionAnalyzer 메서드2→3, listing_model3→3, listing_inference1→1. 새 검사 최대4함수, 기존 검사 파일은7이하 유지. worker최대5함수. Listing.analyze→Region.analyze_regions→region_features→patch_features→fixed_tile_boxes 최대4전이. 준비된view는 feature호출 전에 소비해 preprocessing 경로 Listing→many→region_features→view_tensors→prepared_image도4전이를 지킨다.

## 검사·실제 성능 실험

- context/views/tiles/tiles-max 및224/448, batch_views on/off에서 단일/여러구역 확률·geometry·null 동일, 디코딩횟수 N→1, 빈구역0회, 다음요청 사진재읽기(캐시잔류0)를 작은 회귀로 검증한다.
- 기존 listing의 관찰제한·미검토·glare·누락면·관측모델·recall·출력SHA/race·CLI 경로 관련 검사를 실행한다. fake 검사와 실측을 구분한다.
- 계약/계획/소스 고정 후 기본 checkout에서 ./experiment --plan … -- …를 사용해1회 측정한다. 새 checkpoint/자료/학습은 없고 기존 edge context/tiles checkpoint와 그 report의 동일27 개발구역만 사용한다. 구역 정답/분모를 바꾸지 않는다.
- CPU2threads·동시성1·기존 batch_views=False 고정, 모델로딩 제외, 각 경로1회warmup 후7회 교대 측정. 각모델의 확률차<=1e-7·판정/분모동일·디코딩N→유일면수·입력SHA보존 필수. 각모델 median 최소5%감소를 성공으로 사전명시한다. p95는7회 측정 표본의 nearest rank이며 운영 p95로 외삽하지 않는다.
- 속도뿐인 변경이므로 정확도 변화없음을 보고한다. 기존147/11cohort는 저장점수를 그대로 replay해 보존만 확인하며 이를 새품질통과로 해석하지 않는다. 기존 연구 checkpoint의27구역 FN/FP·분모·전후0%p를 별도로 명시한다. 독립 일반화/운영채택은 주장하지 않는다.
- SHA/동치/시간기준 실패시 그대로 기록, 기준변경·반복실험/백그라운드실행0. 속도 개선 없으면 복잡성만 늘리지 않도록 변경 채택을 재검토한다.

## HTML·인계·리스크·롤백

고정진척30/100·실행sourceSHA·실제속도/출력동치·사진 위 기존정답/모델출력/27분모·MD/HTML수치대조·열기요청/렌더확인상태를 기록한다. 모델 학습0/성능품질개선0를 명시한다. 결과와checks/handoff에HTML경로를 넣는다.

입력사진은 면당 1장의 디코딩RGB를 해당 스트림 동안 보유한다. 구역view는 기존 한 구역 분량만 보유한다. 메모리/CPU/MPS별속도/처리량 일반화는 실측없으면 미확인으로 둔다. 운영fallback/라벨/정답은 불변이다.
롤백: 통합 소스커밋을 ./develop -- git revert 후 관련검사/일반push, 실험기록은 보존. 통합·push뒤 기존 Codex 완료checkout만 잠금/고유증거SHA 확인 후 정리, 최근1개 유지. Claude/미통합 checkout보존.

계약 보충: infer_listings의 실제 feature 호출 위치가 edge_views.region_features로 옮겨져, 기존 OOM/입력변경 fault-injection 검사의 patch 대상을 실제 호출 위치로 옮긴다. 테스트 수/조건은 늘리지 않는다.

실측 입력 정정(실행 전): 지정된 기존 report를 직접 파싱하니 정확한 지원/known 평가는27구역(양성15·정상12)/9면이다. 과거 다른26구역 benchmark와 혼동하지 않는다. 이 원래 report의 정답·구역/순서를 사전 필터 규칙으로 고정하며 원본을 바꾸지 않는다. 속도/동치 수용 기준은 동일하다.
