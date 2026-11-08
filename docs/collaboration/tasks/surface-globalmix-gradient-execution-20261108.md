# surface-globalmix-gradient-execution-20261108

- owner: Codex, 기본 checkout 단일 실행 담당
- status: assigned
- base_sha: 6822908be10f37cea614c8821c451dcab2afd001 (fetch 후 origin/main 동일)
- goal: 소스 변경 없이 공통 실행기 1회로 실제 학습fold의 5성분 gradient를 기록하고 최신 완료 실험과 대조·충돌 분석한다.
- allowed_files: 이 task, docs/collaboration/reports/surface-globalmix-gradient-execution-20261108.md. tracked Python 소스 변경 금지.
- ignored_outputs: artifacts/surface-globalmix-gradient-execution-20261108-44920394e6ef/{plan.json,preflight.json,worker.py,objective.py,metrics.py,armijo_direction.py,console.log,analysis.json,report.html,comparison.csv,opening-status.txt}; 공통 실행기가 새로 만드는 artifacts/experiments/<고유ID>/의 record/snapshot/모델/trace/gradient/결과만 허용.
- source: tools/experiments/surface-globalmix-gradient-recording-20261108/의 검증된4개 runtime 파일을 develop 잠금 안에서 새 artifacts 폴더로 바이트 그대로 복사했다. 공통 실행기의 snapshot 경로 계약상 mirror가 필요하며 새 구현/수정은 아니다. 새 mirror 파일은 baseline=null, 기존 자료는 보존.
- experiment: ./experiment --plan artifacts/surface-globalmix-gradient-execution-20261108-44920394e6ef/plan.json -- .venv/bin/python artifacts/surface-globalmix-gradient-execution-20261108-44920394e6ef/worker.py 를 딱1회 실행. 실패/중단/결과불명 시 수정·자동재시도·추가실험0. stdout/stderr는 새 고유console.log, PYTHONUNBUFFERED=1. CARD_CONDITION_AUTO_CHILD=1로 자동 후속 연결 차단, 실제 외부AI 호출 허용0.
- contract: 기존 손실·output maskedmax/sigmoid·threshold0.5·사람정답·분할·mass·CPU·seed·백본·1000반복/1250평가·최종gradient1e-5/내부1e-7 유지. 품질 게이트 FN≤67/370, FP≤112/1406, 기준AUC 증가≥0.03/paired photo bootstrap하한>0 유지. 기존 AUC 기준대조는 20261106T210640-0eb1bdc0이며 최신 완료 20261108T133726-586d9cdd와 결과 동등성을 별도로 확인한다.
- diagnostic_criteria: 5fold/385차원/유한 성분, 실제 최종theta hash 및 학습행/target/mask/mass 일치, 성분 loss/gradient 합오차≤1e-10. 최신 대비 점수오차≤1e-6 및 모든0.5 판정 동일. 진단완료와 모델 품질통과는 별개.
- hypothesis: 실제 최종 학습fold의 centered 파라미터 공간에서 정상bag 대 두rank합의 내적/코사인을 조사. 전fold 음수면 체계적 반대방향의 근거, 전fold 비음수면 해당충돌 주장 반증, 혼합이면 fold별 현상. L2와 data의 stationarity 상쇄만으로 L2 과다를 결론내리지 않는다. OOF 오류 집합을 학습 gradient로 대체하거나 학습 선별/가중/라벨수정에 사용하지 않는다.
- structure: 기존 코드 함수수 objective3/worker0/direction1/metrics4, 최장 worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss 4전이. 소스/호출 경로 추가 변경0.
- checks/handoff: 반환 후 실제 record 상태·handoff·판정·source SHA·모델/점수/오류ID/수렴·성분norm/코사인/합오차를 대조. 실패는 성능으로 추정하지 않는다. 분석/사진별HTML/CSV와 보존·리스크·롤백 보고. 이전 file: 브라우저 보안정책 차단을 우회하지 않고 렌더 미확인을 명시한다. 진척78/100(v1.13) 유지, 반복개발CV를 독립일반화로 보고하지 않는다.
