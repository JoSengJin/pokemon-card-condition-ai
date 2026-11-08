# 최종 목적함수 성분별 gradient 기록 구현 — 2026-11-08

개발 진척 **78/100(v1.13) 유지**. 최종 채택된 학습 상태의 정상bag·결함bag·0.5산술순위·0.5전체쌍LME·L2 gradient 기록을 새 격리 소스에 구현했다. **합성 검증만 수행**했으며 재학습·공통 성능 실험·실자료/캐시 추론·외부 AI 호출은 0이다. 실제 학습 성분별 gradient 결과나 모델 정확도 개선을 얻었다고 보고하지 않는다.

구현 커밋: `47ed6900024775ce91b3d1378f1bed52d93feaf5`. 최종 검증 기준 소스 커밋: `dfad9a0d4657329022697a77a2da382be065aaf0` (테스트 호출 깊이 보완). 기준 main: `6fb7a0928ca3e6653139fc842075eb3b06fcfc8b`. 계약: [task](../tasks/surface-globalmix-gradient-recording-20261108.md). 작업 전 fetch에서 origin/main과 기준 SHA가 같았으며, 실행 잠금을 읽기 전용 비차단 flock으로 확인했다. 소스 쓰기는 모두 `./develop -- ...` 안에서 수행했다. 비소유 `.claude/`와 기존 worktree는 건드리지 않았다. main fast-forward 통합 후 두 합성 검사와 소스hash/컴파일 검사를 다시 통과했다.

## 변경 파일과 핵심 diff

신규 폴더 `tools/experiments/surface-globalmix-gradient-recording-20261108/`:

| 파일 | 기준 globalmix-console 복사본과 차이 |
|---|---|
| `objective.py` | bag항의 원래 합산 순서를 유지하면서 진단용 성분을 보존. 기존 total backward의 graph를 유지해 최종 상태에서만 5개 성분을 미분. 초기평가/trial/채택 경로의 반환값 수신을 함께 갱신. 최종 sidecar 추가. |
| `worker.py` | 새 격리 가설ID와 학습행 순서/ID/group/사진해시/target sidecar 추가. fit·분할·mass·scorer·평가 블록은 그대로. 실제 worker는 이번에 실행하지 않음. |
| `armijo_direction.py` | 기존과 바이트 동일. 방향/수렴 보호 변경 없음. |
| `metrics.py` | 기존과 바이트 동일. AUC/분모/threshold/paired bootstrap 변경 없음. |
| `checks.py` | 기존 합성 회귀를 새 경로에서 실행하도록 연결. 반환 tuple 4개를 반영하고 실패 시 성공 성분 sidecar가 없는지 검사. |
| `checks_components.py` | 독립 성분 미분/유한차분, 기존 구현과 bit 동일성, 최종 상태·거절trial·초기수렴·수용문턱·기록 보존 검증. |

문서 변경: 이 보고서와 위 task. 기존 실험 소스·snapshot·record·모델·사진·라벨·평가 입력·진척 파일 변경은 0이다. 새 격리 소스는 별도 실행 계획이 있어야 사용되며, 기존 완료 실험이나 운영 모델에 자동 적용되지 않는다. 이번에는 실제 실행 계획을 만들지 않았다.

## 기록 계약과 보존 조건

`objective.py:29`의 총손실은 기존과 같은 순서로 `sum(bags)+L2+0.5*arithmetic+0.5*LME`를 계산한다. `backward(retain_graph=True)`로 계산한 기존 total gradient를 최적화에 그대로 사용한다. 진단용 그룹화 합계를 최적화용 loss로 대체하지 않는다.

`fit_detail_head`는 최초 상태 또는 **실제 채택된** Armijo 상태의 graph만 최종 audit로 유지한다. `objective.py:138` 이후에서 5성분의 gradient를 추출하며 **추가 forward/목적함수 평가/optimizer step은 없다**. 거절 trial은 최종 기록으로 승격하지 않는다. 내부목표 `1e-7` 도달뿐 아니라 기존 수용문턱 `1e-5` 이하의 다른 종료도 기록한다. 미수렴이면 기존 실패 진단/snapshot 경로로 종료하고 성공 성분 sidecar를 쓰지 않는다.

