"""Lossless references inside bounded review evidence."""
from .cross_review import encoded
from .cross_review_evidence_cohort import expand_cohort_table


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
