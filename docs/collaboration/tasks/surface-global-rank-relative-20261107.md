# surface-global-rank-relative-20261107
owner: Codex
status: implementing
base_sha: 8ee0a91
branch: main, serial basic-checkout experiment
Goal: exactly one relative curvature gate experiment after synthetic verification; failure reports only, no further retry.
Allowed: tools/experiments/surface-global-rank-relative-20261107/{worker,objective,metrics,armijo_direction,checks}.py; this task; docs/collaboration/reports/surface-global-rank-relative-20261107.md; ignored artifacts/surface-global-rank-relative-20261107/ and common-runner outputs.
Forbidden: prior records/source/labels/production/progress criteria and other tasks.
Contract: only finite(ys) AND ys>numel(y)*eps(dtype)*norm(y)*norm(s) replaces absolute ys>1e-10. Record ys, bothnorms, relativefloor,update,H_diag directly in fit trace. All other two-loop/history20/L2/mass/init/amax/objective/Armijo/threshold/labels/folds/features/seed unchanged. Existing failure-state checkpoint/ULP/patch-index logs retained. No extra evaluation for diagnostics. Strict1000iterations/1250total evaluations including initial, no final extra evaluation.
Criteria: finalgradient<=1e-5, internaltarget1e-7, FN<=67/370,FP<=112/1406,AUC+0.03 AND photo-bootstrap95%lower>0 allAND. Reference remains original completed revised baseline; failures not performance reference.
Structure: objective3functions, direction1,metrics4,worker0,checks3. worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss4transitions; worker→fit→lbfgs_direction2. Norm/logging are inline tensor operations, no new callbacks/recursion.
Checks: inherited exact objective/gradient and35direction steps on smooth fixture/history20, synthetic convergence/Armijo/duplicate/budget1250; new tinypositive/negative/zero/nearlyorthogonal/nonfinite/scale-invariant curvature cases; compile/AST/diffcheck; runner source/inputhashes/rows; HTML/open/render status.
Experiment snapshots: new files baseline=null; original direction/objective preserved as *-before.py. Plan input hashes also freeze actual tracked modules imported by worker.
Risk: relative gate may accept small unreliable curvature near max transitions; H_diag may become unstable. Finite positive gate is not a convergence guarantee. No criterion relaxation/retry.
HTML: artifacts/surface-global-rank-relative-20261107/report.html. Candidate output only if actual completed inference; failures show explicitly historical baseline photos.
Rollback: no production edits; revert new source/docs if needed, preserve all experiment evidence.
