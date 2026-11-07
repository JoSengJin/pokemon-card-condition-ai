# surface-global-rank-pairlme-20261108
owner: Codex
status: completed_criteria_not_met
base_sha: 1569bfe
branch: main, serial basic-checkout experiment
Goal: synthetic verification then exactly one normal-pair reduction experiment; no further retry on failure/criterion miss.
Allowed: tools/experiments/surface-global-rank-pairlme-20261108/{worker,objective,metrics,armijo_direction,checks}.py; this task; docs/collaboration/reports/surface-global-rank-pairlme-20261108.md; ignored artifacts/surface-global-rank-pairlme-20261108/ and common runner outputs.
Forbidden: previoussource/records/labels/production/progress criteria and other tasks.
Single change: after softplus of ALL trainfold positive×normal region pairs, replace normal-axis arithmeticmean by logsumexp(pair_loss,normalaxis)-log(Nnormal), then meanpositive. Implicitreductiontemperature1 fixed; patch-pooltau0.1 remains unchanged. No error-ID selection/OOF weighting/subsampling. Positive/outputmax/basebagloss/masks/mass/L2/init/seed/labels/folds/frozenbackbone/input448 and optimizer(relativegate/alignment0.01/Armijo/duplicate/checkpoint) unchanged.
Criteria: finalgradient<=1e-5,internaltarget1e-7;FN<=67/370,FP<=112/1406,AUCdelta>=0.03 AND pairedphoto95%lower>0 allAND. Same original completed revised baseline. Previous candidates contextual only. Max1000iterations/1250total evaluations per fold inclinitial/noextra final evaluation. No temperature/threshold search/retry.
Structure: objective3functions,direction1,metrics4,worker0,checks3. worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss4transitions; worker→fit→direction2. Reductioninline, no callbacks/recursion.
Checks: independentperpositive objective/autograd,normal-axis allpairpositiveweights/higherlossmoreweight/equallossnormalization/permutation/algebraicidentity; inheritedpatchpooltau/mask/positivehardmax,direction/history20,Armijo,duplicates,budget1250,relativegate/alignmentstate. Compile/AST/diffcheck;runneractualimport/inputSHA/rows;HTML/open/render status.
Snapshots: newfilesbaseline=null, originalobjective-before.py saved; actualimportsourcehashesfrozen.
Risk: stronger pressure on high-loss normal pairs may increase FN or overfit ambiguous normals; fixed labels preserved. Smooth aggregation doesn't guarantee AUC/FPR improvement or independent generalization.
HTML: artifacts/surface-global-rank-pairlme-20261108/report.html; completed actual204photos/1776truth+scores; failure explicitbaselineonly.
Rollback: revert newsource/docs only, retainrecord/snapshots/models/logs/checkpoints; productionunchanged.

Handoff: source6a71917; artifacts/experiments/20261107T164913-be5e859b/record.json completed, acceptancefalse/evaluationcriterionfalse.5foldconverged,FN59/370,FP176/1406,AUC0.92923379 delta+0.01258314/CI[0.00673871,0.01897883].FPcap/AUCdeltafail;noadoption/noretry. HTML204photos1776zonesverified.

HTML open exit0: 열기 요청 성공, 실제 렌더 미확인. git diff --check 통과.
