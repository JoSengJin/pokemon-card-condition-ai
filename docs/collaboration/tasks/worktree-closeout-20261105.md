# 승인된 레거시 작업 종료·보관

task_id: worktree-closeout-20261105
owner: Codex
status: integrated (종료 승인 이행·감사 기록 완료; 레거시 코드 통합을 뜻하지 않음)
base_sha: 6ac9552e71a7aa0e13c0b84ffda501e639b59a47
branch: main (문서 기록 및 공유 Git worktree 관리)
approval: 사용자 "4개 항목 권장대로 진행해"(2026-11-05). 직전 권장: 1028-6 보관·종료, 과거 보고서는 branch에만 보존, 레거시10개 종료·이력 보존 후 작업 폴더 제거, 완료 Codex 세션 archive. 이전 턴의 삭제 금지는 이 명시 승인 대상에 한해서만 대체한다.
goal: 종료 승인된 11개 작업을 closed_by_user로 기록하고 안전 검사 후 일반 worktree remove한다. 연결된 완료 앱 세션 1개는 고유 ignored 자료 보존 후 공식 도구로 archive한다. 브랜치·커밋·보고서 이력은 유지한다.

대상: claude/task-1026-2; claude/task-1027-1,3,4; claude/task-1028-1,2,3,4,5,6,7. 앱 대상은 codex/review-manifest-dedupe-20261025의 소유 세션01a15109-e475-7c20-b6cb-2f3984059215다. 이 11개가 main 통합됐다는 뜻이 아니며 원래 계약의 과거 상태는 수정하지 않는다.

allowed_files: 이 계약, docs/collaboration/reports/worktree-closeout-20261105.md, ignored artifacts/worktree-closeout-20261105/ 아래 감사·Git bundle·ignored 증거·SHA-256·HTML. 승인된 worktree 등록/폴더 제거와 앱 세션 archived 변경.
forbidden: 개발 중인 두 pair-control worktree 읽기/수정/정리와 서버 조작, 다른 worktree 정리, 브랜치 삭제, force/remove --force/prune/이력 재작성, 모델·worker·제품 소스·라벨·사진·평가·진척 기준 변경, 실험·학습·외부 AI 호출. 앱 내부 DB/state 직접 수정 금지. A3 및 레거시 과거 보고서를 main에 새로 복사하지 않는다.

checks: 제거 전 고정 HEAD/porcelain/진행 Git 작업/process cwd/기존 workspace.lock 비차단 flock. dirty/사용 중/민감 자료 정본 미확인은 해당 경로만 보류. ignored 전체 조사, 고유 증거 복사·SHA 대조, 대상 branch 12개 Git bundle 생성·verify/list-heads. 일반 git worktree remove만 실행하고 flock은 반환까지 유지. 앱 archive는 소유 세션 notLoaded/완료 및 clean/ignored 재확인 후 codex-app-tools의 set_thread_archived를 사용하고 결과·DB 읽기 전용으로 확인. 다른 세션 생성/메시지/모델 요청 없음.
HTML: artifacts/worktree-closeout-20261105/index.html 생성·내용 대조·사용자 열기. queued/open 성공과 실제 렌더 확인을 구분한다.
experiment: 없음. 개발 진척 usable-card-analysis-v1.13 78/100, 점수 변경 없음.
handoff: 실제 removed/retained/blocked, 전체 SHA, 보존 해시·복원 방법·앱 archive 결과를 보고서와 감사 JSON에 기록한다. 문서는 검증 후 일반 push 및 원격 SHA 확인.

result: 레거시11개 모두 일반 remove 완료, branch12개 ref 불변·self-contained bundle 검증, 고유 ignored 잠금 기록7개 해시 보존. 과거 보고서6파일은 branch에만 보존. 앱 세션 archived=true와 DB archived=1 확인; 관리 checkout은 남아 있고 수동 제거하지 않음. 보호 worktree·서버 접근0, 모델·제품 코드 수정0. 기준 확인 중 다른 세션이 main을 be35079→6ac9552로 동기화했으며 그 변경을 이번 성과로 세지 않는다. 상세는 reports/worktree-closeout-20261105.md.
risk: 종료는 작업 성공·main 통합 판정이 아니다. .venv/cache는 재생성이 필요하다. 앱 archive와 실제 관리 worktree 제거는 별도 관측한다. Git 제외 보관 자료는 원격에 자동 보존되지 않는다.
rollback: git worktree add <복원 경로> <보존 branch 또는 SHA>, 필요한 ignored 증거만 복원하고 환경 재설치. 앱 세션은 set_thread_archived archived=false 또는 앱에서 unarchive; 관리 snapshot이 있으면 앱 복원 절차. 문서 기록은 해당 커밋 revert. 원래 branch/커밋을 삭제하지 않는다.
