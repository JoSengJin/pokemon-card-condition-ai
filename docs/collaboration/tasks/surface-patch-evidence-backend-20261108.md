# surface-patch-evidence-backend-20261108
owner: Codex
status: implementing
base_sha: 951654f
branch: main, serial default checkout
Goal: finish authorized frozen-model diagnosis with original backend matched; first2failed score replay records retained, no training/no acceptance relaxation.
Allowed: tools/diagnostics/surface-patch-evidence-backend-20261108/{worker,patch_evidence,patch_geometry,patch_report,checks}.py; this task; prior task status; docs/collaboration/reports/surface-patch-evidence-20261108.md; ignored artifacts/surface-patch-evidence-backend-20261108/ and runner outputs.
Evidence: saved baseline evaluation device=mps, arithmetic/LME/mixture device=cpu. CPUselectedfeatures replay3CPUheads exactly; originalbaselineCPUreplay difference1.49e-6 persisted despite fullbatch. Backend mismatch confirmed in source metadata; batch hypothesis refuted for this discrepancy.
Contract: baseline172MPSfeatures via original cached backbone/weights;3candidateCPUfeatures reuse hashed frozenfeatures from failedv2. Same masks/crops/labels/folds/head scores. Score formula/API unchanged. Original fullfold workspace scoring maintained. Existing evidence/overlay/CSV contract unchanged. No optimizer/training calls.
Criteria: unchanged exactsyntheticlegacy score equality and real replay<=1e-6 plus predictionsunchanged across4models. Selectederrorcohort diagnosticacceptance only, not quality gate or improvement claim. Originalmodelqualitycriteria untouched.
Structure: worker0functions/scorer1/geometry1/report1/checks0. Newscoring/geometry/render1transition; existingfeaturepath3transitions; trainingpath4untouched. No newrecursive/callbacklayer.
Checks: all originalscore/geometry/HTML/workspace/AST checks, originalbackend metadata hashed, cachedCPUfeatures IDs/masks/hash, real all4model replay; open/render distinction.
HTML: artifacts/experiments/<record>/report.html; summarylinks artifactssurface-patch-evidence-backend-20261108/report.html aftercompletion, localphoto paths retained.
Risk: sourcebackend matters for float32 reproducibility. Matchingoriginalbackends preserves model histories but is not evidence that CPU/MPS differences caused prior quality changes; no new quality comparison or retraining.
Rollback: revert newsource/docs only; preservefailedrecords/source/featurecache and finaldiagnosis/logits; originalmodels/labels/scores unchanged.
