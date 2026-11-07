# surface-global-rank-change0-20261107
owner: Codex
status: completed_experiment_failed
base_sha: 9a41805
branch: main, serial main checkout experiment
Goal: one authorized tolerance_change0 retry; no automatic subsequent retry.
Allowed: tools/experiments/surface-global-rank-change0-20261107/{worker,objective,metrics}.py, this task, docs/collaboration/reports/surface-global-rank-change0-20261107.md, ignored artifacts/surface-global-rank-change0-20261107/ and common-runner output.
Forbidden: prior sources/records/labels/production/progress criteria and all other tasks.
Change: tolerance_change1e-12→0 only; diagnostics adds prev_loss/final_loss/signed/absolute difference and confirms max_eval. Worker hypothesis/path updated, metrics exact copy. Prior objective preserved as objective-before.py; new source baseline=null.
Controls: amax/objective/mass/init/backbone/folds/labels/L2/seed/threshold unchanged. max_iter1000/defaultmax_eval1250, tolerance_grad1e-7, final gradient<=1e-5 unchanged. FN<=67/370,FP<=112/1406,AUC+0.03 AND photo-bootstrap95%lower>0 all AND.
Structure: objective4functions incl closure, metrics4, worker1lambda. closure→save_diagnostics1transition; existing closure→detail_bag_loss→point_bag_loss2 unchanged. No extra optimizer step.
Checks: compile; synthetic log serialization/loss difference and default1250 cap checks; source diff; runner frozen inputs/hash/convergence; HTML and local open.
Risk: disabling progress stop can consume budget without convergence; exact zero-step and non-descent stopping remain. No convergence/generalization guarantee.
HTML: artifacts/surface-global-rank-change0-20261107/report.html. If failed, baseline photos explicitly identified with no candidate outputs. Open/render recorded separately.
Rollback: no production modification; revert new source/docs only, retain evidence.

Handoff: sourcea4370c6; artifacts/experiments/20261107T092650-fd09886a/record.json failed.161iterations/221evaluations;step0/loss difference0/gradient0.0011471. No candidate metrics/no retry. HTML generated.

HTML open exit0: 열기 요청 성공, 실제 렌더 미확인. git diff --check 통과.