`component-gradients-foldN.json`은 fold·최종 반올림 전 theta의 SHA·종료 이유·평가 횟수·정규화된 mass/target/mask 해시·학습 bag 수·5성분 loss/전체 gradient 벡터/L2·Linf norm/bias gradient·total gradient·성분합 오차를 담는다. 실제 head라면 벡터 길이는385이며 합성 fixture에서는 특징 차원에 맞는다. cosine은 저장벡터로 나중에 계산할 수 있다. 최종 theta 일치와 성분합 오차≤`1e-10`을 확인한 뒤 exclusive create(`open('x')`)로 저장한다.

`component-gradient-rows-foldN.json`은 worker에서 실제 fit에 넘기는 학습행 순서를 기록한다. OOF 오류 집합을 입력으로 받거나 학습 선별/가중에 사용하지 않는다. 이 파일도 exclusive create라 동일 출력 폴더의 기존 행 근거를 덮어쓰지 않는다. 행 metadata는 fit 직전에 저장되므로, 이 파일만 있고 성공 component 파일이 없으면 학습 성공으로 해석할 수 없다.

출력 masked max→sigmoid·threshold0.5·라벨·그룹분할·1776 평가 분모·정상 tau0.1·50:50 순위 혼합·L2=1·mass·seed·초기화·백본을 유지한다. `gradient≤1e-5`/내부목표 `1e-7`, fit당 1000반복/초기평가 포함1250평가도 그대로다. FN≤67/370, FP≤112/1406, 기준 AUC 증가≥0.03, paired photo bootstrap 하한>0의 품질 기준은 worker의 기존 평가 블록과 바이트 동일하다.

## 호출 경로와 함수 수

- `worker → fit_detail_head → loss_and_grad → detail_bag_loss → point_bag_loss`: 4전이.
- `worker → fit_detail_head → lbfgs_direction`: 2전이.
- 성분 추출은 `fit_detail_head` 안에서 PyTorch `autograd.grad`를 직접 호출한다. 새 프로젝트 helper·중첩 callback·재귀를 추가하지 않았다.
- 기준 복사본 대비 함수 수: objective 3→3, worker 0→0, direction 1→1, metrics 4→4, checks 3→3. 신규 checks_components는 6. AST로 일반/비동기/람다를 합산해 모든 파일≤7 확인. 합성 fit_case→fit→loss_and_grad→detail_bag_loss→point_bag_loss는4전이이며, top-level 거절/오류 fixture도 fit→fixture→loss_and_grad→detail_bag_loss→point_bag_loss의4전이다. 불필요한 호출계수 wrapper를 제거하고 기존 trace·목적함수 호출위치2개 검사를 사용했다.
- 새 fit 경로의 동적 교체 대상은 worker의 `prior.sw.fit_detail_head=objective.fit_detail_head`로 고정되며, 출력 scorer는 기존 `prior.sw.score`다. 기존 import 초기화 체계 자체는 수정하지 않았다.

## 실행한 합성 검증

명령:

```sh
.venv/bin/python tools/experiments/surface-globalmix-gradient-recording-20261108/checks.py
.venv/bin/python tools/experiments/surface-globalmix-gradient-recording-20261108/checks_components.py
.venv/bin/python -m py_compile <위 신규 Python 파일 6개>
git diff --cached --check
```

최종 결과 모두 exit0. 로그는 `artifacts/surface-globalmix-gradient-recording-20261108/{checks.log,checks-components.log,checks.json}`에 보존했다. `checks.json`에 검사 소스 SHA256을 기록했다.

