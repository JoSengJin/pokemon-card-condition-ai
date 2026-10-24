"""Bounded model context assembled from frozen experiment evidence."""
import ast
from pathlib import Path
from .cross_review_auto_contract import CODEX_CONTEXT_VERSION
from .cross_review_auto_sources import review_rules, source_context, verify_sources
from .experiment_record import read, sha


def review_context(root, folder, phase, payload):
    root = root.resolve()
    packet = read(folder / 'packet.json')
    from .cross_review_evidence import expand_evidence,compact_evidence
    packet['evidence']=expand_evidence(packet['evidence'])
    verify_sources(root, packet)
    rules = root / 'AGENTS.md'
    context = dict(payload, context_version=CODEX_CONTEXT_VERSION,
                   project_rules=review_rules(rules),
                   project_rules_source=dict(path='AGENTS.md',sha256=sha(rules)) if rules.exists() else None,
                   source_context=source_context(root,packet,payload.get('allowed_files') if phase=='implement' else None))
    from .cross_review_contract import shared_core
    context['shared_core']=shared_core(root,folder,packet)
    context['baseline_training_contract']=context['shared_core']['baseline_training_contract']
    from .cross_review_contract import registered_evidence
    registered=registered_evidence(root,packet)
    context['valid_evidence_ids']=sorted(registered)
    if phase=='correct' and payload.get('flow_role')=='advocate':
        cited={v['path'] for v in payload.get('response',{}).get('code_checks',[])}
        if cited:
            omitted=[v['path'] for v in context['source_context']['sources'] if v['path'] not in cited]
            context['source_context']['sources']=[v for v in context['source_context']['sources'] if v['path'] in cited]
            context['source_context']['omitted_sources']+=omitted
            context['source_context']['selection']='Cited complete definitions only; omitted code cannot be cited.'
            checks=payload['response']['code_checks']
            for source in context['source_context']['sources']:
                text=source['excerpt'];tree=ast.parse(text)
                definitions=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))]
                quotes=[v['quote'] for v in checks if v['path']==source['path']]
                lines=text.splitlines(True)
                chosen={n.name for n in definitions if any(q in ''.join(lines[n.lineno-1:n.end_lineno]) for q in quotes)}
                if chosen and all(any(q in ''.join(lines[n.lineno-1:n.end_lineno]) for n in definitions if n.name in chosen) for q in quotes):
                    while True:
                        dependencies={v.id for n in definitions if n.name in chosen for v in ast.walk(n) if isinstance(v,ast.Name)}
                        expanded=chosen|{n.name for n in definitions if n.name in dependencies}
                        if expanded==chosen:break
                        chosen=expanded
                    kept=[n for n in tree.body if n not in definitions or n.name in chosen]
                    source['excerpt']='\n'.join(''.join(lines[n.lineno-1:n.end_lineno]) for n in kept)
                    source['omitted_definitions']+= [n.name for n in definitions if n.name not in chosen]
            context['response']=dict(context['response'])
            context['response']['code_check_paths']=[v['path'] for v in context['response'].pop('code_checks')]
            context['response']['experiment']=dict(context['response']['experiment'])
            context['response']['experiment'].pop('success_criterion',None)
            context['response']['experiment'].pop('failure_criterion',None)
            context['response']['criteria_reference']='Keep fixed acceptance, required cohorts and actual-point guard; no success claim.'
            assessment=context['response'].get('debate_assessment')
            if isinstance(assessment,dict):
                # Pre-judge ratings are fixed zeros; keep only the advocate's own issues.
                context['response']['debate_assessment']={k:v for k,v in assessment.items() if k not in ('advocate','skeptic')}

    if packet.get('execution_inputs'):
        context['execution_inputs'] = packet['execution_inputs']
    else:
        from .experiment_record import project_file
        plan = read(project_file(root, str(Path(packet['latest_result']).parent / 'plan.json')))
        context['execution_inputs'] = {k:plan[k] for k in ('feature_sources','input_sha256','execution_inputs') if k in plan}
    if phase in ('verify','correct'):
        context.pop('packet_file',None)
        context.pop('failed_hypotheses',None)  # Included once inside evidence below.
        context['evidence'] = {k:packet[k] for k in ('stagnation_reason','error_cases','same_evaluation_metrics','failed_hypotheses','evidence')}
        context['evidence']['evidence']=registered
        context['evidence']['failed_executions'] = packet.get('failed_executions', {})
        context['evidence']['completed_diagnostics'] = packet.get('completed_diagnostics', {})
        if packet.get('execution_inputs'):
            # Cache hashes/schema are needed by implementation, not duplicated in the verdict input.
            context['execution_inputs'] = {k:v for k,v in packet['execution_inputs'].items()
                if k in ('fixed_ensemble','experiment_constraints','clarification','source_context_note')}
        if context['source_context']['sources']:
            code = context['evidence']['evidence'].get('related_code', {})
            if isinstance(code, dict) and isinstance(code.get('summary'), dict):
                code['summary'].pop('excerpt', None)  # Measurement diff; actual fitter/model sources are inline.
            summary = context['evidence']['evidence'].get('latest_plan',{}).get('summary',{})
            # Parent verifies the frozen references. Verdict needs cohort IDs and exact gates,
            # not the same source file path repeated for every inherited guard.
            if isinstance(summary.get('required_cohorts'),list):
                summary['required_cohorts']=[{k:v for k,v in cohort.items() if k!='reference_result'}
                    for cohort in summary['required_cohorts']]
            for key in ('change',):
                if isinstance(summary.get(key),str) and len(summary[key])>400:
                    summary[key]=summary[key][:400]+' [요약 생략: 전체 worker·수치 기준 참조]'
            for key,value in context['evidence']['evidence'].items():
                if key.startswith('failed_execution_') and isinstance(value,dict):
                    value['summary']={k:v for k,v in value.get('summary',{}).items()
                        if k not in ('change','hypothesis')}
                if key.startswith('failed_') and not key.startswith('failed_execution_') and isinstance(value,dict):
                    comparison=value.get('summary',{}).get('comparison',{})
                    if comparison:
                        value['summary']['comparison']={k:v for k,v in comparison.items()
                            if k in ('before','after','new_misses','new_false_positives','recovered')}
            if 'change' in summary:
                summary.pop('change')
                summary['change_reference']='linked complete worker / frozen plan path and SHA'
            latest=context['evidence']['evidence'].get('latest_result',{}).get('summary',{})
            latest.pop('comparison',None)
            latest.pop('point_comparison',None)
            latest['metrics_reference']='same_evaluation_metrics.latest_experiment / latest_experiment_actual_points'
        # The program verifies the frozen packet's measurement hashes; only code needs LLM SHA citations.
        for value in context['evidence']['evidence'].values():
            if isinstance(value,dict) and 'summary' in value:
                value.pop('path',None);value.pop('sha256',None)
                points=value['summary'].get('point_comparison')
                if isinstance(points,dict):
                    value['summary']['point_comparison']={k:v for k,v in points.items() if k in ('before','after','new_misses','new_false_positives')}
        context['execution_inputs'] = {k:v for k,v in context.get('execution_inputs',{}).items() if k!='input_sha256'}
        if phase=='correct' and context.get('flow_role')!='advocate':
            context['response']={k:v for k,v in context.get('response',{}).items()
                if k in ('hypothesis_id','cause','smallest_experiment')}
            if 'correction' in context:
                context['correction']=dict(context['correction'])
                rationale=context['correction'].get('previous_rationale')
                if isinstance(rationale,str) and len(rationale)>180:
                    context['correction']['previous_rationale']=rationale[:180]+' [전체 판정은 호출 기록에 보존]'
    else:
        context['worker_contract'] = dict(reference_env='CARD_CONDITION_EXPERIMENT_REFERENCE',output_env='CARD_CONDITION_EXPERIMENT_DIR',
            output_file='observations.json',keys=['rows','scores','point_ids','point_scores','required_cohorts'],
            project_root=str(root),reference_keys=['rows','before_scores','point_ids','point_scores','source','source_sha256','required_cohorts'],
            parameter_source='CARD_CONDITION_EXPERIMENT_DIR/plan.json: experiment_parameter.value. 선택된 수치 그대로 사용, 배율 탐색 금지.',
            rules='고정 평가 rows/정답/순서/point_ids 보존. 실제 예측만 저장. 학습·평가 그룹 분리. 기존 사람점 보호. 성공 여부는 공통 실행기가 계산.')
        context['reference_summary'] = packet['same_evaluation_metrics']
        context['worker_contract']['required_cohorts'] = ('reference.required_cohorts가 있으면 각 id/rows/point_ids를 그대로 유지하고 '
            '동일 후보로 실제 평가한 scores/point_scores를 observations.required_cohorts 목록에 저장한다. '
            '기준 점수를 후보 예측으로 복사하거나 필수 평가를 생략하지 않는다. 없으면 이 출력은 생략한다.')
        from .cross_review_execution import VERSION as EXECUTION_VERSION
        setting=root/'trusted-experiment.json'
        context['isolated_execution']=dict(adapter=EXECUTION_VERSION,
            training_input_env='CARD_CONDITION_TRAIN_INPUT',model_output_env='CARD_CONDITION_MODEL_OUTPUT',
            parameter_env='CARD_CONDITION_EXPERIMENT_PARAMETER',project_root_env='CARD_CONDITION_PROJECT_ROOT',
            training_input_keys=['features','masks','targets','point_tokens','weights','ids'],
            model_output=dict(coef='finite float list, feature dimension',bias='finite scalar'),
            training_diagnostics='Bootstrap records LBFGS iterations, final max_gradient and converged in training-diagnostics.json on success/failure. No worker reporting required. Process observations, not independently verified; missing values remain null.',
            trainer_sources=read(setting).get('trainer_sources',[]) if setting.exists() else [],
            rules='Worker executes separately for each fixed fold. Only training input is available; no evaluation data, truth, scores or network. Export numeric model.json only. Do not evaluate or write observations. Import candidate model code from project root; use provided weights. No batch/scale search.')
        context.pop('worker_contract',None)
        context.pop('contract',None)
    if phase in ('verify','correct'):
        setting=root/'trusted-experiment.json'
        importable=set(read(setting).get('trainer_sources',[])) if setting.exists() else set()
        for source in context['source_context']['sources']:
            if source['path'] in importable:source['worker_importable']=True  # Copied into isolated execution.
        transport=expand_evidence(read(folder/'packet.json')['evidence'],decode_tables=False)
        for key,value in context['evidence']['evidence'].items():
            if isinstance(value,dict) and 'required_cohorts' in value.get('summary',{}):
                original=transport.get(key,{}).get('summary',{})
                if isinstance(original.get('required_cohorts'),dict) and original['required_cohorts'].get('format')=='cohort_table_v1':
                    value['summary']['required_cohorts']=original['required_cohorts']
        context['evidence']['evidence_reference_format']='Resolve $ref JSON Pointers from document root. Cohort tables use explicit schema columns; counts and criteria are exact.'
    context['context_reference_root']='document'
    context=compact_evidence(context,document=True)
    return context
