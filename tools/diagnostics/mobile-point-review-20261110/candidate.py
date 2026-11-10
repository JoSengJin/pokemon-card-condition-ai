"""Candidate-box judgments are separate from crop observations and precise points."""
import json
from pathlib import Path
import subprocess
from review import digest
from manual import load_reviewed
from scriptfree import ROOT,CANDIDATE_SCOPE,CANDIDATE_KIND,render


def validate_candidates(packet,answers):
    if packet.get('packet_id')!=digest(packet) or packet.get('region_labels_read_only') is not True:raise ValueError('Original packet required')
    if not isinstance(answers,dict) or set(answers)!={'schema_version','kind','scope','packet_id','responses'} or type(answers['schema_version']) is not int or answers['schema_version']!=1 or answers['kind']!=CANDIDATE_KIND or answers['scope']!=CANDIDATE_SCOPE or answers['packet_id']!=packet['packet_id'] or not isinstance(answers['responses'],list):raise ValueError('Explicit candidate-box answer schema required')
    index={e['id']:e for e in packet['entries']};seen=set()
    for r in answers['responses']:
        if not isinstance(r,dict) or set(r)!={'id','image_sha256','region_target','judgment','point','location_description','candidate_token','candidate_box'} or not isinstance(r['id'],str) or r['id'] not in index or r['id'] in seen:raise ValueError('Unknown/duplicate candidate response')
        seen.add(r['id']);e=index[r['id']]
        if e['completed'] or r['image_sha256']!=e['row']['image_sha256'] or type(r['region_target']) is not int or r['region_target']!=e['row']['target'] or type(r['candidate_token']) is not int or r['candidate_token']!=e['candidate']['token'] or not isinstance(r['candidate_box'],list) or len(r['candidate_box'])!=4 or any(type(v) not in (int,float) for v in r['candidate_box']) or r['candidate_box']!=e['candidate']['box']:raise ValueError('Candidate/image/region binding changed')
        if r['judgment'] not in (None,'normal','defect','unknown') or r['point'] is not None or not isinstance(r['location_description'],str):raise ValueError('Explicit candidate judgment,not localized point,required')
    return answers


if __name__=='__main__':
    packet=json.loads((ROOT/'artifacts/mobile-point-review-20261110/packet.json').read_text());reviewed=load_reviewed(packet,ROOT/'artifacts/mobile-human-review-ledger-20261110')
    indices=[i for i,e in enumerate(packet['entries']) if not e['completed'] and e['id'] not in reviewed][:10]
    out=ROOT/'artifacts/mobile-candidate-review-20261110';out.mkdir(exist_ok=True);sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();pages=[]
    for start in range(0,len(indices),5):
        part=indices[start:start+5];name=f'candidate-{start//5+1:02d}.html';render(packet,part,out,name,sha,candidate=True);pages.append(dict(file=name,indices=part))
    with (out/'manifest.json').open('x') as stream:json.dump(dict(source_sha=sha,scope=CANDIDATE_SCOPE,packet_id=packet['packet_id'],pages=pages,crop_answers_preserved=len(reviewed),new_labels=0,model_calls=0),stream,indent=2)
    print(json.dumps(dict(cases=len(indices),files=pages,source_sha=sha)))
