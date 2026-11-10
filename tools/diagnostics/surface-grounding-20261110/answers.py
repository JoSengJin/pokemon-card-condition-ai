"""Validate explicit human location/explanation as a diagnostic sidecar only."""
import argparse
import json
import math
from pathlib import Path
from audit import packet_digest


def validate_answers(packet,answers):
    if not isinstance(packet,dict) or not isinstance(answers,dict):raise ValueError('Packet and answers must be objects')
    if packet.get('packet_id')!=packet_digest(packet) or packet.get('training_allowed') is not False or packet.get('region_truth_editable') is not False:
        raise ValueError('Unchanged diagnostic packet required')
    if (set(answers)!={'schema_version','kind','packet_id','responses'} or type(answers['schema_version']) is not int or answers['schema_version']!=1
            or answers['kind']!='surface_grounding_human_evidence' or answers['packet_id']!=packet['packet_id'] or not isinstance(answers['responses'],list)):
        raise ValueError('Answers must bind exactly to the diagnostic packet')
    index={e['row']['id']:e for e in packet['entries']};seen=set()
    for response in answers['responses']:
        if not isinstance(response,dict) or set(response)!={'id','image_sha256','target','status','point','category','note'}:raise ValueError('Explicit response schema required; no label overrides')
        identity=response['id']
        if not isinstance(identity,str) or identity not in index or identity in seen:raise ValueError('Unknown or duplicate region response')
        seen.add(identity);entry=index[identity];row=entry['row']
        if not entry['selected'] or entry['known_points']:raise ValueError('Only selected missing evidence may be reviewed')
        if type(response['target']) is not int or response['target']!=row['target'] or response['image_sha256']!=row['image_sha256']:raise ValueError('Fixed region truth/image changed')
        if not isinstance(response['note'],str):raise ValueError('Human note must be preserved verbatim')
        category=response['category'];point=response['point']
        if response['status']=='cannot_localize':
            if point is not None or category!='unclear':raise ValueError('Unlocalizable evidence is unknown, not a negative point')
        elif response['status']=='located':
            allowed=('surface_mark','other') if row['target'] else ('print_pattern','reflection_or_cover','other')
            if category not in allowed or not isinstance(point,dict) or set(point)!={'x','y','label'}:raise ValueError('Explicit compatible point/category required')
            if point['label']!=('surface_defect' if row['target'] else 'normal_explanation'):raise ValueError('Point kind cannot be reinterpreted')
            if any(type(point[k]) not in (int,float) or not math.isfinite(point[k]) or not 0<=point[k]<=1 for k in ('x','y')):raise ValueError('Finite original-photo normalized point required')
            l,t,r,b=row['box']
            if not l<=point['x']<=r or not t<=point['y']<=b:raise ValueError('Point outside its reviewed region')
        else:raise ValueError('Pending/unsubmitted status is not a human answer')
    return answers


def ingest(packet_path,answers_path,output):
    packet=json.loads(Path(packet_path).read_text());answers=json.loads(Path(answers_path).read_text());validate_answers(packet,answers)
    index={e['row']['id']:e for e in packet['entries']};reviewed={r['id'] for r in answers['responses']}
    comparisons=[]
    for response in answers['responses']:
        evidence=index[response['id']].get('evidence',{});geometry=evidence.get('top_geometry');point=response['point'];contains=None
        if response['status']=='located' and geometry:
            l,t,r,b=geometry['box'];contains=l<=point['x']<=r and t<=point['y']<=b
        comparisons.append(dict(id=response['id'],status=response['status'],top_token_index=evidence.get('top_index'),
            top_patch_support_contains_human_point=contains,meaning='geometric_support_only_not_causal_or_localization_accuracy'))
    record=dict(schema_version=1,kind='validated_grounding_sidecar',packet_id=packet['packet_id'],answers=answers,
        model_support_comparisons=comparisons,causal_attribution_proven=False,
        annotation_applied_to_training=False,region_truth_changed=False,
        pending_ids=[key for key,e in index.items() if e['selected'] and not e['known_points'] and key not in reviewed],
        cannot_localize_ids=[r['id'] for r in answers['responses'] if r['status']=='cannot_localize'],
        source_answers_sha256=__import__('hashlib').sha256(Path(answers_path).read_bytes()).hexdigest())
    with Path(output).open('x') as stream:json.dump(record,stream,ensure_ascii=False,indent=2,allow_nan=False)
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--packet',required=True);parser.add_argument('--answers',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();result=ingest(args.packet,args.answers,args.output)
    print(json.dumps(dict(submitted=len(result['answers']['responses']),pending=len(result['pending_ids']),unlocalizable=len(result['cannot_localize_ids']),training_changed=False)))
