"""Lossless cohort-table encoding for review evidence."""

COHORT_COLUMNS=['id','grouped_cohort_ids','comparison','point_comparison','acceptance_passed','acceptance','errors','error_count','errors_omitted']
COMPARISON_COLUMNS=['before','after','new_misses','new_false_positives','recovered','aggregate_improved','both_classes_evaluated','constant_prediction','informative_improvement','no_new_errors']
COUNT_COLUMNS=['tp','tn','fp','fn']


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
