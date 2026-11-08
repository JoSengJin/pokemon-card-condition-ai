# α=0 후보 main 검토·통합 — 2026-11-09

개발 진척 **78/100(v1.13) 유지**. 전달 후보를 직접 검토하고 main에 통합한 뒤 **합성 재검증을 통과**했다. 실제 실험/worker/사진·캐시 추론/외부AI 호출0, 모델 품질·일반화 개선 미평가다. **실제 실험 승인은 아직 없으며 실행하지 않았다.**

## 고정 SHA와 수령 근거

- 전달 후보: `4996d74da79e117049a88016c209c6e41aae52cf`, branch `codex/surface-global-lme-only-20261109`.
- source base: `e52e4e7d669d553b549daef7b94e8226ed142cfa`, checkout base: `00f6372e8912d9145972caa3951c0919042e077e`.
- 통합 전 main: `0c1b9f2bf88cb3ef6544ab0fc0495957b22cc44a`.
- 통합·검증 소스: **`ba0eee9893d8fc912dac07aa90d2044f6956340a`**. `./develop -- git cherry-pick -x 4996d74da79e117049a88016c209c6e41aae52cf`로 충돌 없이 통합했고 원본SHA 주석을 확인했다. 검증 후 일반push 및 원격main의 동일SHA를 직접 확인했다. 이후 검토 문서 커밋의 최종SHA는 세션 완료 결과에 별도 기록한다.

후보 tip/branch/checkout ancestry, clean worktree, 허용8개 파일 diff, task의 status/checks/handoff만 변경한 사실을 확인했다. 후보 보고서가 선언한6개 소스와5개 ignored 산출물 SHA256을 실제 파일과 대조했다. 작업 branch/worktree/ignored 증거는 수정·정리하지 않고 보존했다. 현재 메인에서 작성한 계획·체크리스트도 덮어쓰지 않았다.

## 검토 결론

**통합을 막을 조치 필요 지적은 발견하지 못했다.** runtime의 기준 대비 실제 diff는 다음뿐이다.

1. 신규 `tools/experiments/surface-global-lme-only-20261109/objective.py`: 기존 0.5산술+0.5전체쌍LME를 `alpha=0.0`, `alpha*arithmetic+(1-alpha)*lme`로 변경하고 component도 같은계수0/1 적용. 연결된0산술tensor를 유지한다. 그 외 bag/fit/optimizer/기록 코드는 기준과 동일하다.
2. 신규 `worker.py`: 가설ID만 `surface-frozen-global-region-rank-global-lme-only-20261109`로 변경. 데이터·백본·분할·mass·fit·scorer·학습행·평가 블록은 동일하다.
3. 신규 `armijo_direction.py`, `metrics.py`: 기준 `surface-globalmix-gradient-recording-20261108`와 바이트 동일.
4. 신규 `checks.py`, `checks_components.py`: G-only 독립 oracle과0산술component에 맞게 갱신.50:50 fit 결과 동일성/산술floor 기대를 제거하고 기존 보호를 검사한다.

출력 maskedmax→sigmoid·threshold0.5·라벨·분할·mask·수렴1e-5/내부1e-7·1000반복/초기포함1250평가·평가 기준을 유지했다. 별도alpha옵션·추가변수·epsilon/clipping·새의존성은 없다. 산술항을 int0이나 키삭제로 바꾸지 않았다. 소스 review는 고정 커밋 객체를 기준으로 했으며 미커밋 구현을 가져오지 않았다.

전체 변경목록은 후보의 신규 Python6개·후보보고서·task8개와, 메인 후속 체크리스트·초안·이 보고서다. 후보 보고서와 구현 증거는 원문을 보존했다. main task status/handoff만 통합 결과를 별도로 추가한다.

## 이 메인에서 실행한 검증

기본 checkout 자체 `.venv`, Python3.12.14/torch2.14.1/numpy2.5.3, `card_condition.__file__`이 기본checkout을 가리키는지 확인했다. 다른 worktree 환경을 사용하지 않았다.

```sh
.venv/bin/python tools/experiments/surface-global-lme-only-20261109/checks.py
.venv/bin/python tools/experiments/surface-global-lme-only-20261109/checks_components.py
.venv/bin/python -m py_compile <후보 Python6개>
.venv/bin/python -m pip check
git diff --check 0c1b9f2 ba0eee9
```

모두 exit0. 합성 fixture만 사용했다.

