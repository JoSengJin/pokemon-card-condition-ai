# surface-global-rank-pairmix-20261108
owner: Codex
status: implementing
base_sha: d4b0881
branch: main, serial basic-checkout experiment
Goal: synthetic verification then exactly one fixed50:50 normal-pair aggregation experiment; no extra retry after failure/criterion miss.
Allowed: tools/experiments/surface-global-rank-pairmix-20261108/{worker,objective,metrics,armijo_direction,checks}.py; this task; docs/collaboration/reports/surface-global-rank-pairmix-20261108.md; ignored artifacts/surface-global-rank-pairmix-20261108/ and common runner outputs.
Forbidden: previoussources/records/labels/production/progresscriteria and other tasks.
Single change: normal-pair aggregation becomes0.5*arithmeticmean(allpairsoftplus)+0.5*meanpositive(logsumexp(pairsoftplus,normalaxis)-logNnormal). Fixed totalrankcoefficient1, no mixture tuning. All trainfold pairs/no OOF-ID selection. Patchtau0.1/normalupperLSE/positive/outputmax/basebagloss/mask/mass/L2/init/seed/labels/folds/backbone/input448 and optimizer(relativegate/alignment0.01/Armijo/duplicate/checkpoint) unchanged.
Criteria: finalgradient<=1e-5,internaltarget1e-7;FN<=67/370,FP<=112/1406,AUCdelta>=0.03 AND pairedphoto95%lower>0 allAND. Same original completed revised baseline, priorcandidates contextual only. Strict1000iterations/1250total evaluations per fold inclinitial/no extra final evaluation. No threshold/temperature search/retry.
Structure: objective3functions,direction1,metrics4,worker0,checks3. worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss4transitions;worker→fit→direction2. Inline mixture, no callback/recursion.
Checks: independentperpositive objective/autograd;exact50:50value/gradient/allpairpositivegradientfloor/equal-loss consistency; inheritedpatchpool/mask/positivehardmax,direction/history20,Armijo/convergence/duplicates/budget1250/relativegate/alignmentstate. Compile/AST/diffcheck;runneractualimport/inputSHA/rows;HTML/open/renderstatus.
Snapshots: newfilesbaseline=null, priorobjective-before.py preserved; actualimport hashesfrozen.
Risk: mixture may trade away LME's AUC gain or arithmetic's FN benefit; no guarantee of largeFP reduction. Labels unchanged. RepeateddevelopmentCVnotindependent.
HTML: artifacts/surface-global-rank-pairmix-20261108/report.html; completed actual204photos1776truth+scores, failure explicitbaselineonly.
Rollback: revert newsource/docs only; preserve record/snapshot/models/log/checkpoints; productionunchanged.
