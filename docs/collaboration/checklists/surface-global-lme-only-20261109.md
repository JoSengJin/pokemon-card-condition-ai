# α=0 후보의 메인 검토·통합·실험 체크리스트

2026-11-09. **현재 상태: 사용자 승인 후 단일 실제 실험 completed/exit0. 품질 기준 미달·운영 미채택.** 전체 진척78/100(v1.13) 유지. 이 파일과 `docs/collaboration/plans/surface-global-lme-only-20261109.draft.json`은 현재 메인 세션 소유다. 후보 수령 전에는 다른 구현 세션의 소유 파일에 쓰지 않았다. 고정tip 수령 후에만 main에 cherry-pick했고, 구현 worktree/후보 보고서 원문은 보존했다. main의 task 상태만 통합 결과를 기록한다.

초안은 실행 불가 상태 그대로 보존했다. 이번 사용자 승인에 따른 별도 확정계획은 `artifacts/surface-global-lme-only-execution-20261109-61e14c8c7a46/plan.json`이다. 코드/입력 SHA·runtime mirror·고유 console을 고정해 공통 실행기로1회만 실행했다. 초안의 부가 필드는 실행기가 강제하는 보안장치가 아니며, 실제 실행 횟수는 공통 기록과 console을 대조했다.

## 0. 고정 근거와 소유권

- [x] 배정 source base `e52e4e7d669d553b549daef7b94e8226ed142cfa`, 구현 checkout base `00f6372e8912d9145972caa3951c0919042e077e`, 구현 브랜치 `codex/surface-global-lme-only-20261109`를 기존 계약과 대조했다.
- [x] 초안 작성 시 과학 소스·기존 자료를 수정하지 않고 main 전용 신규2개 파일만 준비했다. 이후 고정tip을 main에 통합했으며 구현 worktree/그 소유 파일에는 직접 쓰지 않았다.
- [x] 고정 품질 대조군은 `artifacts/experiments/20261106T210640-0eb1bdc0/result.json`, 원래 AUC0.9166506478028527이다.
- [x] 최신50:50 비교 대상은 `artifacts/experiments/20261108T145825-59681012/`: completed/exit0, FN51/370·FP179/1406·AUC0.9309272999884665, 운영미채택이다.
- [x] 위 실행의 frozen reference는1776행/결함370/정상1406, 실제 사람점ID0·추가 required cohort0이다. 따라서 point guard=false·required_cohorts=[]를 그대로 유지한다. 향후 실제 reference가 달라지면 누락보호를 끄지 말고 다시 검토한다.
- [x] 초안에 기존 입력 및 최신 결과/모델/학습 진단/성분·행 근거를 포함한138개 SHA256을 현재 owning file과 대조해 고정했다. 최종 확정 때 다시 확인하고 달라진 근거를 조용히 교체하지 않는다.

현재 메인에서 이 문서를 갱신해도 구현 세션의 checkout을 갱신·rebase하지 않는다. 이후 main이 전진했다는 이유로 구현 계약의 기준을 바꾸지 않는다. 기본 checkout에 남은 비소유 `.claude/`도 그대로 둔다.

## 1. 후보 수령 — 전달된 SHA부터 고정

- [x] 사용자가 전달한 전체 tip SHA·커밋 순서·branch·구현 source/checkout base·ready_for_review 보고를 받는다. 브랜치 이름이나 main에 남은 과거 task status만으로 완료를 추정하지 않는다.
- [x] tip이 배정 branch에 속하고 `00f6372...`의 자손인지, 전달 후 branch가 임의로 전진하지 않았는지 확인한다. 작업중 checkout을 바꾸거나 미커밋 파일을 가져오지 않고, 고정 커밋 객체의 diff를 읽는다.
- [x] `git diff --name-status 00f6372e8912d9145972caa3951c0919042e077e <TIP>`와 계약의 허용파일을 대조한다. 신규 후보6개 Python·후보 보고서·task의 status/checks/handoff 외 변경, 기술 계약/프롬프트/의존성/평가 기준/비밀파일 변경은 수령 완료로 처리하지 않는다.
- [x] task 본문 기준을 바꾸지 않았는지 실제 diff를 확인한다. ignored 합성 로그/HTML은 커밋에 자동 전달되지 않으므로 보고된 경로와 SHA를 읽기 전용으로 확인한다. 없으면 미확인으로 남기며 재현 결과를 꾸미지 않는다.

## 2. 수식과 코드 검토 — α 하나인지 확인

