# surface-global-rank-uppernormal-20261108
owner: Codex
status: completed_criteria_not_met
base_sha: 40ddb98
branch: main, serial basic-checkout experiment
Goal: synthetic verification then exactly one unnormalized normal-ranking experiment; no further retry on failure/criterion miss.
Allowed: tools/experiments/surface-global-rank-uppernormal-20261108/{worker,objective,metrics,armijo_direction,checks}.py; this task; docs/collaboration/reports/surface-global-rank-uppernormal-20261108.md; ignored artifacts/surface-global-rank-uppernormal-20261108/ and common runner outputs.
Forbidden: prior source/records/labels/production/progress criteria and other tasks.
Single change: remove -tau*log(valid_count) only from normal ranking logit; tau0.1 fixed. Positive rankmax/outputmax/basebagloss/linearhead/mask/mass/L2/init/seed/labels/folds/frozenbackbone/input448 unchanged. Relativecurvature/alignment0.01/Armijo/duplicateguard/checkpoint/ULPlog unchanged.
Criteria: finalgradient<=1e-5,internaltarget1e-7;FN<=67/370,FP<=112/1406,AUCdelta>=0.03 AND pairedphoto95%lower>0 allAND. Same original completed revised baseline. Normalized completed candidate is contextual secondary reference only. Strict1000iterations/1250total evaluations per fold inclinitial/noextra final evaluation. No tau/threshold search/retry.
Structure: objective3functions,direction1,metrics4,worker0,checks3. worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss4transitions; worker→fit→direction2. No callbacks/recursion.
Checks: explicit unnormalized objective/autograd comparison, masked upper bound, exacttau*logcount difference, invalidpaddinggradient0/continuous switch/positivehardmaxunchanged; inheriteddirection/history20/Armijo/convergence/duplicate/budget1250/relativegate/alignmentstatefixtures. Compile/AST/diffcheck; runneractualimport/inputSHA/rows;HTML/open/render status.
Snapshots: newfilesbaseline=null, originalobjectivebefore.py saved; actual imported source hashes also frozen.
Risk: count-dependent upper bound may overweight bags with more valid patches and stronger normal pressure may increase FN. Smoothing vs outputmax differs though upper bound controls local score. No guaranteed AUC/FPR gain or independent generalization.
HTML: artifacts/surface-global-rank-uppernormal-20261108/report.html; completed run actual204photos/1776truth+scores; failure marked baseline only.
Rollback: revert newsource/docs only, retainrecords/snapshots/models/logs/checkpoints; productionunchanged.

Handoff: source989d618; artifacts/experiments/20261107T155555-84dbfe36/record.json completed, acceptancefalse/evaluationcriterionfalse.5foldconverged,FN55/370,FP177/1406,AUC0.92570067 delta+0.00905002/CI[0.00452131,0.01392209].FPcap/AUCdeltafail;noadoption/noretry. HTML204photos1776zonesverified.

HTML open exit0: 열기 요청 성공, 실제 렌더 미확인. git diff --check 통과.
