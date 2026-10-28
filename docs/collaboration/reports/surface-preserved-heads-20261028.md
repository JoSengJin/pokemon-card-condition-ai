# 원형 특징·감독 분리·작은 비선형 모델 — 2026-10-28

**개발 진척률 30/100(+0%p). 세 방향을 실제 구현·실험했고 채택 가능한 품질 개선은 없었다. 추가 진단과 앞면 중간층 실험까지 실행했다. 기존 모델·정답·평가 기준과 Claude 데이터 작업은 보존했다.**

## 같은 분모의 실제 성능

반복 사용한 개발·모델선택 자료다. 독립 시험이나 일반화 개선의 근거가 아니다. threshold0.5, 구역147개(양성94/정상53), 올바른 종류 실제점51개와 기존11필수cohort를 유지했다. 미확인은 정상으로 만들지 않았다.

| 후보 | 결함 누락 | 정상 오탐 | 실제점 누락 | 판정 |
|---|---|---|---|---|
| 기존 대조 |16/94 (17.02%)|18/53 (33.96%)|21/51 (41.18%)|비교 기준|
| 원형+국소 잔차 |12/94 (12.77%, −4.26%p)|22/53 (41.51%, +7.55%p)|23/51 (45.10%, +3.92%p)|completed, 미채택|
| 실제점/존재 head 분리 |28/94 (29.79%, +12.77%p)|9/53 (16.98%, −16.98%p)|23/51 (45.10%, +3.92%p)|completed, 미채택|
| 8-unit tanh MLP |미측정|미측정|미측정|failed, 수렴 미달|
| 앞면 표면 block8 |미측정|미측정|미측정|failed, 수렴 미달|

H1 새 누락3·새 오탐7·복구10, H2 새 누락12·새 오탐0·복구9다. H1/H2 모두 primary_acceptance_passed=false 및 acceptance_passed=false다. 한 지표 감소를 전체 성능 향상으로 표현하지 않는다. 이번 대상은 표면 결함이며 관찰 제한 모델의 누락/오탐은 새 평가하지 않았다. 속도 개선도 측정하지 않았다.

## 구현과 실제 실행

1. **H1**: 원래384차원 x를 남기고 crop 유효token 평균을 뺀 잔차를 붙였다. `[w_original,0]`이 원래 logit을 보존한다. 원래 손실·가중치·L2·4fold를 유지했지만 특징 차원과 정규화 기하가 달라지는 한계가 있다. 4fit 수렴, 최대 gradient3.02e-6. 새 backbone forward0.
2. **H2**: 정확한 실제점 head는 기존 명시적 정상과 실제점 양성만 학습하고, 구역에 결함이 있다는 head는 원래 모든bag을 학습했다. weak 양성을 정상으로 바꾸지 않았다. raw logit을 고정 0.5로 평균했으며 혼합비 탐색은 하지 않았다. 8fit 수렴, 최대 gradient3.02e-6. 새 backbone forward0.
3. **H3**: 원래384입력·손실·L2=1을 유지한8-unit tanh 모델이다. local CPU generator seed0, LBFGS100/gradient<=1e-5 그대로다. 첫 실행은 float64 확률을 float32 map에 대입하는 오류로 failed였다. 모델 조건을 바꾸지 않고 저장 확률 dtype만 수정한 별도 기록에서 2fold 후3번째fold gradient1.1173997104808181e-5로 failed다. 전체 성능을 추정하지 않았고 수렴 기준을 완화하거나 재학습하지 않았다.
4. **고정 head 진단**: 새 fit0, 기존 head projection40회. H1의 `[w_original,0]` 목적값이 원래 기록을 재생하고 네fold 모두 새 학습 목적이 더 낮았다(0.265~0.271→0.215~0.226). training 오류는 거의0인데 held 실제점 오류는 늘었다. H2 presence 경로는 구역을 맞추어도 실제점 반응이 약했다. 더 오래 학습하거나 모델만 키울 근거가 부족하며 데이터/특징/감독 문제의 인과를 확정하지 않는다. training행은fold 사이 반복되므로 독립 표본으로 합산하지 않는다.
5. **앞면 block8**: 진단에 근거해 분류기 용량 대신 표현층 한 변수만 바꾸었다. 과거 뒷면 엣지448 실험과 다른 앞면 표면224·97bag 가설이다. pinned DINO/로컬 가중치/CPU2threads에서 같은 입력으로 block8·최종층을 동시에 계산했다. 최종층 대조의 특징 오차0/기존 점수 오차0, 11cohort와 판정 동일을 확인했으나 첫fold fit이 고정 수렴 조건을 통과하지 못했다. backbone97회, 완료fold0, 후보 품질 미측정이다. 다른 층·반복횟수·L2 탐색은 하지 않았다.

