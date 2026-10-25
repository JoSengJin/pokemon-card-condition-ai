"""Bound repeated review evidence while preserving metrics and failure gates."""
from .cross_review import encoded
from .cross_review_evidence_cohort import COHORT_COLUMNS, COMPARISON_COLUMNS, COUNT_COLUMNS
from .cross_review_evidence_codec import compact_evidence, expand_evidence


def error_examples(errors,limit):
    chosen=[]
    for item in errors:
        if not any(v['kind']==item['kind'] for v in chosen):chosen.append(item)
    for item in errors:
        if len(chosen)>=limit:break
        if item not in chosen:chosen.append(item)
    return chosen



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
