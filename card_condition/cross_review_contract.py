"""Frozen common facts and deterministic history classification, not model judgments."""
from .cross_review import digest
from .experiment_record import read,save,sha,project_file


def baseline_contract(root):
    root=root.resolve()
    policy=root/'trusted-experiment.json'
    contract=read(policy).get('baseline_training_contract',{}) if policy.exists() else {}
    if contract:
        source=project_file(root,contract['source'])
        if sha(source)!=contract['source_sha256'] or contract['quote'] not in source.read_text():
            raise ValueError('Shared baseline source changed')
    return contract


def registered_evidence(root,packet):
    from .cross_review_evidence import expand_evidence
    evidence=expand_evidence(packet['evidence'])
    contract=baseline_contract(root)
    if contract:
        entry=dict(path=contract['source'],sha256=contract['source_sha256'],summary=contract)
        previous=evidence.get('baseline_training_contract')
        if previous is not None and previous!=entry:raise ValueError('Conflicting baseline evidence registration')
        evidence['baseline_training_contract']=entry
    return evidence


def shared_core(root,folder,packet):
    contract=baseline_contract(root)
    from .cross_review_evidence import expand_evidence
    core=dict(version='shared-core-v3',execution_boundary=dict(worker='train only; output coef,bias',evaluator='fixed FP/FN, point and cohort guards; writes observations.json',diagnostics='bootstrap records LBFGS final gradient, optimizer iterations and convergence in training-diagnostics.json; process observations are not independent performance evidence; unknown stays null'),baseline_training_contract=contract,
        latest_result=packet['latest_result'])
    evidence_hash=digest(expand_evidence(packet['evidence']))
    path=folder/'shared-core.json'
    if path.exists():
        frozen=read(path)
        if frozen.get('core')!=core or frozen.get('sha256')!=digest(core) or frozen.get('evidence_sha256')!=evidence_hash:raise ValueError('Frozen shared core changed')
    else:save(path,dict(core=core,sha256=digest(core),evidence_sha256=evidence_hash))
    return core


def classify_history(packet,verdict):
    reported=verdict.get('failed_hypotheses_checked')
    if not isinstance(reported,list) or any(not isinstance(v,str) for v in reported):raise ValueError('Invalid failure history list')
    expected=set(packet['failed_hypotheses']);extras=set(reported)-expected
    execution_ids=set(packet.get('failed_executions',{}))
    missing=expected-set(reported);unknown=extras-execution_ids
    if missing or unknown:raise ValueError('Failure history mismatch; missing='+','.join(sorted(missing))+'; unexpected='+','.join(sorted(unknown)))
    canonical=sorted(expected)
    warning=dict(kind='execution_ids_in_hypothesis_list',reported_ids=list(reported),
        execution_failure_ids=sorted(extras),canonical_hypothesis_ids=canonical,
        resolution='frozen_registry_classification_only',resolved=True) if extras else None
    return dict(verdict,failed_hypotheses_checked=canonical),warning


ALIAS_TABLES=('failed_hypotheses','failed_executions','completed_diagnostics')


def alias_to_hypothesis(packet):
    """Evidence-registry keys (failed_N, failed_execution_N, completed_diagnostic_N) -> real hypothesis ids.

    The model sees both namespaces: evidence keys in valid_evidence_ids and real ids in the history
    tables. The program owns this mapping, so the model is not asked to translate between them.
    """
    mapping={}
    for table in ALIAS_TABLES:
        for hypothesis,keys in (packet.get(table) or {}).items():
            for key in keys if isinstance(keys,list) else ():
                if isinstance(key,str):mapping[key]=hypothesis
    return mapping


def canonicalize_verdict(packet,verdict,critiques=()):
    """Normalize program-owned bookkeeping only; never the decision, experiment, criteria or citations.

    - failed_hypotheses_checked / review_claims.completed_diagnostic_ids: evidence alias -> real id.
    - critique_responses: must be empty while no critique exists (the program knows this, not the model).
    Returns (verdict, notes). Every change is listed in notes so it can be audited; the raw model
    response stays untouched in the Codex call journal.
    """
    if not isinstance(verdict,dict):return verdict,[]
    value=dict(verdict);notes=[];aliases=alias_to_hypothesis(packet)

    def resolve(items,field):
        if not isinstance(items,list) or any(not isinstance(v,str) for v in items):return items
        mapped=list(dict.fromkeys(aliases.get(v,v) for v in items))
        if mapped!=items:notes.append(dict(field=field,kind='evidence_alias_to_hypothesis_id',before=items,after=mapped))
        return mapped

    if 'failed_hypotheses_checked' in value:
        value['failed_hypotheses_checked']=resolve(value['failed_hypotheses_checked'],'failed_hypotheses_checked')
    claims=value.get('review_claims')
    if isinstance(claims,dict) and 'completed_diagnostic_ids' in claims:
        value['review_claims']=dict(claims,completed_diagnostic_ids=resolve(claims['completed_diagnostic_ids'],'review_claims.completed_diagnostic_ids'))
    if not critiques and value.get('critique_responses'):
        notes.append(dict(field='critique_responses',kind='dropped_no_critique_exists',count=len(value['critique_responses'])))
        value['critique_responses']=[]
    return value,notes
