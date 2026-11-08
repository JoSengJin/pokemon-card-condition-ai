# surface-patch-cause-20261108
owner: Codex
status: completed
base_sha: f4b3f16
branch: main / serial default checkout
Scope: saved-evidence causal narrowing and next single-change proposal only; no training/inference/optimizer/candidate execution/source modification.
Allowed: this task and docs/collaboration/reports/surface-patch-cause-20261108.md; ignored artifacts/surface-patch-cause-20261108/{analysis.json,report.html}.
Input: record20261107T225236-81b0b12a patch-evidence.json and patch-logits.pt, current pairmix objective/worker, saved training diagnostics. Exact source/input hashes in analysis.json.
Result: 172IDs aligned; commonFP160 stabletop142 across3candidates, newFN6 stabletop5 versus baseline, newFP17 stabletop13; stored-logit medianpatch shift negative but oldpeak shift positive for newFP. Formula identity and uniform-bias invariance synthetic checks passed. Causation via training pairs and visual category attribution remain unverified.
Proposal: LME half changes from row-LME mean to global allpair LME; arithmetic half/allpairs/tau0.1/output/truth/folds/optimizer/4transitions/1000iterations/1250evaluations/gradient1e-5 and original FN/FP/AUC/bootstrap gates unchanged. Not implemented or run.
HTML: artifacts/surface-patch-cause-20261108/report.html; links prior local overlays/CSV. Prior file URL policy denial respected; no same-action retry, open/render not executed. Four original photos inspected via view_image only; no human labels changed.
Checks/handoff: docs plus stored-data analysis only; model/worker source unchanged. Risk: error-selection bias, lack of train-contribution evidence, globalLME may amplify lowpositive outliers and leave commonFP intact. Rollback: revert docs commit only, preserve evidence.
