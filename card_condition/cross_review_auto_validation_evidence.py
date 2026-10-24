"""Verdict evidence, failure-history, and code-citation checks."""
from .cross_review_auto_sources import model_file, provided_code_sources, source_context
from .experiment_record import read, sha


def check_completed_diagnostics(root,result,verdict,require_parameter,allowed):
        if require_parameter or 'review_claims' in verdict:
            claims=verdict.get('review_claims')
            if set(claims['completed_diagnostic_ids'])!=set(result['packet'].get('completed_diagnostics',{})):
                raise ValueError('Completed diagnostic history was omitted or misstated; expected='+','.join(sorted(result['packet'].get('completed_diagnostics',{}))))


def check_missing_evidence(root,result,verdict,require_parameter,allowed):
        if require_parameter or 'review_claims' in verdict:
            claims=verdict.get('review_claims')
            if set(claims['missing_evidence_ids']) & (set(allowed)|set(result['packet'].get('completed_diagnostics',{}))):
                raise ValueError('Claimed missing evidence is already supplied')


def check_evidence_ids(root,result,verdict,require_parameter,allowed):
        if verdict['action'] in ('select','second') or require_parameter:
            refs = verdict['evidence_ids']
            if not refs or any(ref not in allowed for ref in refs):
                raise ValueError('Codex cited unknown evidence; unexpected='+','.join(sorted(set(refs)-set(allowed)))+'; allowed='+','.join(sorted(allowed)))


def check_failure_history(root,result,verdict,require_parameter,allowed):
        if verdict['action'] in ('select','second') or require_parameter:
            if set(verdict['failed_hypotheses_checked']) != set(result['packet']['failed_hypotheses']):
                expected=set(result['packet']['failed_hypotheses']);checked_ids=set(verdict['failed_hypotheses_checked'])
                raise ValueError('Failure history mismatch; missing='+','.join(sorted(expected-checked_ids))+'; unexpected='+','.join(sorted(checked_ids-expected)))


def check_code_sources(root,result,verdict,require_parameter,allowed):
        if verdict['action'] in ('select','second') or require_parameter:
            checked = set()
            from .experiment_record import project_file
            contract=read(root/'trusted-experiment.json').get('baseline_training_contract',{}) if (root/'trusted-experiment.json').exists() else {}
            linked = {s['path'] for s in provided_code_sources(dict(source_context=source_context(root,result['packet']),baseline_training_contract=contract))}
            for check in verdict['code_checks']:
                if check['path'] not in linked:
                    raise ValueError('Code citation was not provided in the frozen context')
                file = project_file(root, check['path'])
                if (sha(file) != check['sha256'] or len(check['quote'].strip()) < 10
                        or check['quote'] not in file.read_text() or not check['conclusion'].strip()):
                    raise ValueError('Code citation does not match actual source')
                checked.add(str(file.relative_to(root)))
            for name in verdict['implementation_files']:
                try:model_file(root, name)  # Read-only evidence never becomes editable through a citation.
                except ValueError:
                    # List error only: a worker-only experiment may still be feasible.
                    raise ValueError('Not an editable model source: '+name+'. New worker is separate output: omit it; '
                        '[] is valid if worker passes experiment_parameter to worker_importable code') from None
            if (verdict['action'] in ('select','second') and not checked) or not set(verdict['implementation_files']).issubset(checked):
                raise ValueError('Every editable source must be checked')
