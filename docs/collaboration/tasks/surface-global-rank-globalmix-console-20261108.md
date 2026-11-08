# surface-global-rank-globalmix-console-20261108
owner: Codex
status: completed_criteria_not_met
base_sha: 37f3abc
branch: main / serial default checkout
Goal: synthetic checks then1 newly-authorized logged experiment; no retry after failure/interruption/gate miss.
Allowed: tools/experiments/surface-global-rank-globalmix-console-20261108/{worker,objective,metrics,armijo_direction,checks,checks_logging}.py; this task; docs/collaboration/reports/surface-global-rank-globalmix-console-20261108.md; ignored artifacts/surface-global-rank-globalmix-console-20261108/ and commonrunner records.
Single change: execution output retention with PYTHONUNBUFFERED=1, unique noclobber console.log for stdout/stderr inherited by supervisor+worker. Model objective/direction/metrics byte-identical to globalmix candidate. Only administrative worker hypothesis/path changes. All prior sources/records preserved.
Frozen: arithmetichalf/globalLMEhalf/alltrainpairs/tau0.1/positive+outputmax/threshold/truth/folds/mass/L2/backbone/seed/init/CPU; relativecurvature/alignment0.01/Armijo/duplicateguard. Gradient<=1e-5/internal1e-7;max1000iterations/max1250evaluations inclinitial per fit. FN<=67/370,FP<=112/1406,AUCdelta>=0.03,pairedphoto95%lower>0 allAND; no search/retry.
Structure: worker0/objective3/direction1/metrics4/checks3/loggingchecks0 functions, each<=7. Worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss4transitions, direction2 unchanged. Shell env/redirection adds no projectfunction layer.
Checks: synthetic parent+child unbuffered stdout/stderr live before exit; inherited commonrunner SIGTERM/orphan mock tests; inherited model globalLME/gradient/Armijo/budget etc; byte parity/compile/AST/inputhash. Actualrecord/log/endstate, folds/trialcounts; HTML.
Risk: persistent log is not survival protection against external cancellation; buffered OS tail may be lost. Repeated development CV not independent. No operational adoption.
HTML: artifacts/surface-global-rank-globalmix-console-20261108/report.html; actual completed scores and frozen truth or explicit baselineonly failure. Opening/render limitations recorded.
Rollback: revert newsource/docs only; preserve unique console/record/snapshots/models/traces; production/labels/folds unchanged.

Handoff: sourceb6f4f6c; record20261108T133726-586d9cdd completed/exit0, acceptancefalse/evaluationcriterionfalse.5foldconverged within1000/1250; FN51/370 FP179/1406 AUC0.930927300 delta+0.014276652/CI[0.007979489,0.021023437]. FPcap/AUCdelta fail; noadoption/noretry. Unique console retained feature/5fold/evaluation/supervisor-completion; sha inoutcome.json. Fixedinputs100 unchanged, trialcounts checked. HTML204photos1776truthzones andcomparison.csv1776rows verified; opening/render not performed under currenttool/policy limits.
