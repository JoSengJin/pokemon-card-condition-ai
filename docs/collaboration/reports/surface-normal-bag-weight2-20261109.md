# 정상 bag 계수2 단일 실험 — 2026-11-09

개발 진척 **78/100(v1.13) 유지**. 고정 후보를 공통 실행기로 **1회 completed/exit0** 실행했다. 정상 bag 계수1→2는 α0 대비 **FP167→92, FN57→105, AUC−0.001393641**이었다. 오탐 상한은 통과했으나 누락·AUC 증가량 기준 미달로 **운영 미채택**이다. 추가 수정·재시도·탐색·외부AI 호출은0이다.

## 실행·고정 계약

- 실제 기록: `artifacts/experiments/20261109T093529-05b9f35a/record.json`. status=completed, return_code=0.
- 실행 소스 SHA: `67847d7716ba1cc54613aa090cb5e0dccad5a179`. 계약 커밋b3475e8, 시작 기준a3beb55860f8d3f9e559d84b4c5f4d170d14ab4d.
- 시간: 2026-11-09T18:35:29.455513+09:00 → 2026-11-09T19:01:44.501559+09:00, wall 1575.046초(약26분15초). 자원을 통제한 속도 실험은 아니므로 이전 대비 실행속도 개선으로 해석하지 않는다.
- 확정계획: `artifacts/surface-normal-bag-weight2-20261109/plan.json`, SHA256 `fb61212fc89b2ed623ccfa0123710966b8a818f024d7276a269390af95db0a16`. 고정 입력188개 SHA와 CPU backend를 실행 전후 확인했다.
- 유일 과학 변수: `normal_bag_weight=1→2`, 목적함수 `2N+D+G+L2`. α0·전체쌍 G계수1·산술 연결0을 유지했다. mass 정규화·center·class balance·pair 가중·총 loss를 재정규화하지 않았다. 성분 기록 normal_bag도2N이다.
- 출력 maskedmax→sigmoid, threshold0.5, 라벨·mask·fold·1776행(결함370/정상1406), CPU 백본·seed20261031, 기존 mass·L2=1·초기화·optimizer·예산을 유지했다. 결과 뒤 기준을 바꾸지 않았다.
- 공통 실행기 계약에 따라 검증 runtime4개를 develop 잠금 안에서 새 ignored 경로로 바이트 동일 복사하고 code_changes baseline=null로 등록했다. worker 직접 실행·추가 fit·추가 patch/캐시 추론은 없다.
- 명령: `PYTHONUNBUFFERED=1 CARD_CONDITION_AUTO_CHILD=1 ./experiment --plan artifacts/surface-normal-bag-weight2-20261109/plan.json -- .venv/bin/python artifacts/surface-normal-bag-weight2-20261109/worker.py`. 고유 console noclobber, 자동 후속/review·Gemini/Codex 호출0.
- 동일 가설 기록은 이번 completed1개뿐이다. 공통 실행기 반환 뒤 잠금 사용 가능을 확인했다. development-cycle/latest.json은 과거 ai_calls_forbidden을 가리키며 이번 새 handoff는 없다. 과거 pointer/판정을 이번 결과로 쓰지 않았다.

## 동일 평가 자료의 결과

|대조|FN/370|누락률|FP/1406|오탐률|AUC|
|---|---:|---:|---:|---:|---:|
|원래 품질 기준|67|18.1081%|201|14.2959%|0.916650648|
|최신50:50|51|13.7838%|179|12.7312%|0.930927300|
|직전α0·정상계수1|57|15.4054%|167|11.8777%|0.931924955|
|이번α0·정상계수2|105|28.3784%|92|6.5434%|0.930531314|
|이번−직전α0|+48|+12.9730%p|−75|−5.3343%p|−0.001393641|
|이번−50:50|+54|+14.5946%p|−87|−6.1878%p|−0.000395986|

원래 기준 대비 FN+38(+10.2703%p), FP−109(−7.7525%p), AUC+0.013880666다. 원래 기준 대비 paired photo bootstrap95% **[0.007183352,0.021256975]**(2000회/seed20261107). 직전α0·50:50 대비 bootstrap을 추가 실행하지 않았으므로 그 차이의 유의성으로 위 구간을 사용하지 않는다.

|사전 AND 게이트|실측|판정|
|---|---|---|
|FN≤67/370|105/370|미달|
|FP≤112/1406|92/1406|통과|
|원래 AUC 대비증가≥0.03|+0.013880666|미달|
|원래 대비 paired bootstrap 하한>0|+0.007183352|통과|
|5fold 수렴·근거 유효|모두 내부 목표1e-7 통과|통과|