- [x] 변경은 `B+alpha*M+(1-alpha)*G`, alpha=0.0 고정 하나다. 총 rank계수1, G는 전체쌍 flatten LME다. row-LME 평균·온도·margin·L2·mass·학습쌍 선별·초기화·출력 변수가 섞이지 않았는지 본다.
- [x] 같은 theta/입력에서 bag/L2는 기준과 같고, 최적화 total과 기록된 component 계수가 모두0/1인지 확인한다. `arithmetic_rank`는 연결된 tensor의 loss/gradient/norm0, `global_pair_lme`는전체G다. Python int0/키삭제/계수0.5 잔존/숨은epsilon 산술항을 거절한다.
- [x] 기존 산술혼합의 gradient floor0.5/N을 제거하는 의도와 합성 테스트가 맞는지 본다. 새로운 floor/clipping을 넣지 않았고, zero-vector cosine은None/unavailable인지 확인한다.
- [x] 정상tau0.1 비정규화LSE·결함max·mask·head·seed·CPU float64 fit·정규화mass·L2=1·scorer maskedmax→sigmoid·threshold0.5가 유지되는지 실제 코드와 호출자를 확인한다.
- [x] worker 가설ID는 초안의 `surface-frozen-global-region-rank-global-lme-only-20261109`와 같다. 그 외 worker의 데이터/fit/score/학습행 기록/평가 블록은 기준과 같고 metrics/direction은 바이트 동일한지 확인한다.
- [x] 최종 수용 상태의 graph만 성분 추출에 사용하고, 거절trial을 기록하지 않으며 추가 forward/목적함수 평가/optimizer step이 없는지 확인한다. 공개fit 반환 API와 기존 실패 기록 경로를 유지한다.
- [x] 전 파일 함수≤7, 주요 경로 worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss≤4전이, direction경로2전이를 확인한다. 테스트용 wrapper·동적 교체 경로도 실제로 세며 미확정 경로를 통과로 처리하지 않는다.

## 3. 합성 검사 근거

- [x] 독립적인 전체G 수식/autograd/유한차분·row-LME와 구분되는 fixture·단일/동일/순열/반복쌍·유한성 검사를 확인한다. 실제 사진/라벨/캐시를 fixture로 쓰지 않았는지 확인한다.
- [x] 새 loss를 이전50:50과 동일하다고 주장하지 않는다. 같은 입력/파라미터에서의 bag/L2와 출력식/API 보존, 새 total과5성분합, 0산술항, 최종theta SHA를 검증했는지 본다.
- [x] 초기수렴·내부목표 미달이지만 기존 수용문턱 통과·거절trial 제외·sidecar 덮어쓰기 방지·실패 때 성공sidecar 부재를 확인한다. 수렴1e-5/내부1e-7,1000반복/초기포함1250평가·Armijo/중복trial/곡률/정렬 보호 fixture를 확인한다.
- [x] 실제 실행 명령·exit code·테스트 source SHA·로그/HTML·미검증을 확인한다. 준비·형식 검사·합성 성공을 실제 성능 개선으로 쓰지 않는다.

## 4. 통합 — 이 메인에서 완료, 실제 실험과 별개

- [x] 실행/검토가 없는 기본 checkout에서 origin/main fetch, tracked 미커밋 변경·진행중Git작업·실행 잠금·타작업 소유권을 재확인한다. 비소유 파일을 stash/reset/add하지 않는다.
- [x] 검토한 후보 커밋만 계약 순서대로 `./develop -- git cherry-pick -x <SHA>`로 통합한다. main의 이번 준비2개 문서와 다른 변경을 덮어쓰지 않는다. 충돌은 잠금 안에서 근거를 읽고 해결 또는 abort하며 ours/theirs 전체선택·force·history rewrite를 하지 않는다.
- [x] 기본 checkout 자체 `.venv`의 import 위치를 확인하고 새 경로의 checks.py/checks_components.py, py_compile·AST·diff-check를 다시 실행한다. 별도 worktree의 PASS만으로 통합 성공을 선언하지 않는다. actual worker/experiment/review를 테스트로 실행하지 않는다.
- [x] 통합 후 실제 소스 SHA·후보 tip·cherry-pick SHA·검사 결과를 고정하고 일반 push 및 원격 main SHA 일치를 확인한다. 코드 통합은 모델 채택이나 실제 실험 실행 승인이 아니다.

## 5. 공통 실행 계획 확정 — 후보 수령·통합·승인 이후

