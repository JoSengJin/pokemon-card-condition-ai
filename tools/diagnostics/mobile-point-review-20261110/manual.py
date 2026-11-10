"""Immutable human crop observations; never promote them to localized point truth."""
import argparse
import hashlib
import json
from pathlib import Path
from review import digest

SCOPE='visible_defect_in_displayed_crop'


def validate_manual(packet,answers,legacy_scope=None):
    if packet.get('kind')!='surface_point_review_packet' or packet.get('packet_id')!=digest(packet) or packet.get('region_labels_read_only') is not True:raise ValueError('Original readonly packet required')
    keys={'schema_version','kind','packet_id','responses'}
    if not isinstance(answers,dict) or set(answers) not in (keys,keys|{'scope'}) or type(answers.get('schema_version')) is not int or answers['schema_version']!=1 or answers['kind']!='surface_point_review_manual_draft' or answers['packet_id']!=packet['packet_id'] or not isinstance(answers['responses'],list):raise ValueError('Manual answer schema/packet mismatch')
    if answers.get('scope',legacy_scope)!=SCOPE:raise ValueError('Explicit crop observation scope required; candidate/point truth is different')
    index={e['id']:e for e in packet['entries']};seen=set()
    for r in answers['responses']:
        if not isinstance(r,dict) or set(r)!={'id','image_sha256','region_target','judgment','point','location_description'} or not isinstance(r['id'],str) or r['id'] not in index or r['id'] in seen:raise ValueError('Unknown/duplicate response')
        seen.add(r['id']);e=index[r['id']];row=e['row']
        if e['completed'] or r['image_sha256']!=row['image_sha256'] or type(r['region_target']) is not int or r['region_target']!=row['target']:raise ValueError('Completed evidence/image/old region truth cannot change')
        if r['judgment'] not in (None,'normal','defect','unknown') or r['point'] is not None or not isinstance(r['location_description'],str):raise ValueError('Manual crop observations require explicit judgment/null point/text')
    return answers


def make_receipt(answers,source_text):
    observations=[dict(r) for r in answers['responses'] if r['judgment'] is not None]
    return dict(kind='surface_manual_crop_receipt',packet_id=answers['packet_id'],scope=SCOPE,source_text=source_text,source_answers_sha256=hashlib.sha256(source_text.encode('utf-8')).hexdigest(),human_observations=observations,
        do_not_reask_judgment_ids=[r['id'] for r in observations],conflicts_with_existing_region=[r['id'] for r in observations if r['judgment'] in ('normal','defect') and int(r['judgment']=='defect')!=r['region_target']],
        human_point_labels=[],model_candidate_confirmed_ids=[],existing_region_labels_changed=False,training_applied=False)


def load_reviewed(packet,ledger):
    reviewed={};ledger=Path(ledger)
    if ledger.exists() and not ledger.is_dir():raise ValueError('Ledger directory required')
    for path in sorted(ledger.glob('*.json')):
        receipt=json.loads(path.read_text());answers=json.loads(receipt['source_text']);validate_manual(packet,answers,receipt.get('scope'))
        expected=make_receipt(answers,receipt['source_text'])
        if receipt!=expected or path.stem!=expected['source_answers_sha256']:raise ValueError('Receipt content/hash changed')
        for r in receipt['human_observations']:
            if r['id'] in reviewed and reviewed[r['id']]!=r:raise ValueError('Conflicting human responses; preserve and resolve explicitly')
            reviewed[r['id']]=r
    return reviewed


def ingest_manual(packet_path,answers_path,ledger,legacy_scope=None):
    packet=json.loads(Path(packet_path).read_text());raw=Path(answers_path).read_bytes().decode('utf-8');answers=json.loads(raw);validate_manual(packet,answers,legacy_scope)
    reviewed=load_reviewed(packet,ledger);receipt=make_receipt(answers,raw)
    for r in receipt['human_observations']:
        if r['id'] in reviewed and reviewed[r['id']]!=r:raise ValueError('Conflicting human response; prior evidence not overwritten')
    ledger=Path(ledger);ledger.mkdir(exist_ok=True);target=ledger/(receipt['source_answers_sha256']+'.json')
    if target.exists():
        if json.loads(target.read_text())!=receipt:raise ValueError('Existing receipt differs')
    else:
        with target.open('x') as stream:json.dump(receipt,stream,ensure_ascii=False,indent=2,allow_nan=False)
    return target


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packet',required=True);p.add_argument('--answers',required=True);p.add_argument('--ledger',required=True);p.add_argument('--legacy-scope',choices=[SCOPE]);a=p.parse_args()
    print(ingest_manual(a.packet,a.answers,a.ledger,a.legacy_scope))
