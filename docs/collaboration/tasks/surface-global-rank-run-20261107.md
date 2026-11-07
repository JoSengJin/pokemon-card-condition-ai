# surface-global-rank-run-20261107
owner: Codex
status: completed_experiment_failed
branch: main (serial main execution)
base_sha: 0a7f989
Goal: one authorized global region ranking loss experiment, same1776 rows/five folds, no tuning/retry.
Allowed: tools/experiments/surface-global-rank-run-20261107/{worker,objective,metrics}.py; this task; docs/collaboration/reports/surface-global-rank-run-20261107.md; ignored artifacts/surface-global-rank-run-20261107/ and common runner outputs.
Forbidden: labels, existing workers, production models, frozen evaluation sets, progress criteria and scores.
Structure: worker one existing lambda callback; objective3 definitions including closure; metrics4. Objective closure → detail_bag_loss → point_bag_loss (2 transitions). Existing feature extraction imports/calls unchanged. New ranking term uses PyTorch tensor operations directly.
Contract: coefficient0→1 only, uniform all positive×negative train-region pairs, same masked max logit. Original mass/base bag loss/centering/L2/init/LBFGS/folds/features/seed fixed. Reference saved revised baseline. No held-out training labels.
Checks: source diff against historical fitter, mathematical synthetic rank checks, py_compile, common runner frozen row/SHA/convergence checks, photo HTML and open request.
Criteria: AUC+0.03, paired photo bootstrap95%lower>0, FN<=67/370, FP<=112/1406, all AND. Convergence failure terminates; no retry.
Risk: max objective may fail convergence; developmental CV selection bias, no independent generalization evidence.
Rollback: no production weights changed; retain all experiment evidence; revert new source/document commit if needed.
HTML: artifacts/surface-global-rank-run-20261107/report.html, photos/human answers/both model scores, development CV explicitly.

Handoff: record20261107T064427-9d2a480e failed; fold0/5; no candidate metrics, no retry. Source de96226. Baseline FN67/FP201 verified; registered source hashes unchanged. HTML generated with prior baseline photos only.

HTML open: sandbox 기본앱 열기 실패(-10661), 권한상승 open 성공(exit0); 실제 렌더 미확인. git diff --check 통과.
