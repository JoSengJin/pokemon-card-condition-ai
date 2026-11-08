# surface-globalmix-gradient-recording-20261108

- owner: Codex (현재 main 담당, 단독 직렬 구현)
- status: integrated
- base_sha: 6fb7a0928ca3e6653139fc842075eb3b06fcfc8b (fetch 후 origin/main 동일)
- branch: codex/surface-globalmix-gradient-recording-20261108
- goal: 기존 목적함수/gradient/출력/평가 예산을 유지하며 실제 채택된 최종 학습 상태의 5성분 gradient sidecar를 기록하고 합성 fixture로 검증한다.
- allowed_files: tools/experiments/surface-globalmix-gradient-recording-20261108/{objective.py,worker.py,armijo_direction.py,metrics.py,checks.py,checks_components.py}, 이 task, docs/collaboration/reports/surface-globalmix-gradient-recording-20261108.md
- ignored_outputs: artifacts/surface-globalmix-gradient-recording-20261108/{checks.log,checks-components.log,checks.json,report.html,opening-status.txt}
- forbidden_files: 기존 실험 소스/기록/캐시/모델/라벨/사진, 비소유 .claude/, 다른 worktree, 운영 모델/Gemini fallback, 진척 기준/배점/점수
- contract: 최신 globalmix-console 소스를 새 경로에 격리한다. 동일 순서의 총손실 backward graph를 보존해 최종 채택 상태에서 정상bag/결함bag/0.5산술/0.5전체LME/L2의 gradient를 추출한다. 추가 forward·목적함수 평가·최적화 step 없음. 거절 trial은 최종 sidecar에 기록하지 않는다. 초기수렴 및 내부목표 미달이지만 기존 수용 gradient≤1e-5인 종료도 처리한다. 기존 기록을 덮어쓰지 않는다.
- structure: objective 3→3, worker 0→0, direction 1→1, metrics 4→4, 기존 checks 3→3; 신규 checks_components 6. worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss 4전이, worker→fit→lbfgs_direction 2전이. 새 실행 helper/콜백/재귀 없음. 합성 fit_case→fit→loss_and_grad→detail_bag_loss→point_bag_loss도4전이. top-level 거절/오류 fixture는 fit→fixture→loss_and_grad→detail_bag_loss→point_bag_loss의4전이.
- checks: 기존 합성 checks, 기존 구현과 수치/전체 trace/출력/예산 동등성, 5성분 gradient 합/독립미분, bias 불변성, 실제 최종theta 해시, 초기수렴/거절trial/수용문턱/실패·예산/덮어쓰기 보호, AST/py_compile/diff-check. 합성 데이터만 사용한다.
- experiment: 재학습·재실험·실제 캐시/사진 평가·하이퍼파라미터 탐색·실제 외부AI 호출 금지. 실행 계획/실험 record는 만들거나 실행하지 않는다.
- reporting: 개발 진척78/100(v1.13) 유지. 위 ignored report.html 생성/내용 대조. 같은 chat에서 file: 브라우저 열기가 보안정책으로 차단된 상태이므로 우회/재시도하지 않고 링크와 렌더 미확인을 기록한다.
- handoff: 코드 47ed6900024775ce91b3d1378f1bed52d93feaf5, 검증 fixture 보완 dfad9a0d4657329022697a77a2da382be065aaf0. main fast-forward 통합 후 기존9/신규10 PASS 묶음, py_compile/AST/소스hash/diff-check 통과. 직접목적함수14개 정확동일, 성분유한차분20개, 합성fit3개 전체trace/계수/bias/출력/예산 동일. 실제 재학습/실험/사진추론0. 상세 변경·미검증·리스크·롤백은 reports/surface-globalmix-gradient-recording-20261108.md. HTML 생성/정적 내용 대조, 보안정책상 열기 재시도0/렌더 미확인. 검증한 main은 상시 승인에 따라 일반 push하며 최종 원격 SHA는 세션 결과에 기록한다.
