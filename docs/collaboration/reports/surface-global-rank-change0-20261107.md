# tolerance_change=0 단일 재실험

개발 진척78/100(v1.13) 유지. 첫 fold 수렴 실패, 후보 미채택, 추가 재시도0.

검증 소스 a4370c6. record: artifacts/experiments/20261107T092650-fd09886a/record.json, status=failed/error_kind=child_exit. 벽시계 9.65분(CPU 특징 추출/학습 포함). 완료 fold0/5. 후보 OOF/observations/result/models 없음.

## 실제 결과와 원인

n_iter161/1000, func_evals221/1250. prev_loss=0.5471336346992793, final_loss=0.5471336346992793, signed/absolute loss difference=0.0. coefficient max gradient=0.0011471033770301623(1e-5기준114.7배), bias gradient=5.680756770216899e-6. loss/두 gradient 모두 유한.

tolerance_change=0.0이 실제 기록에 확인된다. 이전 amax실험의160회/212평가보다1회/9평가 더 진행했으나 같은 loss/gradient에서 정체됐다. loss 작은 변화로 인한 조기 종료는 제거됐지만 수렴은 개선되지 않았다.

저장 t=0, direction·최종gradient=-2.3356967770953227e-8, 저장 direction×step 최대0. 설치 PyTorch LBFGS는 line search 전에 t=lr=1로 설정하므로 t0은 line search를 거친 결과다. 반복/평가 한도 미도달, gradient수렴 미충족, loss difference<0은 불가능하다. 따라서 이번 종료는 d*t 최대<=tolerance_change(0<=0)인 정확한 zero-step 종료 분기로 좁혀진다. line search가 업데이트0을 선택했고 최종 gradient가 커 외부 수렴검사에서 거절됐다.

내부 strong_wolfe는 별도 bracket 허용치1e-9에서 종료하고 bracket의 낮은 loss점을 반환할 수 있다. 다만 이번 내부 bracket/정확한 종료분기는 저장하지 않아 왜0을 반환했는지까지 확정할 수 없다. max구역 목적의 비매끄러움이나 line search 해상도 한계는 가능한 설명이며 입증된 인과가 아니다.

## 성능/사전 판정

|지표|기존 모델|후보/변화|고정 기준|
|---|---|---|---|
|누락률|67/370=18.11%|산출 불가|FN<=67|
|오탐률|201/1406=14.30%|산출 불가|FP<=112|
|AUC|0.91665065|산출 불가|差>=0.03 AND 사진bootstrap95%하한>0|

실행/수렴 기준 미통과, 성능 기준 미평가。실패를성능0이나악화로추정하지않는다. 독립 일반화 미확인. 새 재시도/탐색/외부AI0.

## 변경/검증/리스크/롤백

신규 tools/experiments/surface-global-rank-change0-20261107/objective.py: tolerance_change1e-12→0 및 prev_loss/final_loss/signed/absolute difference/max_eval 진단만 추가. worker.py는새가설ID/경로, metrics.py는기존바이트동일. task/본보고서추가. 기존수렴1e-5·tolerance_grad1e-7·최대1000/1250·amax·손실계수·mass·L2·초기값·분할·라벨·백본·임계0.5 불변. 실패실험을성능대조군으로쓰지않고원래completed reference유지.

검사: loss차이/진단직렬화/1250한도 합성검사, py_compile, diff-check 통과. 공통record 소스SHA불변·reference1776/FN67/FP201 검산. 실제1회 재실험실패. 전체회귀/후보성능비교/독립시험 미실행. 구조objective4함수/metrics4/worker1lambda, 새함수호출전이변경없음.

runner반환후 latest.json은과거20261024기록을계속가리킴, 이번handoff/next_steps/token_report생성없음. 과거기록을이번결과로대체하지않음.

HTML artifacts/surface-global-rank-change0-20261107/report.html에 실제실패진단/사전기준 및이전대조군32사진저장출력표시. 후보출력없음. 열기/렌더별도기록.

리스크: loss정체중단해제만으로zero-step문제는해결되지않았다. 내부line-search0선택원인미확인. 운영모델/라벨변경0. 롤백은신규소스/문서커밋만revert후일반push, record/snapshot/진단보존. 추가재실험없음.

HTML open exit0: 열기 요청 성공, 실제 렌더 미확인. git diff --check 통과.
