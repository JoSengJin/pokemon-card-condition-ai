# surface-global-rank-alignment-20261107
owner: Codex
status: completed_experiment_failed
base_sha: d5fbce7
branch: main, serial basic-checkout experiment
Goal: exactly one fixed0.01 alignment safeguard experiment after synthetic tests; no further retry on failure.
Allowed: tools/experiments/surface-global-rank-alignment-20261107/{worker,objective,metrics,armijo_direction,checks}.py; this task; docs/collaboration/reports/surface-global-rank-alignment-20261107.md; ignored artifacts/surface-global-rank-alignment-20261107/ and common runner outputs.
Forbidden: prior source/records/labels/production/progress criteria and other tasks.
Contract: change only direction safeguard. After relative-curvature L-BFGS direction, alignment=-g·d/(||g||||d||)<0.01 clears pair history,scale,stale step and replacesd=-g. Setprev_gradient=currentg and store direction; caller records next accepted Armijo step. Log pre/post alignment/reset/history,distinguish attempted curvature update from discarded history. No new loss evaluations. Same loss,relativegate,Armijo,duplicateguard,labels/folds/features/mass/L2/init/seed/threshold and metrics.
Criteria: finalgradient<=1e-5,internaltarget1e-7; FN<=67/370,FP<=112/1406,AUC+0.03 AND photo-bootstrap95%lower>0 allAND. Same completed revised baseline. Max1000iterations/1250total evaluations per fold including initial. Failed run not performance reference.
Structure: objective3functions,direction1,metrics4,worker0,checks3. worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss4transitions; worker→fit→lbfgs_direction2. Guard inline, no callbacks/recursion.
Checks: inherited35direction steps/history20 on smooth fixture,exactloss/gradient,Armijo,convergence,duplicateguard,budget1250,relativegate boundaries; new0.0099reset/0.0101preserve,clear history/scale/stale step,consistent fresh gradient/direction and next accepted-step curvature. Compile/AST/diffcheck;runner frozenactualimport/inputSHA;HTML/open/render distinction.
Risk: gradient fallback can consume backtracking budget near nonsmooth points; alignment guard does not guarantee rawgradient convergence. Fixedthreshold0.01 only, no sweep.
HTML: artifacts/surface-global-rank-alignment-20261107/report.html; failed run shows baseline photos clearly marked, no invented candidate scores.
Rollback: new source/docs only viarevert, retainrecord/snapshot/checkpoint/logs; productionunchanged.

Handoff: source20379e7; artifacts/experiments/20261107T140438-a4c05402/record.json failed.469iteration/468accepted/1250evaluations;gradient0.0014407593330947113. Fourrestartsrestorealignment~1 but backtrackingrequired. Checkpointverified. No retry/criterionchange. HTMLgenerated.

HTML open exit0: 열기 요청 성공, 실제 렌더 미확인. git diff --check 통과.
