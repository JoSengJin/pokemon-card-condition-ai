# surface-patch-evidence-batch-20261108
owner: Codex
status: diagnostic_replay_failed_backend_mismatch
base_sha: 5ba7cf0
branch: main, serial default checkout
Goal: complete authorized no-training patch diagnosis after first subset-batch replay exceeded fixed1e-6; preserve first source/record and do not loosen criterion.
Allowed: tools/diagnostics/surface-patch-evidence-batch-20261108/{worker,patch_evidence,patch_geometry,patch_report,checks}.py; this task; original task status; docs/collaboration/reports/surface-patch-evidence-20261108.md; ignored artifacts/surface-patch-evidence-batch-20261108/ and common runner output.
Contract: same score-preserving helper/formula and top2/geometry/HTML contract as original task. Restore original fold-wide scoring matrix dimensions with zero workspace for unused rows. Row-wise affine operation is independent across workspace rows; unused outputs discarded, never ground truth/evaluation rows. Selected172rows/98photos/overlapping160+6+17tags unchanged. Four saved OOF heads and heldoutfold unchanged. Save selected frozen features for evidence preservation; no retraining/no optimizer.
Criteria: unchanged synthetic exactlegacy score equality and real maxreplayerror<=1e-6, unchanged threshold predictions/all4models, unchangedtruth/boxes/masks/folds. Diagnostic subset maxFN6/maxFP166/noNewErrors checks reproduction only, not original model quality acceptance. Parent quality remains failed.
Structure: worker0functions, scorer1,geometry1,report1,checks0. Worker→scorer/geometry/report1transition, existing worker→features→views→prepared_image3. No newcallback/recursion, original training4transitionpath untouched.
Checks: original scorer exactrandom/boundary/tie/mask/single-token, exactly1matmul, geometry/EXIF/coverage,HTML/CSV, fullbatchworkspace exactselectedvalues synthetic,compile/AST/no training calls. Real savedscore/error check remains1e-6; first failedrecord retained.
HTML: artifacts/experiments/<newrecord>/report.html, with relative localphoto URLs; forward link artifacts/surface-patch-evidence-batch-20261108/report.html created aftercompletion with paths preserved.
Risk: deterministic scoring may depend on batch dimensions; replay tolerance and any firstfailure are reported. Lattice location is response evidence, not physical defect ground truth or limited ViT receptivefield.
Rollback: revert newsource/docs only; preserve originalfailedrecord/newdiagnosticrecord/features/logits/evidence; originalmodels/scores/labels unmodified.

Record20261107T224828-c9eede80 failed with same1.49e-6 baseline discrepancy; batch shape was not cause. Evaluations confirm baseline MPS vs candidateCPU. CPUcachedfeatures replay3candidateheads bitwiseexact. Followup matches original backends, no tolerance relaxation.
