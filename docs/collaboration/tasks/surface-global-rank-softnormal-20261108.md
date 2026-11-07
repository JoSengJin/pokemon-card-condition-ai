# surface-global-rank-softnormal-20261108
owner: Codex
status: implementing
base_sha: 8f15533
branch: main, serial basic-checkout experiment
Goal: synthetic checks then exactly one negative-ranking-pooling experiment; failure reports only, no extra retry.
Allowed: tools/experiments/surface-global-rank-softnormal-20261108/{worker,objective,metrics,armijo_direction,checks}.py; this task; docs/collaboration/reports/surface-global-rank-softnormal-20261108.md; ignored artifacts/surface-global-rank-softnormal-20261108/ and common runner outputs.
Forbidden: prior sources/records/labels/production/progress criteria and other tasks.
Single change: negative logit in ranking loss becomes tau0.1*(logsumexp(valid_logits/tau)-log(valid_patch_count)); positive ranking logit remains maskedmax. Output scoring remains prior.sw.score hardmax. Original base bag losses,linearhead,mask,mass,L2,init,seed,labels,folds,frozenbackbone/input448 unchanged. Relativecurvature/0.01alignmentguard/Armijo/duplicateguard/checkpoint/logging unchanged.
Criteria: finalgradient<=1e-5,internaltarget1e-7; FN<=67/370,FP<=112/1406,AUC+0.03 AND pairedphoto95%lower>0 allAND. Same original completed revised baseline, previous failed runs not performance reference. Strict1000iterations/1250total evaluations per fold includinginitial, no final extra reevaluation. Global rankcoefficient1,tau0.1fixed, no search/retry.
Structure: objective3functions,direction1,metrics4,worker0,checks3. worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss4transitions; worker→fit→direction2. Poolinginline, no callback/recursion.
Checks: explicit new objective/gradient against independent per-bag normalized expression; normalizedzeros across1/2/3patch counts; invalidmaskgradient0; normal switch gradientcontinuity; unchangedpositive hardmax. Existing35smoothdirection/history20,budget1250,Armijo,duplicates,relativegate,alignmentrestart fixture tests retained. Compile/AST/diffcheck,runner immutable actualimport/source/input SHA/1776rows,HTML/open/render distinction.
Snapshots: newfilesbaseline=null; originalobjective saved before.py. Source changes only under develop lock.
Risk: normalized smoothing can dilute localized normal-bag signals and changes training-vs-output pooling; positive hardmax nonsmoothness remains. This is changed training objective, not optimizer fix or independent generalization evidence.
HTML: artifacts/surface-global-rank-softnormal-20261108/report.html; completed comparison shows actual scores/photos; failure shows clearly historical baseline photos only.
Rollback: revert new source/docs only; preserve record/snapshots/checkpoints/logs, no production changes.
