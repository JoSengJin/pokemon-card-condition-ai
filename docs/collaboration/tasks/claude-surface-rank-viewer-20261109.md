# 오순위 사진쌍 viewer — Codex 인수

- task_id: claude-surface-rank-viewer-20261109
- owner/status: Codex main 단독 / implementing. Claude 미전달, 구현/리뷰/합의 없음.
- base_sha: 3b67f12cf0be0a0cf7a20d2cb99d570f74f0c0fe
- authorization: 사용자 “클로드에게 못넘겼어 다음 진행”. 이전 viewer 범위를 Codex가 인수하며 별도 Claude 호출/에이전트 없음.
- goal: 고정rank_report.json으로15개오순위사례의두사진/관련구역/사람정답/점수/fold/margin과전체사진갤러리를보는재사용CLI를구현·검증.
- allowed_files: tools/diagnostics/surface-rank-viewer-20261109/{render.py,checks.py,fixture.json},이task,docs/collaboration/tasks/surface-rank-partition-20261109.md,docs/collaboration/prompts/claude-surface-rank-viewer-20261109.md,docs/collaboration/reports/surface-rank-viewer-20261109.md.
- forbidden_files: 기존모델/훈련/진단소스·기록·사진·라벨·평가기준·다른작업/.claude/. 소스편집은 ./develop 안에서만. 새학습/추론/통계fit/API/외부AI0. 기존schema변경없음.
- ignored_outputs: artifacts/surface-rank-viewer-20261109/{checks.log,report.html,verification.json,opening-status.txt}. 합성검사는임시디렉터리만사용. 기존HTML/기록덮어쓰기없음.
- input: artifacts/experiments/20261109T123217-c4241d83/rank_report.json. 이전task의schema v1그대로. 204사진/1776구역,520220쌍/35414오순위/AUC0.931924954826804. 표시만하고점수/정답/분할변경없음.
- CLI: python render.py --input <JSON> --output <HTML>. 표준라이브러리,서버/CDN/JS/외부네트워크없음. 사진경로는입력JSON기준으로해석하고출력HTML기준상대URL로표시. 존재하지않는사진은명시적missing. URL문자열을원격img로사용하지않음.
- contract: 총계/3bucket의쌍분모·쌍비중/오류비중/조건부AUC를구분. 15사례는두사진을나란히표시하고대상구역강조,전체1776구역도별도표시. 작은화면은1열. box는사진정규화좌표이며1e-12경계허용오차,원본유지/시각clip만허용. 구역을사람점/모델peak로칭하지않음. 순위오류와thresholdFNFP구분. 독립성/새모델향상주장금지.
- structure: render≤7함수/checks≤7함수,최대4실제호출전이. main→render_document→photo_panel→zone_table는3전이. 동적callback/재귀없음.
- checks: 합성fixture의동점/빈bucket/null AUC/HTMLescape/공백#?사진경로/missing/같은사진두구역/다른fold/경계오차/잘못된schema/입력덮어쓰기거절/CLI/함수수. 실제204사진SHA/원본JSONhash·1776구역/15사례30패널/저장점수출력대조. 실제렌더는관찰가능할때만확인,이전file정책차단우회없음.
- reporting: PROGRESS_CRITERIA.md/development-progress.json78/100v1.13유지. 변경/핵심diff/실행검증/미검증/리스크/롤백/HTML open-render상태기록. 합성·표시완료를성능개선으로간주하지않음.
- risk/rollback: 사례는margin상위선택이라대표성/인과증명아님. 기존원격모델변경없고본viewer코드만의존·실행잠금확인후일반revert/push. 기존증거/다른worktree삭제없음. 새worktree없음.
