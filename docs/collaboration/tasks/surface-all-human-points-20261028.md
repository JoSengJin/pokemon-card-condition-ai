# 기존 표면 다중 클릭 활용: 단일 변경 계약

- task_id: surface-all-human-points-20261028
- owner: Codex
- status: integrated
- base_sha: f58a98aadb43d9796e5ecc63577b7f86f3029509
- branch: codex/surface-all-human-points-20261028
- worktree: 로컬 전용, 원격 문서에 경로 기록하지 않음
- goal: 새 val 자료를 학습에 사용하지 않고 기존 training fold의 미사용 표면 클릭 토큰을 활용해 기존 평가를 개선하는지 한 번 비교한다.

## 근거와 변경 변수

point_dataset.point_rows(grid=True)는 같은 종류·구역의 첫 클릭만 point_by_label에 보존한다. 고정 원본 d971dbca…의 기존147구역에는 올바른 종류 표면 클릭83개/51양성구역이 있고 앞면만37개/18구역이다. 현재 한 토큰만 감독하므로 앞면19토큰을 사용하지 않는다. 추가자료는 새 정답이 아니라 같은 원본의 기존 클릭이다. 153행 중 별도 실제점2개는 그대로 유지한다.

새 가설: 같은 positive bag 안의 중복되지 않는 기존 표면 클릭 토큰에 softplus(-logit)를 평균하면 한 점 선택 편향이 줄어들 수 있다. 변경은 point loss가 첫 토큰 하나에서 기존 고유 토큰 평균이 되는 것 하나다. 구역/클래스/실물 mass·기존 첫 점으로 계산한 center·zero 초기값·L2=1·max_bound·LBFGS100·gradient1e-5·입력224/RGB·4fold·뒤 map·.5·11cohort·기존147/51정답/수치조건을 고정한다. ranking항·새 정답/샘플·val편입·추가 계수/초기값 탐색은 없다.

## allowed_files

- tools/experiments/surface-all-human-points-20261028/objective.py
- tools/experiments/surface-all-human-points-20261028/worker.py
- tools/experiments/surface-all-human-points-20261028/plan.json
- tests/test_surface_all_human_points.py
- docs/collaboration/tasks/surface-all-human-points-20261028.md
- docs/collaboration/reports/surface-all-human-points-20261028.md
- docs/collaboration/reports/surface-all-human-points-20261028.html

ignored: artifacts/surface-all-human-points-20261028/ (원본 무변경 SHA와 a~e 최신 상태 집계·출처/학습금지), 공통 실행기의 새 artifacts/experiments/<run>/record.json·observations.json·index.html·사진.
금지: Claude checkout·수집/검토파일·라벨/geometry·manifest·캐시·기존실험/모델·운영소스·PokeCollector·Gemini fallback·진척/기준 수정, 외부AI·설치/다운로드, 구현worktree 실제 실험.

## 구조·검증·실험

- objective.py: 신규 함수 최대5(closure포함), worker.py 신규 최대3, 테스트 최대4. 주요 fit->closure->point loss->detail_bag_loss->point_bag_loss는 최대4전이. 다중점 경로는3전이.
- raw source SHA·각row image/box/card_box/group/target·기존 최초토큰 포함·모든추가토큰 valid mask·새kind/point 생성0·fold held그룹/raw/decoded분리·검토입력 전후 SHA 보존 검사.
- 한 점일 때 기존 fit/loss 동치, 다중점 평균과 중복 제거/기울기, 잘못된 mask/첫점 누락 거절의 소수 검사. 단위검사는 모델 개선 증거가 아니다.
- 계약 커밋 후 ./develop 안에서 구현, 격리검사 후 main 통합/재검사. 공통 ./experiment --plan … -- …로1회 직렬 실행한다.
- 사전 성공: primary FN<=16/94,FP<=18/53,새오류0,typed51 기존누락 보호,최소1기존오답복구 및 기존11cohort 품질조건 전체. 하나라도 실패하면 미채택. 수렴/입력/SHA 실패는 failed, 평가점수로 대체하지 않고 기준변경/자동재시도0.
- plan에 전체 baseline/입력 SHA, code_changes 신규 baseline=null, 기존 실패 가설과 다른점 기록. 새 자료는 val 전용/출처감사·채택 미완 상태를 사실대로 보고하고 학습0.
- HTML에 고정30/100·사진 위 정답/출력·같은분모/%p·기존51과추가학습점구분·수치/파일대조를 기록하고 open요청/실제렌더확인을 구분한다.

## 인계·리스크·롤백

실행record/status/판정·소스SHA/검사·변경파일·side effect·원격SHA일치·미검증·남은의존을 기록한다. 다중점은 독립실물 수를 늘리지 않으며 전체구역감독이 아니다. 원본 클릭/정답은 그대로, 연구후보 미채택이면 운영변경0. 제거는 통합source커밋을 ./develop -- git revert 후 관련검사/일반push, ignored실험은 보존한다. 최신완료checkout 하나 유지 규칙과 unique증거SHA보존을 지키며 Claude/미통합checkout은 보존한다.


## 실제 실행 인계

source70dda82, 격리source5142f4e. 관련14검사 양쪽OK, 함수4/2/3·최대4전이. record20261027T222515-1d33d82d statuscompleted/4fit수렴/수용false. 같은147 FN16→12/94,FP18→20/53,typed21/51동일. 새누락0·오탐2로미채택. 새val a~e 읽기전용확인,학습0·라벨변경0·운영0. 보고서는 동명reports MD/HTML, 사진은실험폴더 index/comparison.html. 입력·record SHA와수치대조완료,열기요청/렌더미확인은최종기록참조. 일반push후최근완료checkout1개만유지하며Claude/미통합작업은보존한다.
