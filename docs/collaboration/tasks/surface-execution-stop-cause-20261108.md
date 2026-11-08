# surface-execution-stop-cause-20261108
owner: Codex
status: completed_diagnosis_only
base_sha: 70d7ac9; previous outcome docs were staged and preserved
Scope: execution-code/log/abort-record analysis only; no experiment, inference, source patch or process restart.
Allowed: this task; docs/collaboration/reports/surface-execution-stop-cause-20261108.md; ignored artifacts/surface-execution-stop-cause-20261108/{timeline.json,report.html}. Finish prior staged interrupted-outcome docs without changing sources/results.
Evidence: own actual rollout lines4180/4183/4184/4211/4217, interrupted/orphaned experiment20261108T002449-6e4ad830, experiment_record.py _run/records/main, worker, existing tests. Turncancel09:27:01.575KST and commandfailed09:27:01.584KST; tool exit-1 not interpreted as OSsignal. Parent/child absent, no final supervisor save. OS PID/timefilterlog0matches; no proof excluding OOM.
Proposal: standard common-runner command inherits unbuffered stdout/stderr redirected to unique local console.log. No code patch/functions/call layers. Model4transitionpath/criteria/1000iter/1250eval unchanged. Logging improves durability, not immunity to external cancellation. Not executed.
Checks: read-only source/event/OSlog inspection; sanitized timeline; source/record hashes, docs diff. No claimed test reruns or modelqualityresult. HTML localreport created, opening/render not performed under current tool/policy restriction.
Risk: exact OS signal and sender remain unknown; external cancellation may recur; logs can still lose buffered tail. Rollback: docs-only revert; preserve unique evidence.