`result.json.acceptance_passed=false`, `evaluation.json.criterion_met=false`. 오탐 감소 방향은 관측됐지만 품질 통과가 아니다. 동일 반복 개발CV·부분 모델 점수 선택 재판정 자료이며 독립 일반화 개선은 미확인이다. 원라벨 보조 평가179/1597은 주평가370/1406과 섞지 않는다.

## 오류 이동·점수 이동

직전α0 대비 신규 누락48·누락 회복0·신규 오탐0·오탐 회복75다. 50:50 대비 신규 누락54·누락 회복0·신규 오탐0·오탐 회복87다. 전체 ID는 `analysis.json`의 comparisons/error_changes와 CSV에 보존한다. 이 오류ID는 사후 진단에만 사용하며 학습 선별·가중·라벨 수정에 쓰지 않았다.

저장 점수1,776개 중 **1,761개 하락·15개 상승**, 평균 변화−0.078831539. 직전α0 대비 threshold0.5 판정123개가 바뀌었다. 출력식은 유지했으며 학습 결과 점수가 동일하다는 뜻은 아니다. AUC도 달라졌으므로 순수한 bias 이동만으로 모든 변화를 설명하지 않는다.

## 실제 학습fold와 gradient

사진204장 해시와188개 고정 입력·snapshot/source 해시를 확인했다. 5fold의 실제 학습행 순서/ID/group/사진해시/target이 직전α0와 정확히 일치한다. float32 group/class mass를 float64로 정규화한 SHA와 target SHA를 재구성했고, mask SHA는 이전 검증된 실제 학습 기록과 모든fold에서 일치한다. 학습/평가 그룹·사진 겹침0. 저장 모델5개는 유한한384계수와 bias를 갖는다. 기록된 최종theta SHA와 fit진단 SHA·성분합이 일치한다.

|fold|학습/평가|반복/평가|최종gradient Linf|성분합오차 Linf|
|---|---:|---:|---:|---:|
|0|1424/352|114/119|9.90427e-08|2.4182e-15|
|1|1419/357|116/125|8.84558e-08|5.06886e-15|
|2|1414/362|129/135|8.77995e-08|4.05925e-15|
|3|1420/356|117/123|6.52457e-08|2.80678e-15|
|4|1427/349|123/132|9.97233e-08|5.89459e-15|

산술 loss/gradient/norm/bias는 정확히0이며 cosine은None이다. 모든fold에서 성분합 오차≤1e-10, 성분차원385·유한성·최종 계수 해시가 검증됐다. 평가수는 초기1+실제trial수와 일치하며 fit당1000반복/1250평가를 지켰다. 성분 기록용 추가 목적함수 평가/optimizer step0. OOF 오류 집합의 값을 실제 학습 gradient로 부르지 않았다.

같은 수식의 raw 정상 항을 비교하려고 신규 normal_bag loss·norm을2로 나눴다. 다음은 직전α0 대비 서로 다른 최종점의 국소 비교다.

|fold|raw N loss 변화|D loss 변화|G loss 변화|raw N gradient norm 전→후|
|---|---:|---:|---:|---:|
|0|-0.057537393|+0.064276450|-0.012461610|2.834736→1.982192|
|1|-0.056533668|+0.071165936|-0.002709012|2.811937→1.936797|
|2|-0.062085310|+0.078664306|-0.005310455|3.093978→2.145773|
|3|-0.059798211|+0.071029822|-0.008398253|2.951769→2.078946|
|4|-0.057218203|+0.069886234|-0.006545211|2.831732→1.990057|

**raw N loss는5/5 감소, D loss는5/5 증가**했고 G loss는5/5 감소했다. 정상 억제 목표가 낮아진 대신 결함 존재 손실이 커지는 절충이 실제 훈련fold에서 측정됐다. 가중 normal gradient norm 증가 자체를 개선 근거로 쓰지 않았다.

|fold|N↔G cosine α0→계수2|가중 bag합↔G α0→계수2|출력 bias α0→계수2|
|---|---:|---:|---:|
|0|+0.433718→+0.398128|-0.223234→-0.221159|-3.567058→-4.620519|
|1|+0.505340→+0.648864|-0.281569→-0.446784|-3.101943→-3.700496|
|2|+0.459065→+0.536312|-0.343625→-0.466860|-3.746930→-4.295388|
|3|+0.486536→+0.480605|-0.408064→-0.474726|-3.493636→-4.424949|
|4|+0.494335→+0.501928|-0.306135→-0.352955|-3.628171→-4.383665|

bag합은 기존N+D, 신규2N+D라 구성 계수도 다르다. 위 cosine을 같은 방향 벡터의 순수 개선량으로 해석하지 않는다. 전체 bag합↔G 충돌은5fold 모두 음수로 남았다. G는 normal_z−defect_z 차이를 사용해 공통 bias에 불변이고 L2는 bias를 벌하지 않는다(`objective.py`의pair_loss·l2). 실제 G bias gradient는약1e-17 이하·L2는0이며, 가중 N/D bias gradient가 약+0.156~0.171/−0.156~0.171로 상쇄됐다. 출력 bias는 모든fold에서 더 음수다.

