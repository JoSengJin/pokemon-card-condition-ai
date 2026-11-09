"""Link explicit same-image surface points without changing region truth."""
import hashlib
import json
import math
from pathlib import Path


def packet_digest(packet):
    return hashlib.sha256(json.dumps({k:v for k,v in packet.items() if k!='packet_id'},sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def audit_points(rows,sources):
    by_photo={};locations={r['id']:[] for r in rows};seen={};rejected=[];counts={};hashes={}
    for row in rows:
        side=row.get('side') or ('back' if '/back/' in row['id'] else 'front' if '/front/' in row['id'] else None)
        by_photo.setdefault((row['image_sha256'],row['group'],side),[]).append(row)
    for source in sources:
        for line_number,line in enumerate(Path(source).read_text().splitlines(),1):
            if not line.strip():continue
            item=json.loads(line)
            for side,annotation in item.get('side_annotations',{}).items():
                for point in annotation.get('defect_points',[]):
                    reason=None;label=point.get('label');counts[label or 'missing_kind']=counts.get(label or 'missing_kind',0)+1
                    if label!='surface_defect':reason='other_or_missing_kind'
                    elif item.get('excluded') or not item.get('reviewed_by') or annotation.get('labels',{}).get(label)!=1:reason='not_explicit_confirmed_surface_point'
                    elif any(type(point.get(k)) not in (int,float) or not math.isfinite(point[k]) or not 0<=point[k]<=1 for k in ('x','y')):reason='invalid_coordinates'
                    path=annotation.get('image')
                    if reason is None:
                        if not isinstance(path,str) or not Path(path).is_file():reason='missing_source_image'
                        else:
                            if path not in hashes:hashes[path]=hashlib.sha256(Path(path).read_bytes()).hexdigest()
                            candidates=by_photo.get((hashes[path],item.get('group'),side),[])
                            if not candidates:reason='image_or_group_outside_pool'
                    if reason is None:
                        hits=[r for r in candidates if r['box'][0]<=point['x']<=r['box'][2] and r['box'][1]<=point['y']<=r['box'][3]]
                        if len(hits)!=1:reason='ambiguous_or_outside_region'
                        elif hits[0]['target']!=1:reason='point_conflicts_with_fixed_normal'
                    origin=dict(source=str(source),line=line_number,card_id=item.get('id'),side=side)
                    if reason is not None:
                        rejected.append(dict(origin,reason=reason,label=label));continue
                    row=hits[0];key=(row['id'],point['x'],point['y'],label)
                    if key in seen:seen[key]['sources'].append(origin)
                    else:
                        value=dict(x=point['x'],y=point['y'],label=label,image_sha256=row['image_sha256'],coordinate_frame='exif_oriented_normalized',sources=[origin])
                        seen[key]=value;locations[row['id']].append(value)
    return dict(locations=locations,source_files=[str(s) for s in sources],point_kind_counts=counts,rejected=rejected,
        reusable_points=sum(len(v) for v in locations.values()),regions_with_points=sum(bool(v) for v in locations.values()),
        positive_regions_without_points=sum(r['target']==1 and not locations[r['id']] for r in rows),
        region_truth_changed=False,unreviewed_is_normal=False)


def make_packet(rows,scores,folds,locations,source):
    if len(rows)!=len(scores) or len({r['id'] for r in rows})!=len(rows):raise ValueError('Unique aligned region rows required')
    entries=[];strata={}
    for i,(row,score) in enumerate(zip(rows,scores)):
        if type(row['target']) is not int or row['target'] not in (0,1) or not math.isfinite(score) or not 0<=score<=1:raise ValueError('Explicit fixed truth and finite probability required')
        fold=folds[row['group']];outcome=('TP' if score>=.5 else 'FN') if row['target'] else ('FP' if score>=.5 else 'TN')
        e=dict(row=row,parent_index=i,fold=fold,saved_score=score,outcome=outcome,known_points=locations.get(row['id'],[]),selected=outcome in ('FN','FP'),selection_reason='all_errors' if outcome in ('FN','FP') else None)
        entries.append(e)
        if outcome in ('TP','TN'):strata.setdefault((fold,row['area'],outcome),[]).append(e)
    for group in strata.values():
        chosen=min(group,key=lambda e:hashlib.sha256(e['row']['id'].encode()).hexdigest())
        chosen['selected']=True;chosen['selection_reason']='hash_chosen_correct_control'
    packet=dict(schema_version=1,kind='surface_grounding_packet',source=source,entries=entries,
        summary=dict(rows=len(entries),groups=len({r['group'] for r in rows}),errors=sum(e['outcome'] in ('FN','FP') for e in entries),
            selected=sum(e['selected'] for e in entries),correct_controls=len(strata),
            selected_missing_points=sum(e['selected'] and not e['known_points'] for e in entries)),
        independent=False,training_allowed=False,region_truth_editable=False)
    packet['packet_id']=packet_digest(packet)
    return packet
