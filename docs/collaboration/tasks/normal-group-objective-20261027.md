task_id: normal-group-objective-20261027
owner: Codex
status: implementing
base_sha: 084a2c3b854f59cbe4d5d6f72e10312e8a1ba95c
branch: codex/normal-group-objective-20261027

goal: H3 실제 측정에 근거해 정상 실물 간 손실 집계 하나만 바꾼 앞면 고정4-fold 후보를 개발평가한다.
allowed_files:
- tools/experiments/surface-normal-group-objective-20261027/objective.py
- tools/experiments/surface-normal-group-objective-20261027/worker.py
- tools/experiments/surface-normal-group-objective-20261027/plan.json
- tests/test_normal_group_objective.py
- docs/collaboration/tasks/normal-group-objective-20261027.md
- docs/collaboration/reports/normal-group-objective-20261027.md
- docs/collaboration/reports/normal-group-objective-20261027.html
ignored: artifacts/surface-normal-group-objective-20261027/ 미러·출력검사, 새 실험 폴더 산출물만.
forbidden: card_condition/*, Claude checkout, 데이터 확보/라벨/사진/manifest/캐시·기존실험 수정, consumer, 운영모델, 범위/배점/완료조건, 외부AI 호출.

가설: H3에서 정상 c/ㄴ의 상호제외가 각각FP+3/9,+4/9였다. 평균 정상 손실은 어려운 정상 실물의 손실을 나머지 정상 실물로 희석할 수 있다. 같은 정상 bag loss를 실물별 평균한 뒤 temperature0.1 log-mean-exp로 묶으면 미관찰 정상 실물에 대한 FP가 줄 수 있다. 인과로 확정하지 않는다.0.1은 기존 max_bound 고정 평활상수 재사용이며 탐색/조정하지 않는다.

변경 변수: 앞면 정상 실물 간 집계만 산술평균→0.1*log(mean(exp(group_loss/0.1))). 양성항 가중치0.5·정상항0.5·L2=1·중심화·max_bound·실제점감독·특징153행·4fold·threshold.5·뒷면maps 고정. 참조는 122011 공동제외 결과이며 동일147행 FN16/94·FP18/53,typed21/51. 기존11required_cohorts 삭제/완화 금지.

사전 성공: 같은147행에서 FN<=16, FP<=18, 새오답0, 적어도1오류복구, typed51 신규누락0, 기존11cohort 전체통과. 미충족/변화없음은 미채택. 수렴·분리·재현·SHA 실패면 failed이며 수치성과로 해석/자동재시도하지 않는다.

실행: 기본checkout의 ./experiment --plan ... -- .venv/bin/python artifacts/.../worker.py 한 번. 수정은 own worktree ./develop 안에서, 실제캐시·사진 접근/학습은 기본checkout만. 워커는既存coex baseline replay와 front fold검증/사진render를 재사용한다. 비교 시작 전에 joint maps/147점 재생 동일성을 확인하고 학습입력에 held group/raw/decoded SHA가 없음을 검사한다.

구조: objective fit+closure 2함수,worker load1함수(추가loader는 필요시7이내). fit→closure→detail_bag_loss→point_bag_loss=3전이, 모듈guard에서직접fit 호출. 전용 목적식은 card_condition 운영 경로에 연결하지 않는다. 정상 실물1개이면 기존목적식과 동일함을 수치 검산한다.
checks: 작은합성목적식/입력/1실물동치 검증,컴파일/AST,기존worker 재사용계약. 실행후record/status/acceptance/실제FNFP/typed분모/%p와원본SHA·4fit수렴·동결11cohort대조. 모델바깥 source 변경 없음을 확인. HTML에사진구역정답/출력·반복개발평가 표시; 열기/렌더구분.
rollback: 신규 실험 helper/worker는 미채택시 연구 전용으로 보존하며 운영소스 복구 불필요. 코드통합revert후관련검사/일반push. 실험기록은보존. 진척30/100은실제고정수용조건이없으면 유지.
