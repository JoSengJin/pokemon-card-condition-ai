# 승인된 레거시 작업 종료·보관 — 2026-11-05

**개발 진척 78/100(v1.13), 변화 0점. 레거시 작업 11개 종료 기록·worktree 제거, 완료 앱 세션 1개 archive, 과거 보고서 6파일 branch 보존.**

사용자 승인: "4개 항목 권장대로 진행해". 1028-6 보관·종료, 과거 보고서는 main에 추가하지 않기, 레거시10개 종료·이력 보존 후 작업 폴더 제거, 완료 Codex 세션 archive라는 직전 권장을 승인했다. 이전 삭제 금지는 이 승인 대상에 한해서만 대체한다.

검증 기준 main `6ac9552e71a7aa0e13c0b84ffda501e639b59a47`. 이번 변경은 Git 관리·종료 기록이며 제품·모델·라벨·진척 기준 변경이 아니다. 다른 세션이 반영한 main 변경을 이번 성과로 세지 않는다.

## 1. 종료 승인 이행 정본

아래 작업의 현행 종료 판정은 `closed_by_user`다. 작업 성공·main 코드 통합·실험 완료로 바꿔 쓰지 않는다. 원래 task 문서의 과거 assigned/rejected/review_pending 기록은 삭제하거나 수정하지 않았다. 1028-6도 이제 사용자 승인으로 보관·종료하며 실패 원인을 새로 추정하지 않는다.

| branch | 보존 HEAD | 종료 상태 | 실제 조치 |
|---|---|---|---|
| claude/task-1026-2 | `341acc95acf2a0e20d824ad5d66f44447aa55210` | closed_by_user | removed |
| claude/task-1027-1 | `d964af5ae60cdc68aaa484719da55b981c15916c` | closed_by_user | removed |
| claude/task-1027-3 | `16dce587f5c8b27774d5dced64dd5f79ff9ea798` | closed_by_user | removed |
| claude/task-1027-4 | `5f1b17c3ea2dd180901e155b0590600ab34afb01` | closed_by_user | removed |
| claude/task-1028-1 | `1e5a8db9c0c255a30444db60ea81c3caeca2b5b3` | closed_by_user | removed |
| claude/task-1028-2 | `2dfde1819bd3f900805f92ea2ec5b9f4b7fb822c` | closed_by_user | removed |
| claude/task-1028-3 | `43d2532ac03ea802e901d35c9d2e861e5a2ad660` | closed_by_user | removed |
| claude/task-1028-4 | `9c4f6df3a8c174fa8e7bcaaa79da696314cb51bf` | closed_by_user | removed |
| claude/task-1028-5 | `d2d8843d56eb45b02d7908774319a44c1990e6b5` | closed_by_user | removed |
| claude/task-1028-6 | `8c8a8224e1eeee4276ca4b29892a0ac655e51106` | closed_by_user | removed |
| claude/task-1028-7 | `d65948283f91363c9c2926a079f386f79b32ce25` | closed_by_user | removed |

pair-control 실행 상태 파일은 접근 금지 대상이므로 읽거나 수정하지 않았다. 이 문서가 종료 승인 이행 기록이며, 금지된 서버의 런타임 task 상태까지 동기화됐다는 뜻은 아니다. 두 개발 중 worktree·미커밋 변경·Mastra 서버는 이번 턴 접근·조작하지 않았다.

## 2. 과거 보고서 보존

새로 main에 복사한 과거 보고서는 0개다. 기존 branch/commit에 다음 6파일을 보존했다. SHA는 각 원본 Git blob 내용을 SHA-256으로 계산한 값이다. A3 branch는 기존 worktree도 그대로다. 종료된 레거시 문서는 branch와 복구 bundle에 보존된다.
- `6c0d7ba6d81815082f385b55c58be3938d68f786:docs/collaboration/reports/a3-data-intake-batch-20261025.md` (claude/a3-data-intake-batch-20261025), SHA-256 `74b5d8130f4bbe7b450c872a8cf4cc906b6572d2a43995b25e2f530d356150d1`.
- `6c0d7ba6d81815082f385b55c58be3938d68f786:docs/collaboration/reports/a3-data-intake-batch-20261025.html` (claude/a3-data-intake-batch-20261025), SHA-256 `10cc3aafef35459d7af159fbaf0bd7c144d69c6b343e914ec83cd4df8d894976`.
- `43d2532ac03ea802e901d35c9d2e861e5a2ad660:docs/collaboration/reports/task-1028-3-handoff.md` (claude/task-1028-3), SHA-256 `21936f50844bb152c603165f6c68cbeca249af4b961e1ce0b9b83ea520485b9a`.
- `9c4f6df3a8c174fa8e7bcaaa79da696314cb51bf:docs/collaboration/reports/task-1028-4-status-20261028.md` (claude/task-1028-4), SHA-256 `8078658edfdf398246b915532cdda4fe2df5e5f5306d199e009533bb693e911d`.
- `9c4f6df3a8c174fa8e7bcaaa79da696314cb51bf:docs/collaboration/reports/task-1028-4-status-20261028.html` (claude/task-1028-4), SHA-256 `43d61c7401b05ffa6deae1126e2d1cac30f685242795d26c8d4c7f64149171a0`.
- `d2d8843d56eb45b02d7908774319a44c1990e6b5:docs/collaboration/reports/task-1028-5-status-20261028.md` (claude/task-1028-5), SHA-256 `f035c5ae04d5453199b6304d03e76ea0c188f1a5065550e03f37d34af2c44249`.

