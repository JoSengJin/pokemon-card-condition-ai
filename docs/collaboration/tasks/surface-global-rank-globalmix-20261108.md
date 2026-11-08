# surface-global-rank-globalmix-20261108
owner: Codex
status: completed_experiment_interrupted
base_sha: 83a1e76
branch: main / serial default checkout
Goal: synthetic checks then exactly1 authorized experiment; no retries after failure or quality miss.
Allowed: tools/experiments/surface-global-rank-globalmix-20261108/{worker,objective,metrics,armijo_direction,checks}.py; this task; docs/collaboration/reports/surface-global-rank-globalmix-20261108.md; ignored artifacts/surface-global-rank-globalmix-20261108/ and commonrunner records.
Single variable: LME half row-LME mean to global all-trainingpair LME. Arithmetic0.5/LME0.5/ranktotal1/allpairs/tau0.1/positive max/output/threshold/truth/folds/basebag/mass/L2/backbone/init/seed/optimizer unchanged. No OOF-ID weighting/selection. Old sources/records untouched.
Criteria: finalgradient<=1e-5,internal1e-7;fitmax1000iterations/1250evaluations inclinitial/noextra finalcall;FN<=67/370,FP<=112/1406,AUCdelta>=0.03 AND pairedphoto95%lower>0. AllAND;no threshold search/retry. Original baseline20261106T210640-0eb1bdc0; previousmixture contextonly.
Structure: objective3,direction1,metrics4,worker0,checks3functions. worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss4transitions;worker→fit→direction2. Inline reduction only; no newcallback/recursive path.
Checks: independent algebraic loss/gradient;globalallpairvalue/gradient/floor,axis permutation,repetition normalization,singleton,finite extremes; inherited real syntheticfit/Armijo/duplicate/budget1250/relativecurvature/alignment/normalupper/positivehardmax. Compile/AST/input hashes; actual folds/trials/evaluationcounts; HTML/open/render status.
HTML: artifacts/surface-global-rank-globalmix-20261108/report.html with actual photos1776zones/204groups on completed run or explicit baselineonly on failure.
Risk: hard-positive outliers may dominate LME half, convergence or normal falsepeaks may worsen. Repeated development CV, not independent. No operational adoption authorized by criterion completion alone.
Rollback: revert newsource/docs only; preserve record/snapshot/models/traces/checkpoint. Production/labels/folds unchanged.

Handoff: source70d7ac9; record20261108T002449-6e4ad830 interrupted/orphaned_process after waiting connection interruption; parent57813/child57817 absent, exact termination cause/exitcode unknown. LaststageCPUfeatures1776; completedfits0; noactualtrainingdiagnostics/models/observations/evaluation/result. CandidateFN/FP/AUC/gates unknown. No retry/no adoption. Inputhashes unchanged; syntheticpassed. HTML baselineonly204photos1776zones; opening/render not performed due prior fileprotocolpolicy denial/currentCUA unavailable.
