"""Read-only label audit against a frozen development snapshot."""
import hashlib
import json
from pathlib import Path
from .data import LABELS, load_manifest
from .review import ReviewStore


def label_audit(inventory, reference, output):
    output=Path(output)
    if output.exists():
        raise ValueError('Output exists; choose a new path')
    # No final/test labels or pixels are loaded by this development audit.
    frozen={r['id']:r for r in load_manifest(reference,splits={'train','val'})}
    current=ReviewStore(inventory)
    findings=[]
    for row in current.rows:
        old=frozen.get(row['id'])
        if old is None:
            continue
        if row.get('split') != old['split']:
            findings.append({'id':row['id'],'kind':'split_changed','current':row.get('split'),
                             'frozen':old['split'],'action':'Preserve frozen split when making a new snapshot'})
        for side,a in row.get('side_annotations',{}).items():
            labels=a['labels']
            if labels['gradable']==0:
                if not a.get('visibility_issues'):
                    findings.append({'id':row['id']+'/'+side,'kind':'ungradable_reason_missing',
                                     'action':'Record glare, blur, obstruction, cropped, low_resolution, perspective, or shadow'})
                negatives=[k for k in LABELS if k!='gradable' and labels[k]==0]
                if negatives:
                    findings.append({'id':row['id']+'/'+side,'kind':'ungradable_negative_review',
                                     'labels':negatives,'action':'Confirm these areas are visible; obscured areas should be null, not 0'})
            previous=old.get('side_annotations',{}).get(side)
            if previous and (a['image']!=previous['image'] or labels!=previous['labels']
                             or a.get('visibility_issues',[])!=previous.get('visibility_issues',[])):
                findings.append({'id':row['id']+'/'+side,'kind':'annotation_changed',
                                 'action':'Review change and create a new snapshot; do not overwrite old experiments'})
    report={'inventory_sha256':hashlib.sha256(Path(inventory).read_bytes()).hexdigest(),
            'reference_sha256':hashlib.sha256(Path(reference).read_bytes()).hexdigest(),
            'development_cards':len(frozen),'findings':findings,'labels_modified':False,
            'limitations':['Review prompts are not confirmed labeling errors.',
                            'Visible defects may coexist with ungradable areas; do not erase positives.',
                            'Only IDs in the development reference are compared.']}
    with output.open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
    return report
