# Saved OOF ranking partition and Claude viewer contract

- task_id: surface-rank-partition-20261109
- owner/status: Codex main, diagnostic implementation/execution/integration, implementing. Claude owns a separate viewer worktree only.
- base_sha: 58ad67d0b9ce4b1e90b1c54ef6ebaaf435b39d00
- authorization: User requested a Claude pair-coding prompt and independent Codex development. This task uses saved scores only. No new training, inference, feature statistics fit, external AI calls, labels or loss changes.
- goal: Partition all520220 positive-negative region pairs by photo/fold relationship; verify exact identities and produce a diagnostic artifact before selecting another representation.
- Codex allowed_files: tools/experiments/surface-rank-partition-20261109/{analysis.py,worker.py,checks.py}, this task, docs/collaboration/reports/surface-rank-partition-20261109.md, docs/collaboration/prompts/claude-surface-rank-viewer-20261109.md.
- Claude allowed_files: tools/diagnostics/surface-rank-viewer-20261109/{render.py,checks.py,fixture.json}, docs/collaboration/tasks/claude-surface-rank-viewer-20261109.md. No edits to Codex files/shared schema/models/other tasks. No direct main edits/merge/push.
- ignored_outputs: artifacts/surface-rank-partition-20261109/{analysis.py,worker.py,plan.json,preflight.json,checks.log,console.log,postflight.json,report.html,opening-status.txt,claude-prompt.txt}; new common-runner record/snapshots/observations/rank_report.json/evaluation.json. Claude uses synthetic artifacts in its own worktree only.
- source: artifacts/experiments/20261108T215307-941b3aaa/{observations.json,result.json}; folds=artifacts/surface-label-consistency-20261107/folds.json.1776 rows,370positive/1406negative,204groups,threshold0.5. Preserve exact row/score order and all source hashes.
- buckets: same_photo (same group); cross_photo_same_fold (different groups, same fold); cross_fold (different folds). Validate a photo SHA cannot belong to different groups. Different-fold OOF comparisons involve different fitted models; their inversion counts do not establish calibration as a cause.
- credits: defectscore<normalscore gives1, exact tie gives0.5, correct order0. Total pairs=370*1406=520220. Sum pair counts/strict inversions/ties/error_credit across all3 buckets exactly. AUC=1-error_credit/pairs; empty bucket auc=null. loss_share=bucket error_credit/total error_credit, or0 when total error_credit0. Never use selected error pairs to alter training or truth.
- success: independent synthetic nested-loop oracle matches every count/credit/AUC; ties/empty buckets/permutation/invalid inputs tested. Actual partition identities reproduce known AUC0.931924954826804 to1e-12 with unchanged rows/scores/hashes. Completed means diagnostic execution success, not adoption. Keep model gates FN<=67/FP<=112 unchanged; identity replay still hasFP167 and does not pass them.
- structure: analysis<=7/worker0/checks<=7 functions, each project call path<=4 transitions. Claude render/checks each<=7 functions and<=4 transitions. Do not hide callbacks/recursion.
- checks: synthetic oracle/identity/partition/frozen-input hashes/record/photo-group/fold consistency, diff/AST. No new model execution.
- reporting: Codex creates artifacts/surface-rank-partition-20261109/report.html with saved human truth/region scores and partition diagnostics. Claude viewer is separately reviewed on return; do not imply it ran. Preserve78/100v1.13 from PROGRESS_CRITERIA.md/development-progress.json. Distinguish open-command success from actual rendering.
- risk/rollback: observed OOF score relations do not prove a visual cause or future representation benefit. Same-fold subsets are not independent tests. No production changes. Revert only this task's commits after checking dependencies/lock, ordinary push, preserve evidence. No force/reset/cleanup of other sessions/.claude/.

## Frozen rank_report.json schema v1

Top keys: schema_version=1,kind="saved_oof_rank_partition",source_record(string),source_sha(string),independent=false,new_training_calls=0,new_inference_calls=0,threshold=0.5,rows_count(int),groups_count(int),positive(int),negative(int),total(object),buckets(array),photos(array),examples(array).

total fields: pairs(int),strict_inversions(int),ties(int),error_credit(number),auc(number|null),loss_share(number).
buckets: same fields as total plus key(string, one of the3 names above); always include all3, even empty.
photos: group(string),fold(int),image(string),image_sha256(string),zones(array).
zones: id(string),area(string),box([x1,y1,x2,y2],normalized0..1),target(0|1),score(number0..1),prediction(0|1),outcome(TP|TN|FP|FN). Boxes are regions, not human defect points or model peak patches.
examples: bucket(string),defect_id(string),normal_id(string),defect_score(number),normal_score(number),normal_minus_defect(number). Select at most5 strict inversions per bucket by descending margin then lexicographic IDs. Resolve zone IDs via photos. These are diagnostic examples, not representative causal evidence or training selections.

Claude CLI: python render.py --input rank_report.json --output report.html. Read JSON only; no network/CDN/JS/API/training/inference. Test with synthetic fixture only; visibly mark missing synthetic images. Show total/3buckets and denominators/AUC/credit/loss_share, all human region truth/scores/predictions/outcomes with photo overlays/tables, and both photos for each example. Real paths/photos/truth belong only in ignored artifacts, never tracked fixtures. Escape HTML and handle local image paths explicitly. No schema changes without coordinating with Codex. Do not add a generic UI framework.