## 공통 실행 기록

각 경로의 `record.json`이 실제 상태의 정본이다. 모든 실행은 canonical checkout의 `./experiment --plan <계획> -- <worker>`로 직렬 실행했고 실패 기록과 snapshot을 덮어쓰지 않았다.

| 계획 | record 폴더 | 실제 상태/품질 |
|---|---|---|
| plan-preserved.json |artifacts/experiments/20261028T101236-890223b7|completed / false|
| plan-separated.json |artifacts/experiments/20261028T101319-9e1f577e|completed / false|
| plan-nonlinear.json |artifacts/experiments/20261028T101414-6b20743e|failed / 미측정|
| plan-nonlinear-storage-fix.json |artifacts/experiments/20261028T101838-cb8057c6|failed / 미측정|
| plan-audit.json |artifacts/experiments/20261028T102607-3d234a18|completed / 진단 성공, 품질 false|
| plan-layer8.json |artifacts/experiments/20261028T103903-512b1606|failed / 미측정|

진단의 primary=true는 원래147/11cohort 재생 검산이며 전체 acceptance=false다. 실제 성능 개선이나 운영 채택이 아니다. 기존 development-cycle/latest의 다른 세션 ai_calls_forbidden 인계는 이번 결과가 아니며 provider 호출을 실행하지 않았다.

## 변경 파일·검증

검증 소스 main **2a4a7a0bfad15f4726148b62b4bb7307f055b78c**, 초기 구현 ead010c, dtype 수정6e746fb, 진단5743196. 최종 보고 문서는 후속 커밋이며 실험 source snapshot과 구분한다.

- `tools/experiments/surface-preserved-heads-20261028/`: features.py(원형/잔차1함수), nonlinear.py(MLP3), worker.py(선정·학습·기존평가4), audit.py(목적/학습·held 진단5), worker-audit.py(1), worker-layer8.py(대조 포함2), 위6개 사전계획. 원래 `card_condition` 운영 소스 변경0.
- `tests/test_surface_preserved_heads.py`, `tests/test_surface_layer8.py`: 특징 임베딩·역할 선정·MLP forward/dtype·audit 재생·두 층 API의 최소 회귀 검사. 기존 관련 검사와 합쳐 main17개OK(0.072초), 격리17개OK(0.107초). 합성 검사 통과를 모델 품질로 세지 않는다.
- task 문서와 동명 MD/HTML: 단일 변수·기존147/51/11cohort·수렴조건·역할/리스크 동결 및 실제 결과.
- 주요 변경 경로 fit_fold→fitter→closure→detail_bag_loss→point_bag_loss 최대4전이. 새 소스 함수 수 모두7이하를 AST로 확인했다. DINO 내부 라이브러리 호출은 기존 pinned 구현을 사용한다.
- postcheck: 6record.files 전체 SHA 일치, 기존 입력 SHA 일치(최초3plan의 worker 추적 소스만 명시적 dtype 수정 이력으로 달라짐; 원래 실행 mirror/snapshot 보존). H1/H2 저장map의147점수 재생 오차0·뒷면map 동일·11cohort 유지. 새 fit/추론0. 근거 `artifacts/surface-preserved-heads-20261028/postcheck.json`.
- `git diff --check` 및 허용 파일 대조 통과. 독립 시험·관찰제한 성능·실사용 속도·소비 프로젝트 통합 검사는 이번에 실행하지 않았다.

