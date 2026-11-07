# 후면 표면 전역 순위 손실 1회 실험

개발 진척78/100(v1.13) 유지. 승인된 단일 실험은 첫 fold 수렴 검사 실패로 종료, 후보 미채택.

검증 소스 커밋 de96226. record: artifacts/experiments/20261107T064427-9d2a480e/record.json, status=failed, error_kind=child_exit. 첫 fold fit_detail_head에서 Detail head did not converge 발생. gradient가 유한하고<=1e-5여야 한다는 기존 기준을 통과하지 못함. 실제 gradient 값은 기록되지 않아 수치 미확인. 완료 fold0/5, observations/result/models 없음. 24.8분 실행(CPU 특징추출 포함); 재시도0, 외부AI0.

|지표|기존 동결 대조군|후보|변화|사전 기준|
|---|---:|---|---|---|
|누락률|67/370=18.11%|산출 불가|산출 불가|FN<=67|
|오탐률|201/1406=14.30%|산출 불가|산출 불가|FP<=112|
|AUC|0.91665065|산출 불가|산출 불가|差>=0.03、paired photo bootstrap95%lower>0|

판정: 실행/수렴 기준 미통과. 성능 기준은 미평가이며 성능 악화/0점으로 해석하지 않는다. 독립 일반화 개선 미확인.

변경 파일: tools/experiments/surface-global-rank-run-20261107/worker.py, objective.py, metrics.py 및 task/이 보고서. 새 실험용 복사본만 추가. 기존 학습 손실에 계수1×mean softplus(z_normal-z_defect) 추가, train fold의 모든 결함×정상 구역쌍 사용. 백본·라벨·mask·head·초기값·mass·L2·LBFGS1000·seed·5fold·threshold0.5 고정. 기존 저장 revised 점수와 비교하도록 구성. 원라벨 평가도 별도 분모로 유지하도록 구현했으나 실행 실패로 미산출.

검증: 순위항 벡터/이중루프 동일, 결함/정상 gradient 방향, 동률 대비 정순위 손실 감소 합성3검사 통과. py_compile 통과. reference FN67/FP201 및1776행 확인, 등록 소스SHA 불변 확인. 실제 학습1회 수행, 첫 fold 수렴 실패. 전체 회귀/독립시험/새 후보 성능 비교 미실행.

구조: objective3함수(closure포함), metrics4함수, worker1익명callback. 새 손실은 tensor 연산으로 직접 계산. 수정 fit closure→detail_bag_loss→point_bag_loss2전이. 과거 feature extraction 경로는 변경하지 않음.

공통 실행기 반환 후 latest.json 확인: 이전 20261024 기록을 계속 가리킴. 이번 실험의 handoff/next_steps/token_report 새 생성 없음. 이전 결과를 이번 결과로 대체하지 않음.

HTML: artifacts/surface-global-rank-run-20261107/report.html. 실패상태와 사전기준을 표시하고 과거32사진/구역별 사람 정답·기존모델 점수는 저장 진단임을 명시. 후보 출력 없음. 열기 요청/렌더 결과는 별도 기록.

리스크: 비매끄러운 max 기반 목적에서 수렴하지 못했다. 정확한 원인/gradient 수치는 미확인. 이번 실패는 순위학습 일반의 불가능을 입증하지 않는다. 반복 개발CV이며 독립검증 아님.

롤백: 운영 모델·라벨 변경0으로 복구 불필요. 신규 소스/문서 커밋 revert 후 일반push 가능, 실패record와snapshot 보존. 자동재시도/기준완화/후속실험 없음.

HTML open: sandbox 기본앱 열기 실패(-10661), 권한상승 open 성공(exit0); 실제 렌더 미확인. git diff --check 통과.
