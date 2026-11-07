# surface-global-rank-amax-20261107
owner: Codex
status: implementing
base_sha: 4a65e12
branch: main, serial execution on basic checkout
Goal: authorized one retry only, amax tie gradients and failure diagnostics, no optimization/metric relaxation.
Allowed: tools/experiments/surface-global-rank-amax-20261107/{worker,objective,metrics}.py; this task; docs/collaboration/reports/surface-global-rank-amax-20261107.md; ignored artifacts/surface-global-rank-amax-20261107/{plan.json,objective-before.py,worker.py,objective.py,metrics.py,REPORT.md,report.html} and common-runner output.
Forbidden: existing source/records/labels, production models, criteria, other tasks.
Structure: objective4 functions incl closure, metrics4, worker1 lambda; changed closure→save_diagnostics1 transition, existing closure→detail_bag_loss→point_bag_loss2 transitions. Diagnostics uses existing optimizer state, no new iteration/fit.
Contract: ranking max(dim1)→amax(dim1), total loss finite check, save fold/loss/gradient/finiteness/n_iter/func_evals/last_step. Label/folds/base loss/mass/L2/backbone/init/seed/threshold and LBFGS1000 unchanged. Frozen reference is original completed revised baseline; failed run is NOT performance reference. New files baseline=null, prior objective preserved as objective-before.py.
Criteria: maximum gradient<=1e-5; FN<=67/370, FP<=112/1406, AUC delta>=0.03 AND paired photo bootstrap95%lower>0. All AND. Failure stops with no retry.
Checks: py_compile, amax value/tie-gradient tests, diagnostics serialization synthetic, source diff, common-runner hashes/rows, photo HTML/open request.
Risk: non-smooth objective can still fail. Exact optimizer stop reason inferred conservatively from saved counters/state, not asserted without proof. No independent generalization claim.
HTML: artifacts/surface-global-rank-amax-20261107/report.html; actual candidate scores only if completed; otherwise baseline photos explicitly marked.
Rollback: production unchanged; retain failed evidence; revert this new source/docs only if necessary.
