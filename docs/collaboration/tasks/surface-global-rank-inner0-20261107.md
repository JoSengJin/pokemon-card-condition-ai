# surface-global-rank-inner0-20261107
owner: Codex
status: completed_experiment_failed
base_sha: 4a00b38
branch: main, serial basic-checkout execution
Goal: exactly one authorized retry with internal line-search tolerance0 and existing-evaluation logs; no subsequent retry.
Allowed: tools/experiments/surface-global-rank-inner0-20261107/{worker,objective,metrics}.py; this task; docs/collaboration/reports/surface-global-rank-inner0-20261107.md; ignored artifacts/surface-global-rank-inner0-20261107/ and runner outputs.
Forbidden: prior records/source/labels/production/progress criteria, other tasks.
Contract: internal strong_wolfe tolerance_change1e-9→0 only. Experiment-process-only wrapper restored in finally. Log start/trial/return step/loss/direction derivative/evaluation counts using already computed values, no diagnostic evaluations. Closure guard enforces strict1250 calls including existing final verification, max_iter1000. Finalgradient<=1e-5/tolerance_grad1e-7/outertolerance0, sameamax/objective/seed/folds/labels/mass/L2/init/backbone. Same completed baseline FN67/FP201/AUC0.91665065; failed runs not reference. FN<=67,FP<=112,AUC+0.03 AND photo-bootstrap95%lower>0 allAND.
Structure: objective6functions incl closure/traced_wolfe/observed_trial, metrics4, worker1lambda. tracing only new path traced_wolfe→original_strong_wolfe→observed_trial→existing obj_func→existing directional_evaluate→closure includes pre-existing optimizer callback path; wrapper adds2 transitions. Full framework optimizer path exceeds4, disclosed, no structural compliance claim for that pre-existing framework path. Experiment diagnostics do not add mathematical functions/layers to model path closure→detail_bag_loss→point_bag_loss.
Checks: compile, synthetic controlled fit/trial log/count/restoration and AST function counts, source diff; common-runner frozen SHA/row validation; HTML/open request.
Risk: private PyTorch API wrapper is restricted to this isolated serial worker/version; zero tolerance can consume entire budget; guard terminates before1251st closure. No smoothing/threshold relaxation or new trial direction.
HTML: artifacts/surface-global-rank-inner0-20261107/report.html. Failed run uses clearly marked historical baseline photos; complete run shows actual both scores.
Rollback: original_wolfe restored in finally; no installed package/production change. Revert new source/docs only, retain records.

Handoff: source ddbac13; artifacts/experiments/20261107T094656-f5f8ae4d/record.json failed; fold0,iteration159,actual1250evaluations,noOOF/noRetry. Originalfunctionrestored. HTMLgenerated.

HTML open exit0: 열기 요청 성공, 실제 렌더 미확인. git diff --check 통과.