- 기존 회귀 9개 PASS 묶음: 35단계 L-BFGS 방향/history20 대조, 수렴·strict Armijo·중복 파라미터 차단·1250평가 예산, 상대곡률·정렬 재시작, 정상 smooth upper bound/mask, 결함 hardmax, 모든 학습쌍과50:50 전체쌍LME 계약.
- 신규 10개 PASS 묶음: 직접 목적함수14개(7개 합성 seed×2종 정상 reduction)에서 기존 loss/total gradient/active patch **정확히 동일**. 독립 재구성한 5성분 loss/gradient 최대 차이0. rank/L2 bias gradient0 확인.
- 성분별 중심 유한차분20개에서 오차<`1e-8` 확인.
- 합성 fit3개에서 계수·bias·masked-max 점수·전체 Armijo trace·기존 진단 dict가 **bit 동일**. 0 mass 제외, point/presence 역할도 포함. 평가/반복은11/11,11/11,6/6이며 gradient는9.96e-9,1.73e-8,6.43e-10. 기록을 위한 추가 목적함수 호출0.
- 초기평가에서 수렴하는 사례, 거절된 가짜 zero-gradient trial의 해시 제외, 내부목표 미도달이지만 수용문턱 통과하는 종료, 기존 sidecar 거절/보존, 잘못된 성분합 거절을 검증.
- worker 전체를 실행하지 않고 신규 행 sidecar 작성 AST 블록만 가짜 ID/group/해시/target으로 실행해 순서/fold/정답 및 덮어쓰기 방지를 검증.
- metrics/direction의 바이트 동일성, worker 평가 블록 동일성, AST 함수수, py_compile, diff-check 확인.

테스트 작성 중 인용문과 테스트 tensor dtype 오류를 고친 뒤 최종 전체 검사를 통과했다. 실제 학습/사진/캐시를 테스트 fixture로 사용하지 않았다. 이것은 모델 성능 개선·실자료 메모리/시간·독립 일반화 검증이 아니다.

## 리스크·미검증·롤백

graph 유지로 현재 채택 상태와 trial graph가 함께 살아 있어 메모리가 늘고, 최종5회 성분 backward의 시간이 추가된다. graph는 함수 밖에 저장하지 않으며 detach한 숫자만 JSON에 쓴다. 목적함수 평가 횟수 불변은 시간/메모리 불변을 뜻하지 않는다. 실자료1776개에서의 메모리/시간과 실제 gradient 충돌은 이번 범위에서 측정하지 않았다.

내부 `loss_and_grad` tuple이3→4개로 바뀌어 격리 objective의 초기/trial 호출자와 합성 fixture를 함께 갱신했다. 공개 fit의 반환3개는 유지한다. 실제 수치 동일성은 합성 fixture에서 확인했으며 실자료 결과를 추정하지 않는다. component 합 검증/파일 I/O에 실패하면 오류로 종료하므로 그런 기록을 성공한 모델 근거로 사용하면 안 된다.

롤백: 테스트 후속 `dfad9a0d4657329022697a77a2da382be065aaf0`와 코드 `47ed6900024775ce91b3d1378f1bed52d93feaf5`를 최신순으로 `./develop -- git revert <테스트SHA> <코드SHA>` 하여 일반 push한다. 기존 실험/운영 경로가 바뀌지 않아 기존 모델·라벨을 복원할 필요는 없다. 문서만 되돌릴 때는 해당 문서 커밋을 별도로 revert한다. 과거·신규 진단 근거는 보존한다.

HTML: `artifacts/surface-globalmix-gradient-recording-20261108/report.html`. 외부 CDN/업로드/서버 없이 합성 결과와 진척/리스크를 표시한다. 같은 chat의 이전 열기에서 브라우저가 file: URL을 보안정책으로 차단했고 우회를 금지했으므로 재시도하지 않았다. **열기·렌더 미확인**이며 로컬 링크만 제공한다. 원인과 경로는 `opening-status.txt`에 기록한다.

에튜 포인트: `retain_graph=True`는 같은 forward 계산을 다시 미분할 수 있게 중간값을 남긴다. 이번에는 동일한 최종 파라미터에서 total과5성분을 비교하기 위해 사용했다. 예를 들어 total gradient가0이어도 성분이+3/-3이면 합계 수렴과 큰 상쇄를 구분할 수 있다. 이 편의에는 메모리 비용이 있다.