## 3. 완료 앱 세션 archive

- 대상: `01a15109-e475-7c20-b6cb-2f3984059215`, codex/review-manifest-dedupe-20261025의 소유 세션. 공식 read_thread로 notLoaded·마지막 turn completed를 확인했다. 다른 세션을 생성하거나 메시지·모델 요청을 보내지 않았다.
- checkout의 HEAD `4ef75f4491c31c22ff459b255ec449ca9ea57df2`, porcelain clean, Git 작업 없음, process command/cwd 사용 없음 확인. ignored247개는 Python cache뿐이고 고유 증거는0개다.
- `codex-app-tools`의 `set_thread_archived(archived=true, hostId=local)` 결과 archived=true. 읽기 전용 DB에서도 해당 세션 archived=1 확인. 앱 DB를 직접 수정하지 않았다.
- 실제 관측: archive 후 관리 checkout 폴더는 남아 있다. 앱 소유권을 존중해 일반 Git remove로 강제 정리하지 않았다. 현재 대화에 연결된 worktree attachment가 없어 archive_worktree 도구의 대상으로 임의 등록/소유권 변경하지 않았다.
- [OpenAI 공식 worktree 안내](https://learn.chatgpt.com/docs/environments/git-worktrees)는 관리 worktree의 앱 정리·snapshot 복원을 설명한다. 세션 archive 완료와 실제 폴더 제거 여부를 구분한다.

## 4. 보존·실행 검증

- 대상 branch12개를 `preserved-branches.bundle`로 보존. 크기 1902308 bytes, SHA-256 `3982c12cbaa4a899250981d8770aed48f9b596472b40b2c11d419b8702cbfe85`. `git bundle verify`와 `git bundle list-heads`로 12개 전체 ref/SHA를 확인했고 정리 후에도 원래 branch ref가 모두 동일하다.
- 제거 직전 고정 HEAD·porcelain·진행 Git 작업·프로세스 command/cwd를 확인했다. 기존 workspace.lock이 있는7개는 비차단 flock을 획득하고 git worktree remove 반환까지 유지했다. 기존 잠금이 없는4개는 파일을 새로 만들거나 삭제하지 않았다.
- ignored 전체 목록을 조사했고 잠금 기록7파일을 tar 보존 후 멤버·SHA 검증했다. .venv/Python cache/egg-info는 재생성 가능 자료로 제외했다. 민감 원본·비밀 설정·미커밋 파일을 삭제한 대상은 없다.
- 명령: `./develop -- python3 artifacts/worktree-closeout-20261105/cleanup.py` 안에서 main 개발 잠금과 대상별 잠금을 사용. 대상마다 일반 `git worktree remove <path>`만 실행. --force, prune, branch delete, rm, 서버 종료, stash/reset/rebase 없음.
- 검증: 제거11개 경로 소멸, 보존12개 branch ref 동일, bundle/압축본 SHA 재대조, 앱 archived=1, 과거 보고서6파일이 각 branch에 존재하고 main에 새로 편입되지 않았음을 확인. 로컬 절대경로/비밀값은 이 문서에 기록하지 않는다.
- 미실행: 코드·제품 테스트, 실험·학습·모델 추론·외부 AI 호출. 제품 코드가 바뀌지 않아 테스트 재실행은 하지 않았다. 정확도·일반화·속도·비용 개선 근거가 아니다. HTML 열기/렌더 결과는 ignored audit.json에 기록한다.

고유 ignored 증거 SHA:
- claude/task-1027-3: `pokemon-card-condition-claude-task-1027-3.tar.gz`, archive SHA-256 `eb462024966d6964f3e9da0e082ad7c6db66254ae5c4f2536241133f0dd23902`.
  - `artifacts/development-cycle/workspace.lock`: `c52a7317076a5ea7910057054b260776020623264e606bf9e1dccb8a4e29b7e3` (47 bytes).
- claude/task-1027-4: `pokemon-card-condition-claude-task-1027-4.tar.gz`, archive SHA-256 `ed1166803cb1092a2d1701dd04cf791ba7af64f06cf173fb935af03a81699142`.
  - `artifacts/development-cycle/workspace.lock`: `26f72896619654109a77adce29467aeb58eb986485e0127008e3014e83742f3d` (47 bytes).
- claude/task-1028-2: `pokemon-card-condition-claude-task-1028-2.tar.gz`, archive SHA-256 `baa63f8817c8a2e82f04976e934e5521e06c96085fd827e395aad1cee048c1b9`.
  - `artifacts/development-cycle/workspace.lock`: `159003e7b760af7a17533c50a31769f76e950ac929139f26f0b741a0a4b8bfef` (47 bytes).
- claude/task-1028-3: `pokemon-card-condition-claude-task-1028-3.tar.gz`, archive SHA-256 `6a6cf2c664ca0cb96856be71d4fb28734cae1daac435075663a52da8373cacdd`.
  - `artifacts/development-cycle/workspace.lock`: `32c54d4482573acebdd3c8f27878ad61e72c33cc85b2c9c3e468f8950875cd20` (47 bytes).
- claude/task-1028-4: `pokemon-card-condition-claude-task-1028-4.tar.gz`, archive SHA-256 `7ef49e8001204949dd29318da45b32792e831c290cf005ab0462224238750b80`.
  - `artifacts/development-cycle/workspace.lock`: `41e9cf9c30052077cba8db59810a385300571323052414c306d475ee1818ec1b` (47 bytes).
- claude/task-1028-5: `pokemon-card-condition-claude-task-1028-5.tar.gz`, archive SHA-256 `0ae0d703493f6ce2c4300e5a27704c32f2f041786768d548409719995a93e55c`.
  - `artifacts/development-cycle/workspace.lock`: `4de2b9d9f7244b024b45080aaf6e2ffc3166183296c12cb465a7fb7621f63d0f` (47 bytes).
- claude/task-1028-6: `pokemon-card-condition-claude-task-1028-6.tar.gz`, archive SHA-256 `c5da467f51bc3147f4ab0df1b155e0f7dc81d76b71ca8283ba3da6d2bcce9b7c`.
  - `artifacts/development-cycle/workspace.lock`: `1d59ab31668dae0e43934105a02dea8e960b04d4ffc1e23b6c0229d83cf4c1d0` (47 bytes).

## 5. 변경·리스크·롤백

- 변경 파일: `docs/collaboration/tasks/worktree-closeout-20261105.md`, 이 보고서. 감사 JSON·Git bundle·압축 증거·해시 목록·HTML은 Git 제외 artifacts/worktree-closeout-20261105/에 보존한다. 기존 .claude/ 미추적 파일은 건드리지 않는다.
- 핵심 diff: 사용자 결정 대기였던11개에 closed_by_user 종료 판정과 실제 제거 결과를 기록. 과거 보고서는 branch만 유지. 앱 완료 세션 archive를 공식 도구로 수행. 이전 19개 검토 보고서는 당시 기록으로 보존하며 새 결과는 이 문서가 이어받는다.
- 리스크: 종료된 worktree를 참조하는 오래된 명령/외부 task 상태는 디렉터리가 없어 실행되지 않을 수 있다. 금지된 pair-control runtime은 수정하지 않았다. .venv/cache는 복원 후 재설치가 필요하다. ignored 백업은 원격에 자동 업로드되지 않는다.
- 원래 저장소에서 checkout 복원: `git worktree add <복원 경로> <아래 보존 branch>`; 필요한 ignored tar 증거만 상대경로로 복원하고 가상환경 재설치. 모든 branch와 commit을 보존했다.
- `git worktree add <path> claude/task-1026-2` (고정 HEAD `341acc95acf2a0e20d824ad5d66f44447aa55210`).
- `git worktree add <path> claude/task-1027-1` (고정 HEAD `d964af5ae60cdc68aaa484719da55b981c15916c`).
- `git worktree add <path> claude/task-1027-3` (고정 HEAD `16dce587f5c8b27774d5dced64dd5f79ff9ea798`).
- `git worktree add <path> claude/task-1027-4` (고정 HEAD `5f1b17c3ea2dd180901e155b0590600ab34afb01`).
- `git worktree add <path> claude/task-1028-1` (고정 HEAD `1e5a8db9c0c255a30444db60ea81c3caeca2b5b3`).
- `git worktree add <path> claude/task-1028-2` (고정 HEAD `2dfde1819bd3f900805f92ea2ec5b9f4b7fb822c`).
- `git worktree add <path> claude/task-1028-3` (고정 HEAD `43d2532ac03ea802e901d35c9d2e861e5a2ad660`).
- `git worktree add <path> claude/task-1028-4` (고정 HEAD `9c4f6df3a8c174fa8e7bcaaa79da696314cb51bf`).
- `git worktree add <path> claude/task-1028-5` (고정 HEAD `d2d8843d56eb45b02d7908774319a44c1990e6b5`).
- `git worktree add <path> claude/task-1028-6` (고정 HEAD `8c8a8224e1eeee4276ca4b29892a0ac655e51106`).
- `git worktree add <path> claude/task-1028-7` (고정 HEAD `d65948283f91363c9c2926a079f386f79b32ce25`).
- 저장소 자체 복구가 필요하면 `git clone <bundle 위치> <새 저장소>` 후 보존 branch를 선택한다. bundle은 self-contained임을 verify로 확인했다.
- 앱 세션은 같은 set_thread_archived 도구의 archived=false 또는 앱에서 unarchive. 현재 관리 checkout이 남아 있으므로 별도의 폴더 복원은 실행하지 않았다.
- 종료 문서만 되돌리려면 이번 문서 커밋을 ./develop -- git revert 후 일반 push. 문서 revert만으로 checkout 제거가 취소되지는 않으므로 위 git worktree add를 별도로 사용한다.