- checks.py: **8개 PASS 묶음**.35단계 L-BFGS/history20, strict Armijo·상대곡률·alignment0.01·중복trial·1250평가·mask·hardmax·global LME와극단 underflow 유한성.
- checks_components.py: **11개 PASS 묶음**. 독립목적함수14건·성분20+total4 유한차분24건·합성fit3건·385차원산술gradient0·5성분합/해시·초기수렴·수용문턱·거절trial 제외·기존sidecar 보존·오염성분합 거절·가짜행/고정scorer AST 검사.
- 독립성분 loss/gradient의 최대 오차 각각 **8.88e-16**. 합성fit의 반복/평가11/11,11/11,6/6, 최종gradient9.96e-9/1.75e-8/6.43e-10. 실제 데이터 수렴이나 모델품질 결과가 아니다.
- 후보 source SHA256은 전달 커밋과 main의6개 파일이 모두 일치한다. 기본 출력/평가 보존은 소스와 고정파라미터 scorer로 검증했으며 새 학습 예측이 기존과 같다고 요구하지 않았다.
- 함수수 objective3/worker0/direction1/metrics4/checks3/checks_components6. worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss4전이, direction2전이. 합성 fit_case/거절·오염 mock/boundary 경로까지 직접 읽어4전이 이하를 확인했다.

현재 메인 로그/해시/환경/검증JSON/HTML: `artifacts/surface-global-lme-only-main-review-20261109/{checks.log,checks-components.log,checks.json,report.html,opening-status.txt}`. 후보 worktree의 과거 로그를 이번 재실행 결과로 대신하지 않았다. 실제 worker 전체/공통실행기/prepare/review/provider는 호출하지 않았다.

## 계획 상태와 실험 권한

메인 체크리스트 수령·정적검토·합성근거·통합 부분을 완료로 갱신하고, 공통 **초안**에 후보 tip/통합·검증 SHA/소스해시와 검토 문서 경로만 연결했다. `execution_authorized=false`, `code_changes=[]`, 실행 승인·runtime mirror·console·worker command 미확정 상태를 유지한다. 초안은 여전히 공통실행기 준비 검증을 통과할 수 없으며 실행하지 않는다.

실제 실험은 별도 사용자 승인 뒤 이 메인만 새 고유폴더·snapshot·최종계획을 고정해서1회 수행할 수 있다. 기존 gradient 실행 승인을 α0 학습 승인으로 재사용하지 않는다. 품질 게이트 FN≤67/370·FP≤112/1406·원래 기준AUC대비증가≥0.03·paired photo bootstrap하한>0은 유지한다. 최신50:50 FN51/370·FP179/1406·AUC0.930927300은 과거 비교값이며 이번 성능 측정이 아니다.

## 리스크·보존·롤백

α0은 산술gradient floor를 없애므로 극단의 쉬운쌍 기여가 underflow되어0일 수 있다. 이는 의도한 수식의 수치 특성이며 epsilon·clipping으로 바꾸지 않았다. 새 학습의 계수·예측·trace는50:50과 달라질 수 있다. 실제 학습의 수렴·시간/메모리·FN/FP/AUC·독립일반화·운영채택은 여전히 미검증이다. 기존 graph보존의 자원비용도 실제 실험으로 분리 측정하지 않았다.

rollback은 현재 메인만 후속문서/실행/소유권을 확인한 뒤 `./develop -- git revert ba0eee9893d8fc912dac07aa90d2044f6956340a` 및 일반push로 수행한다. 후속 계획/상태 문서의 바인딩도 정리하되 기록은 보존한다. 운영 모델/라벨/fallback 변경이 없어 복원할 모델 변경은 없다. 후보 worktree는 최신 통합 후보의 검증/롤백 근거로 유지하고, 기존 보류·미통합 worktree도 손대지 않았다.

HTML은 합성 재검증 결과만 표시한다. 이 chat의 이전file:브라우저 보안정책 차단을 존중해 새 열기/우회를 시도하지 않았다. **생성·정적내용/링크 대조, 실제열기·렌더미확인**이다. 후보의 과거 `open exit0`를 이 메인HTML의 열기 성공으로 사용하지 않는다. 외부 서버/터널/업로드0.

에튜 포인트: `0.0*arithmetic`은 값0과 미분graph 연결을 함께 유지한다. 이번 main 재검사에서385차원0벡터와5성분합을 확인한 이유는 loss만 바꾸고 진단계수를0.5로 남기는 불일치를 방지하기 위해서다. 합성수식 검증과 실자료 품질 검증은 별개다.