- [x] 초안 파일을 그대로 실행하지 않는다. 고정 후보 tip/통합커밋/검사한main SHA를 revision_bindings/source_sha에 채운 **별도 새 실행계획**을 만든다. 현재 draft 파일을 실측 결과로 덮어쓰지 않는다.
- [x] 모델·worker/의존 소스가 검사한 커밋과 같은지 SHA로 묶는다. main에서 고유한 새 ignored 실행폴더를 만들고 검토된 runtime4개를 바이트 동일 mirror로 복사한다. 현재 공통 실행기 code_changes는 tools 경로를 직접 받지 않아 artifacts mirror가 필요하다.
- [x] code_changes에 실제 mirror 경로와 baseline을 등록한다. 새 후보 파일은 baseline=null, 기존 파일 수정이면 실제 수정 전 Python snapshot만 baseline으로 쓴다. 읽기 좋은 비교를 만들려고 새 파일을 수정 파일로 위장하거나 과거 snapshot을 덮어쓰지 않는다. 후보와50:50의 cross-source diff는 별도 검토 근거로 보존한다.
- [x] 초안의138개 고정 입력을 다시 확인하고 실제 후보 runtime/의존 소스 SHA를 추가한다. 고유console 경로·명령·계획경로·source/통합 SHA·승인 근거의null을 모두 해소하고 mirror/실제 import 경로가 일치하는지 정적으로 확인한다. API키/전체env를 기록하지 않는다.
- [x] 실제 실행 전 CPU backend가 직전과 같은지 확인한다. MPS가 선택될 상태라면 조용히 backend/env/worker를 바꿔 실행하지 않는다. 기준 변경 여부를 먼저 검토한다.
- [x] AUC 품질 기준의 reference_result는 원래 `20261106T210640-0eb1bdc0`, 최신 변화량 비교는 `20261108T145825-59681012`로 유지한다. FN67/370·FP112/1406·AUC증가0.03·paired bootstrap하한>0,seed/draws·실제점/추가cohort 보호를 재확인한다.
- [x] α0 후보는 예측·계수·trace가 바뀔 수 있으므로 최신 대비 점수오차0/모델동일 조건을 넣지 않는다. 대신 ID/정답/분모/fold/mask/학습mass 계약과 자기 최종theta/component 합을 검증한다.
- [x] 실제 실행에 대한 별도 사용자 승인을 확인한다. 현재의 준비 요청이나 이전 gradient 기록 실행 승인을 α0 학습 승인으로 재사용하지 않는다. 승인 전 execution_authorized는false 유지다.

## 6. 단일 실행 — 승인 후 이 세션에서 완료

- [x] 동일 가설의 running/completed/failed/interrupted 기록과 이전 호출 여부를 확인한다. 상태 불명·실패·중단이면 새 명령으로 자동 재시도하지 않는다. `max_executions=1`은 metadata라 자동 방지장치라고 주장하지 않는다.
- [x] 공통 실행기 `./experiment --plan <확정된새계획> -- .venv/bin/python <검토된mirror-worker>`만 사용한다. 직접worker·추가fit·사진추론·backbone/cache replay·threshold/비율 탐색은 실행하지 않는다.
- [x] PYTHONUNBUFFERED=1, CARD_CONDITION_AUTO_CHILD=1, 계획 Gemini/Codex 호출허용0을 명시한다. 부모/자식 stdout/stderr는 새 고유console에 exclusive/noclobber로 보존한다. 자동review/후속실험0이다. 실제 실행 중 별도 개발 명령을 병렬로 실행하지 않는다.
- [x] 공통 실행기가 반환할 때까지 관찰하고, 실행 중/failure/interrupt를 성능 결과로 대신하지 않는다. 실패하면 보존·보고하고 그 자리에서 수정·재시도·새 계획 실행을 하지 않는다.

## 7. 반환 후 대조와 판정