**확인 사실:** 계수 강화 후 대부분 점수가 낮아졌고 FP가 줄면서 FN이 크게 늘었다. **원인 가설:** 정상 bag 가중 강화가 상대 순위보다 절대 판정 경계에 큰 영향을 줘 결함 점수까지 억제한 결과와 맞는다. **미확인:** 계수/bias/특징 방향별 정확한 OOF 기여 분해·개별 최고 patch의 변화·선형 특징의 분리 한계·독립 일반화. 추가 patch 추론/학습/threshold 탐색으로 이 빈칸을 채우지 않았다. threshold 변경만으로 AUC를 개선한다고 제안하지 않는다.

## 변경 파일·호출 경로·검증

- 신규 `tools/experiments/surface-normal-bag-weight2-20261109/`의 objective.py/worker.py/armijo_direction.py/metrics.py/checks.py/checks_components.py 6개, 이 결과 보고서와 task 총8개다. 기존 소스는 수정하지 않았다.
- 핵심 diff: objective는 정상 bag 기여에만 계수2 추가, worker는 가설ID만 변경, direction/metrics는α0와 바이트 동일. 기존 출력/평가 블록은 그대로다. 합성 oracle은 정상2배·다른항 동일·전체차=N을 검증하도록 변경했다.
- 함수 수 objective3/worker0/direction1/metrics4/checks3/checks_components6. 주요 프로젝트 호출 worker→fit_detail_head→loss_and_grad→detail_bag_loss→point_bag_loss 최대4전이, direction경로2전이. 테스트 wrapper/동적교체도 기존 구조로 확인했다.
- checks.py8 PASS그룹, checks_components.py11 PASS그룹: 독립 목적함수14·중심유한차분24·합성fit3, 385D0산술·성분합/계수/학습입력 해시·초기수렴·거절trial 제외·증거 덮어쓰기 거절·실패 sidecar 부재·Armijo·history20·곡률/정렬·중복trial·1250평가 예산. 독립 loss/gradient 최대오차8.882e-16.
- Python6개 compile, pip check(의존성 오류없음), AST·diff 검사 통과. 실제 성능 검증은 위 단일 공통 기록뿐이다.

근거: `artifacts/surface-normal-bag-weight2-20261109/`의 plan/preflight/console/analysis/postflight·checks.log/checks-components.log/synthetic-checks.json. 사진별 `report.html`·1776행`comparison.csv`는 저장 점수만 사용한다. 새 patch 추론은 없고 과거 patch 근거를 이번 최고 patch처럼 표시하지 않는다.

## 리스크·보존·롤백

진척은 기존 PROGRESS_CRITERIA.md/development-progress.json의78/100 v1.13을 유지한다. 합성 검사·수렴·부분 오탐 감소를 진척/독립 일반화 개선으로 바꾸지 않는다. FN105는 수용 한계보다38개 많고 원래 대비AUC 증가량도 미달이다. 이 후보를 운영 경로에 연결하지 않았다.

기존 사진·라벨·캐시·모델·초안·로그·비소유.claude/와 다른 세션 branch/worktree는 보존했다. 다른 세션 산출물은 편집·정리하지 않았다. 속도/메모리 원인·underflow 발생량·개별patch 인과는 미측정이다. 후속수정·재실험·계수/threshold 탐색·자동review는 실행하지 않았다.

롤백: 운영 모델/라벨/fallback 변경이 없으므로 복원할 운영 변경은 없다. 신규 격리 후보는 미채택 근거와 함께 보존한다. 필요시 현재 메인에서 `./develop -- git revert 67847d7716ba1cc54613aa090cb5e0dccad5a179`와 일반push로 후보 소스 통합을 되돌리되 실험 기록은 삭제하지 않는다. force/reset/과거snapshot 일괄 덮어쓰기는 하지 않는다.

HTML은204사진/1776구역의 사람 정답·최신50:50/α0/계수2 저장 점수·FN/FP/분모/%p를 표시한다. 정적 생성/경로·데이터 대조를 수행했다. 현재chat의 기존 file: 브라우저 보안정책 거절을 우회·재시도하지 않아 열기·렌더는 미확인이다. 외부서버·터널·업로드0.

에튜 포인트: 상대 순위 손실은 모든 logit에 같은 bias를 더해도 차이가 같아서 bias를 정하지 못한다. 이번에는 정상bag 가중치가 절대 경계에 영향을 줘 오탐을 줄이는 동시에 누락을 늘렸다. 그래서 FP 하나의 개선 대신 FN·FP·AUC의 사전 AND 기준을 함께 검사했다.
