# surface-global-rank-armijo-20261107
owner: Codex
status: implementing
base_sha: 3dd1e5d
branch: main, serial basic checkout
Goal: fixed-budget flat L-BFGS direction with Armijo and exact duplicate rejection; synthetic checks then exactly one real experiment. If failed, evidence-based code/diagnostic followup only, no second real experiment.
Allowed: tools/experiments/surface-global-rank-armijo-20261107/{worker,objective,armijo_direction,metrics,checks}.py; this task; docs/collaboration/reports/surface-global-rank-armijo-20261107.md; ignored artifacts/surface-global-rank-armijo-20261107/ and common runner outputs.
Forbidden: prior workers/records/labels/production models/progress criteria/other tasks.
Contract: keep exact existing bag/pair loss and gradient, float64,centering,mass,L2,init,seed,mask,folds,threshold and L-BFGS two-loop curvature/history20. Step selection only becomes Armijo c1=1e-4,halving,strict actual loss decrease. Block exact candidate=current or candidate=previous trial before evaluating. Log step float/hex,parameter SHA/actual displacement,loss hex/derivative/gradient,active patch change count and evaluations. Flat functions with no nested optimizer callbacks or privateAPI patches. <=1000iterations/1250loss-gradient evaluations per fold including initial evaluation; no extra final reevaluation.
Criteria: final gradient<=1e-5, internal target1e-7; FN<=67/370,FP<=112/1406,AUCdelta>=0.03 AND pairedphoto95%lower>0 allAND. Same frozen completed revised model reference; previous failed runs not performance references.
Structure: objective3functions(detail_bag_loss,loss_and_grad,fit_detail_head), armijo_direction1,metrics4,worker0,checks3. worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss=4transitions. worker→fit→lbfgs_direction=2. No recursive/custom optimizer callback calls; tensor/PyTorch math primitives unchanged. Function limits<=7 each.
Checks: 35direction steps including history eviction match installed torchLBFGS; exact old loss/autograd parity; synthetic convergence/Armijo strict decrease; precise logging/evaluation equality; no-progress exact duplicate fixture;1250budget fixture; compile/AST/diff-check; runner frozen SHA/rows; HTML/open/render status.
Risk: Armijo may approach a nonsmooth minimum without satisfying raw gradient gate. Flat implementation direction parity tested but changing step selection is not guaranteed to improve performance. Strict loss decrease prevents rounded non-decrease acceptance.
HTML: artifacts/surface-global-rank-armijo-20261107/report.html; failure uses explicitly historical baseline photos; completed model comparison uses actual scores.
Rollback: no operational state changed; revert new source/docs only, retain all records/snapshots. Followup corrections must not rewrite experiment snapshots.