- [x] 실제 record.json의 completed/exit0와 frozen source/reference/hash를 확인한다. development-cycle/latest와 해당handoff/next_steps/token_report가 있으면 읽되, 차단 플래그로 새handoff가 없을 수 있다. 과거 pointer를 이번 실행의 판정으로 쓰지 않는다.
- [x] 자기 학습행 순서/그룹·사진 분리·target/mask/normalized mass·최종theta SHA·5fold/385차원/유한값·성분합≤1e-10·추가평가0을 확인한다. 산술항0과 zero-cosine=None을 확인한다.
- [x] 최신50:50 대비 FN/FP·누락률/오탐률 %p·AUC차·오류ID 변화를 같은1776행/370·1406분모로 계산한다. common result의 new_misses/new_false_positives는 **원래reference 대비**이므로 최신 대비 오류 목록으로 잘못 부르지 않는다.
- [x] worker의 원라벨 보조평가179/1597과 확정라벨 주평가370/1406을 섞지 않는다. raw G의 기여를 비교할 때는 기존component계수0.5/신규1의 차이를 명시한다. 새로운0산술gradient에서 cosine을 만들지 않는다.
- [x] 공통 result의 FN/FP acceptance와 worker evaluation의 AUC증가/bootstrap 판정을 모두 확인한다. 공통 실행기의 기본 acceptance에는 AUC 조건이 없으므로 그것만으로 통과를 선언하지 않는다. **FN≤67/370 AND FP≤112/1406 AND 원래AUC대비증가≥0.03 AND paired photo bootstrap하한>0 AND 수렴·근거유효성**을 모두 충족해야 품질통과다.
- [x] FP≥179면 의도한 오탐 감소를 지지하지 않는다. FP가줄어도 고정게이트 하나라도 미달이면 미채택이다. gradient 정렬/형식검사/합의/실행완료를 품질 개선으로 대체하지 않는다. 품질통과도 자동 운영 채택은 아니다.
- [x] 최종점의 local centered gradient와 실제 OOF오류 개선을 구분한다. 반복개발CV·부분 점수선택 재판정·훈련fold 중복은 독립일반화 근거가 아니다. OOF오류ID를 학습선별·가중·라벨변경에 쓰지 않는다.

## 8. 보고·보존·롤백

- [x] 결과는 새 메인 전용 `docs/collaboration/reports/surface-global-lme-only-evaluation-20261109.md`와 새 실행폴더의 analysis/HTML/CSV로 보고한다. 다른 세션의 후보 보고서를 병행 편집하지 않는다.
- [x] 사진 위 구역별 기존 사람정답·최신/α0 점수·FN/FP·분모·%p, 원래 품질대조와 최신 비교의 구분, record 상태·SHA·성분진단·변경파일·검사·미검증·리스크·롤백을 표시한다. 새 patch추론이 없으면 오래된 patch근거를 새 결과로 표시하지 않는다.
- [x] HTML은 로컬 정적경로로 생성·대조한다. 현재 chat의 file: 브라우저 보안정책 차단을 우회·재시도하지 않고 열기/렌더 미확인과 링크를 기록한다. 외부 서버/터널/업로드는 시작하지 않는다. 준비 당시에는 실행성과를 만들지 않았으며, 이번 실행 완료 후 새 성능 HTML을 별도 생성했다.
- [x] 운영모델/라벨/fallback 변경이 없으면 복원할 모델 변경은 없다. 코드 rollback이 필요하면 현재 실행·후속소유권·통합SHA를 확인한 뒤 현재 메인만 `./develop -- git revert <후보통합SHA>`와 일반push를 수행한다. reset/force·증거삭제·과거snapshot으로일괄덮어쓰기를 하지 않는다.
- [x] record·모델·gradient·console·실패 근거와 작성중/미통합 worktree는 보존한다. 합성검사나 후보 코드 통합만으로 진척 점수를 올리지 않는다.

## 완료 결과와 보존

검토·통합·합성 검증의 기존 근거는 `docs/collaboration/reports/surface-global-lme-only-main-review-20261109.md`와 `artifacts/surface-global-lme-only-main-review-20261109/`에 보존했다. 사용자 승인 후 최종 계획의 입력147개를 검증하고 공통 실행기로1회 실행했다. 실제 기록은 `artifacts/experiments/20261108T215307-941b3aaa/record.json`: completed / return_code0. 추가 소스 수정·재시도·탐색·자동 후속·외부AI 호출0.

FN57/370·FP167/1406·AUC0.931924954826804. 최신 대비 FP12감소·FN6증가·AUC+0.000997655. FP≤112와 원래 AUC대비증가≥0.03 미달로 운영 미채택. 5fold 내부gradient목표1e-7·학습행/mask/mass·성분합/최종theta SHA 검증 통과. 성분별 비교·전체 오류 이동은 `docs/collaboration/reports/surface-global-lme-only-evaluation-20261109.md`와 실행폴더의 analysis/HTML/CSV를 참조한다. HTML 열기·렌더는 기존 정책 차단으로 미확인이다.

초안은 고정입력이므로 수정하지 않았다. 다른 세션 worktree/소유 산출물과 기존 모델·라벨·기록·비소유.claude/를 보존했다. 운영 변경은 없으므로 복원할 운영 모델이 없다. 필요시 새 결과 문서 커밋만 일반 revert하고 실험 증거는 보존한다. 전체 진척78/100(v1.13) 유지.