## 사진 보고서·리스크·롤백

실자료는 Git 제외 artifacts에만 둔다. H1/H2 각 실험 폴더 `index.html`에 앞면91구역 사진 위 사람 정답·모델 출력과 기존 점을 표시하고 전체147/51분모 표를 덧붙였다. 진단102607의index.html과 합친 `artifacts/surface-preserved-heads-20261028/index.html`에서 실패3건·모델선택 자료임을 함께 확인한다. block8/MLP는 실패해 완료 후보 사진 점수나 정확도 향상을 표시하지 않는다.

실자료 요약·H1·H2 HTML 열기 요청은 모두 queued였다. 실제 HTML 렌더는 미확인이다. 공개 HTML도 통합 후 열기 요청한다. 원본 사진·정답·개인 경로·가중치는 원격 문서에 넣지 않았다.

리스크: 개발 평가를 반복 사용해 선택 편향이 있고 실물 수가 적다. H1/H2는 실제 보호 기준을 위반했고 MLP/block8은 계산 완료조차 못했다. 현재 운영 품질 미달과 독립 자료 의존은 남는다. Claude의 수집·검토·live 라벨·박스·split·미채택 수집자료는 수정/학습 편입하지 않았다. 기존 정답/평가/봉인 자료와 운영 Gemini fallback 변경0, 외부 AI 호출0, 새 라벨0, 운영 채택0이다.

롤백: 실행 중인 작업이 없음을 확인하고 `./develop -- git revert --no-edit 2a4a7a0 dff0a10 5743196 2fa0125 6e746fb 812736e ead010c 709e8d4` 후 관련17검사와 일반push. 기존 운영 모델/라벨 복구는 불필요하며 실험 기록·미채택 head는 보존한다. 완료 후 원격 main 일치와 이전 Codex checkout 정리를 별도 확인한다. Claude·미통합·사용중 checkout은 보존한다.

## 다음 진행과 에튜 포인트

현재 근거는 training 목적 감소가 held 개선을 보장하지 않음을 보여준다. 예를 들어 원형+잔차는 네fold 모두 학습loss가 줄었지만 실제점 누락은21→23개다. 학습loss만 보고 용량/반복수를 늘리지 않고 원래 분모의 오탐·실제점 보호를 함께 적용했다.

다음 모델 변경은 실패 가설과 다른 구체 근거가 있어야 한다. 확보 중인 새 독립 실물의 정상/실제점 정답이 준비되면 같은 정답·고정 기준으로 검증한다. 불필요한 반복 실험이나 한도 소진만을 위한 작업은 하지 않는다. 계정5시간 사용량은 마지막 확인87% 사용/13% 남음이며 이후 변할 수 있다. 자동 reset은 승인받지 않아 사용하지 않았다.


## 원격 반영·보존 확인

검증 코드와 보고서 **aff886989161c307e024fccc4950fe9156d22ab9**를 일반 push했고, 확인 시점 main/origin main SHA가 일치했다. 후속 문서 커밋도 일반 push한다. 최신 Codex 구현 checkout(브랜치 codex/surface-preserved-heads-20261028)을 롤백용1개로 보존했다. 이전 Codex 특징/손실 checkout만 전달SHA042713a의main대응·clean·진행Git없음·비차단flock을 확인해 일반remove했다. 고유lock 증거1개를SHA로 보존했으며 브랜치/이력·Claude/미통합checkout은 유지했다. 감사: artifacts/surface-preserved-heads-20261028/worktree-cleanup/audit.json.

공개 보고서 포함4개 열기 요청은queued다. 추가 렌더 확인 시도는 브라우저file URL정책에 차단되어 실제HTML렌더미확인을 유지한다. 우회 서버/다른브라우저는 사용하지 않았다. Claude DATA_INVENTORY_20261028.md는 읽기만했으며Git추가/수정하지 않았다. 5시간사용량은19:43 이후확인90%사용/10%남음,한도도달아님. 한도를채우기위한실험은하지않는다.
