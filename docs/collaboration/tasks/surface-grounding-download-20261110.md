# 검토 JSON 파일로 전달 — 2026-11-10

- task_id: surface-grounding-download-20261110
- owner/status: Codex main / integrated/completed; solo primary checkout, main.
- base_sha: 2de1dfaa394a90df827f888bfc01066dc3c2bb36.
- authorization: User requested an easier way to provide reviewed JSON. Add a native JSON download beside existing copy/export, keep answer schema/packet/labels/model unchanged.
- goal: One recorded review can be downloaded as UTF-8 JSON and attached to chat; empty responses cannot be downloaded; submitted notes/packet identity preserved; old open report/runtime untouched.
- allowed_files: tools/diagnostics/surface-grounding-20261110/{review.js,report.py,review_checks.cjs}; this task; docs/collaboration/reports/surface-grounding-download-20261110.md.
- ignored_outputs: artifacts/surface-grounding-download-20261110/{report.html,checks.log,postflight.json,opening-status.txt,remote-sync.json}; no new inference/experiment/model/labels/point answers. Keep old report,run/runtime/snapshots/packet immutable.
- contract: Same313review cases and packet397ed4fb79b6ff215a6cd4ec5d582b86b8cd1f9af7db63cbe3dc713c820f10cc. download uses validated existing export via Blob/objectURL, filename includes packet prefix/response count. Only explicit recorded responses exported, no default answers. Visible copy textarea and resume remain. Revoke old objectURL on change, keep current URL until next export so browser can finish download. No server/upload/storage/dependency.
- structure: review.js7→7functions,report.py3→3,review_checks.cjs≤7. event→refreshExport→validateAnswers→exactKeys≤3project transitions; native anchor download needs no new handler. No recursion.
- checks: existing syntheticPython/Node checks; Node actualBlob/fetch download payload matches exact submitted JSON/notes, identity/filename/count and empty-disabled state; static actual313case/newanchor/embeddedpacket/relativepaths checks. No model evaluation.
- HTML: artifacts/surface-grounding-download-20261110/report.html, new URL to protect old open-tab input; open same OS path with host permission, record opening versus render verification. No browser/file-content policy bypass.
- risks/rollback: unsaved old-tab input remains there; user must copy/export before refreshing it. Some browsers differ in file-save behavior; copy textarea fallback retained. Rollback this UI commit only, preserve diagnostics/packet/humananswers. Ordinarypush and remoteSHA confirmation. No new worktree/other-worktree/.claude changes.

## Checks before report generation

Existing Python/Node grounding contracts passed. New NodeVM test executes actual refreshExport with native Blob/objectURL and fetch, verifies exact UTF-8 JSON/notes/packet identity, filename/count, disabled empty state and revoked previous URL. No browser render/download claim. JSproduction7functions unchanged; Nodechecks5definitions (async check+3DOMmethods+catch arrow),Pythonreport3. Native anchor retains link keyboard semantics. Source changes3files,37lines mostly new meaningful download test. No model/worker/runtime/packet/oldHTML edits. New313case HTML generated after UI source commit; original old-tab state unaffected.

## Handoff

Source7eb2636ba380057a06857aa0ec2bf5eab4dd4e2a. Existing grounding+new nativeBlob UTF-8 download test passed. Actual313case HTML+samepacket/paths/oldHTMLhash/frozenruntime checked. New artifacts/surface-grounding-download-20261110/report.html opened with same host OSopen exit0; render/browserdownload unobserved,securitypolicyunchanged. Original open report untouched; no inferred current user input. Total5files changed,JS7functions/Pythonreport3/Nodechecks5,max3projecttransitions. Fullcheck/risk/rollback in matchingreport. No training/inference/model/label/criterion/progresschange;78/100v1.13 maintained. Ordinarypush/remoteSHA evidence at artifacts/surface-grounding-download-20261110/remote-sync.json. No newworktree; old retained checkouts/.claude unchanged.
