# amax 순위 손실 1회 재실험 결과

개발 진척78/100(v1.13) 유지. 첫 fold 수렴 실패, 후보 미채택, 추가 재시도0.

검증 소스06d21fb. record: artifacts/experiments/20261107T071429-0922604e/record.json, status=failed, error_kind=child_exit. 벽시계 경과 105.4분(CPU 특징추출/학습 포함; CPU 순수 계산시간 아님). 완료 fold0/5. 후보 OOF/observations/result/models 없음.

## 원인과 진단

실제 fit-diagnostics-fold0.json: loss=0.5471336346992793, 계수 최대 gradient=0.0011471033770301623, bias gradient=5.680756770216899e-06. 둘 다 유한. 최종 계수 gradient는1e-5 기준의114.7배이므로 수렴 검사에서 거절됐다. bias만 기준 이내여도 전체 수렴은 통과하지 않는다.

n_iter160/1000, func_evals212/기본1250. 반복/함수평가 한도 소진이나 비유한 손실이 원인은 아니다. amax 변경으로 동점처리는 기존 scalar max와 맞췄지만 수렴 실패는 지속됐다. 따라서 동점 gradient 차이만으로 이번 최적화 문제를 해결한다는 가설은 지지되지 않는다.

저장 step scale 약7.0944e-7, 저장 direction×step 최대값2.1790e-10, 저장 direction·최종gradient=+1.10791e-8. 작은 이동/비하강 방향에 해당하는 정체 징후다. PyTorch LBFGS는 g·d>-tolerance_change, loss 변화<tolerance_change 등으로도 조기 종료한다. 이번에는 정확한 break 분기를 계측하지 않아 어느 조건인지 단정하지 않는다. d와t는 저장상태이며 조기break 시 서로 다른 iteration에 대응할 수 있어 direction×step을 실제 마지막 적용 이동량으로 확정하지 않는다. 비매끄러운 max 구역 목적의 gradient 전환/line-search 정체는 가능한 설명이며 직접 원인 입증은 아니다.

## 성능과 사전 기준

|지표|기존 모델|후보/변화|기준|
|---|---|---|---|
|누락률|67/370=18.11%|산출 불가|FN<=67|
|오탐률|201/1406=14.30%|산출 불가|FP<=112|
|AUC|0.91665065|산출 불가|差>=0.03 AND paired photo bootstrap95%lower>0|

판정: 실행·수렴 기준 미통과, 성능 기준 미평가。성능 악화/0점으로 해석하지 않는다. 반복 개발CV 목적이며 독립 일반화 미확인. 사전 기준/계수/optimizer/초기값/분할/정답 변경0, 재시도0, 외부AI0.

## 변경과 검증

신규 tools/experiments/surface-global-rank-amax-20261107/objective.py: max(dim1)→amax(dim1), 전체 loss 유한성 검사, 예외/최종상태 진단 저장만 추가. worker.py는 새 가설ID/경로와 fold 진단 문맥을 연결. metrics.py는 기존 바이트 그대로 보존. 기존 실패 worker/원답/라벨/운영모델 불변. task/본 보고서 추가.

합성 검사3개: amax 최대값 동일·동점 gradient 균등·진단 JSON 직렬화 통과. py_compile 및 diff-check 통과. 공통 record 등록 소스SHA 불변, baseline1776/FN67/FP201 검산. 실제 재실험1회. 전체 회귀/독립시험/후보 성능 비교 미실행.

구조: objective4함수(closure포함), metrics4, worker1lambda. 새 closure→save_diagnostics1전이; optimizer의 기존 _gather_flat_grad로 gradient를 읽고 추가 step은 수행하지 않음. 기존 closure→detail_bag_loss→point_bag_loss2전이 유지.

공통 실행기 반환 후 latest.json은 과거20261024 handoff를 계속 가리킴. 이번 handoff/next_steps/token_report 없음; 과거 결과를 이번 결과로 대체하지 않음.

HTML: artifacts/surface-global-rank-amax-20261107/report.html에 실패진단/사전기준/기존 사진32장 저장 출력 표시. 후보 출력은 없음. 열기/렌더 결과 별도 기록.

리스크: amax가 수렴을 보장하지 않음이 확인됨. 정확한 optimizer 종료분기/손실구성별 원인은 미확인. 운영·라벨 변경0. 롤백은 신규 소스/문서 커밋만 revert후 일반push, record/snapshot/진단 증거 보존. 추가 실험/자동재시도 없음.

HTML open exit0: 열기 요청 성공, 실제 렌더 미확인. git diff --check 통과.
