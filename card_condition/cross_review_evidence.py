"""Build bounded review evidence from saved project experiments, never from labels guessed by a model."""
import ast
import hashlib
import json
from pathlib import Path
import re

from .cross_review import digest, encoded
from .regression_audit import compare_predictions


def load(path):
    return json.loads(path.read_text())


def source(path, root):
    return {'path': str(path.relative_to(root)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def required_cohort_summary(result):
    return [dict(id=c['id'], comparison=c['comparison'], point_comparison=c.get('point_comparison'),
                 acceptance_passed=c['acceptance_passed'], acceptance=c['acceptance'],
                 errors=[dict(id=r['id'], target=r['target'], score=s,
                              kind='miss' if r['target'] else 'false_positive')
                         for r, s in zip(c['rows'], c['scores']) if int(s >= .5) != r['target']])
            for c in result.get('required_cohorts', [])]


def experiment(path):
    result = load(path)
    rows = result.get('rows')
    if not isinstance(rows, list) or not rows or not all(isinstance(r, dict) and 'target' in r and 'id' in r for r in rows):
        return None
    if 'runs' in result and 'reference' in result:
        before = result['reference']['scores']
        after = result['runs']['candidate']['scores']
    elif all(isinstance(result.get(k), list) for k in ('before_scores', 'scores')):
        before, after = result['before_scores'], result['scores']
    else:
        return None
    comparison = compare_predictions([r['target'] for r in rows], before, after)
    saved = (result['comparisons']['latest_reference']['crop'] if 'runs' in result
             else result.get('comparison'))
    if saved is not None and comparison != saved:
        raise ValueError('Saved experiment metrics do not match paired scores')
    if any(not r.get('group') or not r.get('image_sha256') or not r.get('box') for r in rows):
        raise ValueError('Missing group/image hash/box identity for paired evidence')
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate experiment row IDs')
    identity = [{k: r.get(k) for k in ('id', 'group', 'image_sha256', 'box', 'target', 'fold', 'profile', 'split')} for r in rows]
    return dict(path=path, result=result, rows=rows, before=before, after=after,
                comparison=comparison, cohort=digest(identity))


def latest_packet(root):
    from .experiment_record import records, verify, LatestExperimentUnavailable
    root = root.resolve()
    candidates = []
    dated_paths = []
    registered = records(root)
    common = {folder / 'result.json': (folder, record) for folder, record in registered}
    if registered and registered[0][1]['status'] != 'completed':
        folder, record = registered[0]
        raise LatestExperimentUnavailable('최신 공통 실험 상태: ' + record['status'] + '. 과거 결과로 대체하지 않습니다. 기록: ' + str(folder / 'record.json'))
    for folder, record in registered:
        if record['status'] == 'completed':
            verify(folder, record)
            dated_paths.append(((1, record['started_at']), 0, str(folder), folder / 'result.json'))
    for path in (root / 'artifacts').glob('*/result.json'):
        # Only dated experiment directories participate; review responses are not experiments.
        dates = re.findall(r'20\d{6}', path.parent.name)
        if dates and not path.parent.name.startswith(('cross-review-', 'manual-')):
            dated_paths.append(((0, max(dates)), path.stat().st_mtime_ns, str(path), path))
    for date, modified, name, path in sorted(dated_paths, reverse=True):
        try:
            result = experiment(path)
        except ValueError:
            if not candidates:
                raise  # Never replace an invalid latest result with an older experiment.
            continue  # Invalid historical metrics are not review evidence.
        if result:
            candidates.append((date, modified, name, result))
    if not candidates:
        raise ValueError('지원하는 최신 실험 결과가 없습니다. 예제 자료로 대체하지 않습니다.')
    candidates.sort(key=lambda item: item[:3], reverse=True)
    latest = candidates[0][3]
    path, rows = latest['path'], latest['rows']
    evidence, manifest = {}, []

    def add(name, file, summary):
        record = source(file, root)
        manifest.append(record)
        evidence[name] = dict(record, summary=summary)

    point_comparison = (latest['result'].get('point_comparison')
                        or latest['result'].get('comparisons', {}).get('latest_reference', {}).get('point'))
    add('latest_result', path, dict(comparison=latest['comparison'], point_comparison=point_comparison,
        required_cohorts=required_cohort_summary(latest['result']),
        independent=latest['result'].get('independent'), production_adopted=latest['result'].get('production_adopted')))
    plan_path = path.parent / 'plan.json'
    plan = load(plan_path) if plan_path.exists() else {}
    if plan.get('threshold', .5) != .5:
        raise ValueError('Unsupported experiment threshold; do not mix evaluation contracts')
    if plan:
        add('latest_plan', plan_path, {k: plan[k] for k in ('hypothesis_id', 'hypothesis', 'change', 'accept', 'success_criterion', 'failure_criterion', 'acceptance', 'required_cohorts', 'threshold', 'independent') if k in plan})
    if latest['result'].get('diagnostic_evidence') is not None:
        add('latest_diagnostic', path, latest['result']['diagnostic_evidence'])
    training_diagnostics = path.parent / 'training-diagnostics.json'
    if training_diagnostics.exists():
        add('latest_training_diagnostics', training_diagnostics, load(training_diagnostics))
    completed_diagnostics = {}
    for _, _, _, candidate in candidates:
        if candidate['cohort'] != latest['cohort'] or not candidate['result'].get('diagnostic_evidence'):
            continue
        diagnostic_plan = load(candidate['path'].parent/'plan.json')
        hypothesis = diagnostic_plan['hypothesis_id']
        if hypothesis in completed_diagnostics: continue
        key = 'completed_diagnostic_' + str(len(completed_diagnostics))
        summary = candidate['result']['diagnostic_evidence']
        add(key,candidate['path'],dict(hypothesis_id=hypothesis,status='completed',
            measurements=summary,
            note='Completed measurement, not a performance gain. Earlier execution failures do not negate this record.'))
        completed_diagnostics[hypothesis] = [key]
        if len(completed_diagnostics)>=3: break
    current_scores = latest['after']
    failed = {}
    # Geometry diagnostics explicitly preserve the parent result row ordering.
    diagnostic = path.parent / 'geometry-diagnostic.json'
    if diagnostic.exists():
        d = load(diagnostic)
        comparison = compare_predictions([r['target'] for r in rows], current_scores, d['scores'])
        if comparison != d['comparison']:
            raise ValueError('Saved diagnostic metrics do not match its paired scores')
        add('latest_diagnostic', diagnostic, dict(comparison=comparison,
            eligible_rows=d.get('eligible_rows'), positive_rows_with_approved_geometry=d.get('positive_rows_with_approved_geometry'),
            independent=d.get('independent'), events=[{k: event[k] for k in ('row', 'target', 'before', 'after', 'old_peak_retained', 'new_peak', 'retained_tokens', 'photo_tokens') if k in event} for event in d.get('events', [])[:5]]))
        current_scores = d['scores']
        stalled = not comparison['informative_improvement']
        if stalled:
            failed[path.parent.name + '/geometry'] = ['latest_diagnostic']
    else:
        stalled = (not latest['result']['acceptance_passed'] if path in common
                   else not latest['comparison']['informative_improvement'])
    if not stalled:
        if path in common:
            raise LatestExperimentUnavailable('최신 공통 실험이 사전 성공 기준을 충족하여 정체 근거가 없습니다. 기록: ' + str(path.parent / 'record.json'))
        raise ValueError('최신 실험은 개선됐으며 후속 정체 근거가 없습니다. 자동 호출하지 않습니다.')
    execution_failures = {}
    for folder, record in registered:
        if record['status'] not in ('failed', 'interrupted'):
            continue
        verify(folder, record)
        reference = load(folder / 'reference.json')
        if reference['cohort_sha256'] != latest['cohort']:
            continue
        failed_plan = load(folder / 'plan.json')
        key = 'failed_execution_' + str(len(execution_failures))
        add(key, folder / 'record.json', dict(status=record['status'], error_kind=record.get('error_kind'), stage=record.get('stage'), return_code=record.get('return_code'),
            hypothesis_id=failed_plan['hypothesis_id'], hypothesis=failed_plan['hypothesis'], change=failed_plan['change'],
            note='No completed evaluation; do not infer model scores from this execution'))
        execution_failures.setdefault(failed_plan['hypothesis_id'], []).append(key)
        if sum(map(len, execution_failures.values())) >= 4:
            break
    for _, _, _, previous in candidates:
        if len(failed) >= 4:
            break
        previous_plan = load(previous['path'].parent/'plan.json') if previous['path'] in common else {}
        if previous_plan.get('experiment_kind') == 'diagnostic' and previous['result'].get('diagnostic_evidence'):
            continue  # A diagnostic not improving scores does not refute its measured mechanism.
        passed = (previous['result']['acceptance_passed'] if previous['path'] in common
                  else previous['comparison']['informative_improvement'])
        if previous['cohort'] != latest['cohort'] or passed:
            continue
        key = 'failed_' + str(len(failed))
        previous_plan = load(previous['path'].parent / 'plan.json') if (previous['path'].parent / 'plan.json').exists() else {}
        points=previous['result'].get('point_comparison') or previous['result'].get('comparisons',{}).get('latest_reference',{}).get('point')
        rules=previous_plan.get('acceptance',{})
        after=previous['comparison']['after'];reasons=[]
        if 'max_fp' in rules and after['fp']>rules['max_fp']:reasons.append('fp_above_limit')
        if 'max_fn' in rules and after['fn']>rules['max_fn']:reasons.append('fn_above_limit')
        if rules.get('no_new_errors') and not previous['comparison']['no_new_errors']:reasons.append('new_crop_errors')
        if rules.get('require_actual_point_guard'):
            if not points:reasons.append('actual_point_evaluation_missing')
            elif points['new_misses']:reasons.append('actual_point_miss')
        required = required_cohort_summary(previous['result'])
        reasons.extend('required_cohort_failed:' + c['id'] for c in required if not c['acceptance_passed'])
        if not reasons:reasons.append('no_informative_gain_or_other_acceptance_failure')
        plan_path=previous['path'].parent/'plan.json'
        conditions={k:previous_plan[k] for k in ('hypothesis_id','change','experiment_parameter','acceptance','threshold') if k in previous_plan}
        summary=dict(status='completed_not_accepted',comparison=previous['comparison'],point_comparison=points,
            required_cohorts=required,
            conditions=conditions,failure_reasons=reasons,independent=previous['result'].get('independent'))
        if plan_path.exists():
            manifest.append(source(plan_path,root))
        add(key, previous['path'], summary)
        failed[previous_plan.get('hypothesis_id', previous['path'].parent.name)] = [key]
        if len(failed) >= 4:
            break
    errors = [dict(id=r['id'], target=r['target'], before=old, score=score,
                   kind='miss' if r['target'] else 'false_positive')
              for r, old, score in zip(rows, latest['before'], current_scores) if int(score >= .5) != r['target']]
    if not errors:
        raise ValueError('최신 평가에 실패 사례가 없습니다. 자동 호출하지 않습니다.')
    evidence['remaining_errors'] = error_examples(errors,12)
    if path in common:
        folder, record = common[path]
        add('execution_record', folder / 'record.json', {k: record[k] for k in ('experiment_id', 'hypothesis_id', 'status', 'started_at', 'finished_at')})
        diff = (folder / 'changes.diff').read_text()
        limit = 1000 if plan.get('experiment_kind') == 'diagnostic' else 6000
        add('related_code', folder / 'changes.diff', dict(role='frozen executed code diff', excerpt=diff[:limit],
            truncated=len(diff) > limit, code_changes=plan['code_changes']))
    for value in (() if path in common else plan.get('tracked_sha256', {})):
        file = Path(value).resolve()
        if not file.is_relative_to(root / 'card_condition') or file.suffix != '.py' or not file.exists():
            continue
        text = file.read_text()
        functions = [n for n in ast.parse(text).body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        if functions:
            excerpt = '\n'.join(text.splitlines()[functions[0].lineno-1:functions[0].end_lineno])[:2000]
            add('related_code', file, {'role': 'current project implementation, not necessarily executed snapshot', 'excerpt': excerpt})
            break
    if 'related_code' not in evidence:
        raise ValueError('최신 실험 계획에서 관련 프로젝트 코드 근거를 찾지 못했습니다.')
    snapshot = path.parent / 'candidate.py'
    if path not in common and snapshot.exists():
        text = snapshot.read_text()
        functions = [n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)]
        if functions:
            add('executed_code', snapshot, {'role': 'saved executed candidate snapshot', 'excerpt': '\n'.join(text.splitlines()[functions[0].lineno-1:functions[0].end_lineno])[:2000]})
    from .cross_review_contract import baseline_contract
    contract=baseline_contract(root)
    if contract:add('baseline_training_contract',root/contract['source'],contract)
    manifest=list({(item['path'],item['sha256']):item for item in manifest}.values())
    packet = dict(source_mode='project-latest', topic='latest-project-' + latest['cohort'],
        stalled=True, stagnation_reason='Latest saved follow-up still has errors without an informative improvement; earlier gains are retained separately.',
        error_cases=error_examples(errors,12), error_count=len(errors), code_excerpts=[key for key in ('related_code', 'executed_code') if key in evidence],
        same_evaluation_metrics=dict(cohort_sha256=latest['cohort'], regions=len(rows), threshold=.5,
            latest_experiment=latest['comparison'], latest_experiment_actual_points=point_comparison, latest_followup=compare_predictions([r['target'] for r in rows], latest['after'], current_scores),
            independent=latest['result'].get('independent')),
        failed_hypotheses=failed, failed_executions=execution_failures, completed_diagnostics=completed_diagnostics, evidence=evidence, latest_sources=manifest,
        selection='latest dated supported experiment result, then result mtime; only identical cohorts in failure history',
        latest_result=str(path.relative_to(root)), error_cases_truncated=len(errors)>12)
    # A changed prompt/role or newly added summary is not new experimental evidence.
    previous_reviews=[]
    for file in (root/'artifacts/manual-cross-review').glob('*/result.json'):
        if (file.parent/'response_reuse.json').exists():continue
        try:
            review=load(file);old=review.get('packet',{})
            if (not isinstance(review.get('response'),dict) or not any(a.get('status')=='complete' for a in review.get('attempts',[]))
                    or old.get('same_evaluation_metrics',{}).get('cohort_sha256')!=latest['cohort']):continue
            previous_reviews.append((review.get('deadline',file.stat().st_mtime),str(file),old))
        except (OSError,ValueError,TypeError):continue
    prior=max(previous_reviews,key=lambda item:(item[0],item[1])) if previous_reviews else None
    seen={(v['path'],v['sha256']) for v in (prior[2].get('latest_sources',[]) if prior else [])}
    packet['fresh_evidence_ids']=[key for key,value in evidence.items()
        if (key in ('latest_result','latest_diagnostic','related_code','executed_code') or key.startswith('completed_diagnostic_'))
        and isinstance(value,dict) and 'path' in value and (value['path'],value['sha256']) not in seen]
    packet['freshness_reference']=prior[1] if prior else None
    packet['evidence']=compact_evidence(packet['evidence'])
    packet['evidence_reference_format']='Identical values use $ref JSON Pointers rooted at the evidence ID registry. Resolve the referenced value; no facts were omitted.'
    return bound_code_excerpt(bound_repeated_errors(packet))



def error_examples(errors,limit):
    chosen=[]
    for item in errors:
        if not any(v['kind']==item['kind'] for v in chosen):chosen.append(item)
    for item in errors:
        if len(chosen)>=limit:break
        if item not in chosen:chosen.append(item)
    return chosen


COHORT_COLUMNS=['id','grouped_cohort_ids','comparison','point_comparison','acceptance_passed','acceptance','errors','error_count','errors_omitted']
COMPARISON_COLUMNS=['before','after','new_misses','new_false_positives','recovered','aggregate_improved','both_classes_evaluated','constant_prediction','informative_improvement','no_new_errors']
COUNT_COLUMNS=['tp','tn','fp','fn']


def bound_repeated_errors(packet):
    """Bound case lists, retaining every cohort's counts, criteria, verdict and source."""
    if len(encoded(packet).encode())<=23700:return packet
    import copy
    result=copy.deepcopy(packet)
    evidence=expand_evidence(result['evidence'])
    schema=dict(columns=COHORT_COLUMNS,comparison_columns=COMPARISON_COLUMNS,count_columns=COUNT_COLUMNS)
    def comparison(value):
        if value is None:return None
        if set(value)!=set(COMPARISON_COLUMNS):raise ValueError('Unsupported cohort comparison fields; refusing to omit evidence')
        return [[value[k][n] for n in COUNT_COLUMNS] if k in ('before','after') else value[k] for k in COMPARISON_COLUMNS]
    for entry in evidence.values():
        if not isinstance(entry,dict):continue
        summary=entry.get('summary',{});cohorts=summary.get('required_cohorts',[])
        if not cohorts or not isinstance(cohorts,list) or 'errors' not in cohorts[0]:continue
        grouped={};rows=[]
        for original in cohorts:
            c=copy.deepcopy(original)
            if set(c)!={'id','comparison','point_comparison','acceptance_passed','acceptance','errors'}:raise ValueError('Unsupported cohort summary fields; refusing to omit evidence')
            errors=c['errors'];c.update(errors=[],error_count=len(errors),errors_omitted=len(errors))
            signature=encoded({k:v for k,v in c.items() if k!='id'})
            if signature in grouped:
                grouped[signature][1].append(c['id']);continue
            row=[c['id'],[],comparison(c['comparison']),comparison(c['point_comparison']),c['acceptance_passed'],c['acceptance'],c['errors'],c['error_count'],c['errors_omitted']]
            grouped[signature]=row;rows.append(row)
        summary['required_cohorts']=dict(format='cohort_table_v1',schema=schema,rows=rows)
    result['evidence']=compact_evidence(evidence)
    chosen=error_examples(packet['error_cases'],3)
    result['error_cases']=chosen
    result['error_cases_truncated']=len(chosen)<packet['error_count']
    if 'remaining_errors' in result['evidence']:result['evidence']['remaining_errors']=chosen
    result['error_list_summary']=dict(total=packet['error_count'],shown=len(chosen),omitted=packet['error_count']-len(chosen),selection='one per observed kind, then original order; cohort lists retain exact total; full cases remain in source files')
    result['evidence_reference_format']=result['evidence_reference_format'].replace('no facts were omitted.','duplicate values are referenced without loss.')
    result['evidence_reference_format']+=' cohort_table_v1 follows schema columns; before/after follow count_columns. grouped_cohort_ids share metrics and criteria. Full error lists remain in source files.'
    return result


def expand_cohort_table(table):
    if table['schema']!={'columns':COHORT_COLUMNS,'comparison_columns':COMPARISON_COLUMNS,'count_columns':COUNT_COLUMNS}:raise ValueError('Unsupported cohort table schema')
    import copy
    def comparison(row):
        if row is None:return None
        if len(row)!=len(COMPARISON_COLUMNS):raise ValueError('Invalid cohort comparison row')
        value=dict(zip(COMPARISON_COLUMNS,row,strict=True))
        for key in ('before','after'):value[key]=dict(zip(COUNT_COLUMNS,value[key],strict=True))
        return value
    result=[]
    for row in table['rows']:
        c=dict(zip(COHORT_COLUMNS,row,strict=True));others=c.pop('grouped_cohort_ids')
        c['comparison']=comparison(c['comparison']);c['point_comparison']=comparison(c['point_comparison'])
        for identity in [c['id'],*others]:result.append(dict(copy.deepcopy(c),id=identity))
    return result


def compact_evidence(evidence, *, document=False):
    """Lossless JSON Pointer aliases inside the evidence registry, not missing measurements."""
    import copy
    result=copy.deepcopy(evidence);seen={}
    if document and result.get('context_reference_root')=='document':
        # Short root pointers avoid repeating long cohort IDs, criteria and nested aliases.
        # Pool exact values only: no measurement/condition truncation or inferred equivalence.
        from collections import Counter
        counts=Counter();values={}
        def count(value):
            if isinstance(value,(dict,list,str)):
                key=encoded(value)
                if len(key.encode())>=80:counts[key]+=1;values[key]=value
            children=value.values() if isinstance(value,dict) else value if isinstance(value,list) else ()
            for child in children:count(child)
        count(result)
        pool={key:str(i) for i,(key,n) in enumerate(counts.items())
              if n>=2 and (n-1)*len(key.encode())>n*35+12}
        def share(value,exclude=None):
            key=encoded(value) if isinstance(value,(dict,list,str)) else None
            if key in pool and key!=exclude:return {'$ref':'/shared_values/'+pool[key]}
            if isinstance(value,dict):return {k:share(v) for k,v in value.items()}
            if isinstance(value,list):return [share(v) for v in value]
            return value
        if pool:
            if 'shared_values' in result:raise ValueError('Reserved shared value registry')
            result={'shared_values':{i:share(values[key],key) for key,i in pool.items()},**share(result)}
    def pointer(path):return '/'+ '/'.join(str(p).replace('~','~0').replace('/','~1') for p in path)
    def visit(value,path):
        if isinstance(value,(dict,list,str)) and len(encoded(value).encode())>=80:
            key=encoded(value)
            if key in seen:
                alias={'$ref':seen[key]}
                if len(encoded(alias).encode())<len(key.encode()):return alias
            else:seen[key]=pointer(path)
        if isinstance(value,dict):return {k:visit(v,path+[k]) for k,v in value.items()}
        if isinstance(value,list):return [visit(v,path+[i]) for i,v in enumerate(value)]
        return value
    if document:return visit(result,[])
    for key,value in result.items():
        if isinstance(value,dict) and isinstance(value.get('summary'),dict):
            value['summary']={k:visit(v,[key,'summary',k]) for k,v in value['summary'].items()}
    return result


def expand_evidence(evidence, *, decode_tables=True):
    import copy
    def visit(value,trail=()):
        if isinstance(value,dict) and set(value)=={'$ref'}:
            path=value['$ref']
            if path in trail:raise ValueError('Cyclic evidence alias')
            target=evidence
            for key in path.split('/')[1:]:
                key=key.replace('~1','/').replace('~0','~');target=target[int(key)] if isinstance(target,list) else target[key]
            return visit(target,trail+(path,))
        if isinstance(value,dict):
            expanded={k:visit(v,trail) for k,v in value.items()}
            return expand_cohort_table(expanded) if decode_tables and expanded.get('format')=='cohort_table_v1' else expanded
        if isinstance(value,list):return [visit(v,trail) for v in value]
        return copy.deepcopy(value)
    expanded=visit(evidence)
    if isinstance(expanded,dict) and expanded.get('context_reference_root')=='document':expanded.pop('shared_values',None)
    return expanded

def bound_code_excerpt(packet):
    """Trim only the already partial diff; never omit failure criteria or measurements."""
    if len(encoded(packet).encode()) <= 23700:
        return packet
    summary=packet['evidence']['related_code']['summary']
    excerpt=summary.get('excerpt','')
    if not excerpt:
        return packet  # Existing validation still rejects oversized non-code evidence.
    summary.update(truncated=True,budget_truncated=True,excerpt_chars_before_budget=len(excerpt))
    low,high=0,len(excerpt)
    while low<high:
        middle=(low+high+1)//2
        summary['excerpt']=excerpt[:middle]
        if len(encoded(packet).encode())<=23700:low=middle
        else:high=middle-1
    summary['excerpt']=excerpt[:low]
    return packet
