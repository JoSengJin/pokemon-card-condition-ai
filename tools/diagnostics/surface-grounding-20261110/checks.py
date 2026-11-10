"""Synthetic grounding/audit/answer/renderer contracts; no real inference."""
import ast
import copy
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import torch
from PIL import Image

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(HERE))
from audit import audit_points,make_packet,packet_digest
from answers import validate_answers,ingest
from report import render_report


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def rejects(function,*args):
    try:function(*args)
    except (ValueError,FileExistsError):return
    raise AssertionError('Invalid or overwriting operation accepted')


if __name__=='__main__':
    torch.manual_seed(20261110);torch.set_num_threads(2)
    evidence=load('evidence',ROOT/'tools/diagnostics/surface-patch-evidence-20261108/patch_evidence.py')
    geometry=load('geometry',ROOT/'tools/diagnostics/surface-patch-evidence-20261108/patch_geometry.py')
    x=torch.randn(4,1024,384);valid=torch.ones(4,1024,dtype=torch.bool);valid[:,100:200]=False
    coef=torch.randn(384)*.01;bias=torch.tensor(.03)
    scores,details,logits=evidence.score_with_evidence(x,valid,coef,bias)
    expected=(x@coef+bias).masked_fill(~valid,-torch.inf).amax(1).sigmoid().tolist()
    assert scores==expected and all(valid[i,e['top_index']] for i,e in enumerate(details))
    for size in ((448,448),(300,900),(901,299)):
        full=[0.,0.,1.,1.]
        for token in range(1024):
            try:g=geometry.token_box(size,full,token)
            except ValueError:continue
            assert 0<g['coverage']<=1 and all(0<=v<=1 for v in g['box'])
    with tempfile.TemporaryDirectory() as temp:
        directory=Path(temp);image=directory/'original #?.png';Image.new('RGB',(448,448)).save(image);sha=hashlib.sha256(image.read_bytes()).hexdigest()
        rows=[dict(id='positive',side='back',group='g',target=1,image=str(image),image_sha256=sha,box=[0.,0.,.5,1.],area='middle_left'),dict(id='normal',side='back',group='g',target=0,image=str(image),image_sha256=sha,box=[.5,0.,1.,1.],area='middle_right')]
        annotation=dict(id='card',group='g',reviewed_by='J',side_annotations=dict(back=dict(image=str(image),labels=dict(surface_defect=1),defect_points=[dict(label='surface_defect',x=.25,y=.5)])))
        documents=[annotation,copy.deepcopy(annotation)]
        for point in [dict(label='edge_defect',x=.25,y=.5),dict(label='surface_defect',x=.75,y=.5),dict(label='surface_defect',x=.5,y=.5),dict(label='surface_defect',x=True,y=.5)]:
            d=copy.deepcopy(annotation);d['side_annotations']['back']['defect_points']=[point];documents.append(d)
        d=copy.deepcopy(annotation);d['group']='outside';documents.append(d)
        d=copy.deepcopy(annotation);d['side_annotations']['front']=d['side_annotations'].pop('back');documents.append(d)
        d=copy.deepcopy(annotation);d['reviewed_by']=None;documents.append(d)
        source=directory/'labels.jsonl';source.write_text('\n'.join(json.dumps(d) for d in documents))
        audit=audit_points(rows,[source]);assert audit['reusable_points']==1 and audit['regions_with_points']==1 and len(audit['locations']['positive'][0]['sources'])==2
        assert not audit['locations']['normal'] and not audit['region_truth_changed']
        reasons={r['reason'] for r in audit['rejected']}
        assert reasons=={'other_or_missing_kind','point_conflicts_with_fixed_normal','ambiguous_or_outside_region','invalid_coordinates','image_or_group_outside_pool','not_explicit_confirmed_surface_point'}
        pool=[];probabilities=[];folds={}
        for f in range(5):
            for j,(truth,score) in enumerate([(1,.9),(1,.8),(0,.1),(0,.2),(1,.1),(0,.9)]):
                row=dict(rows[0],id=f'card{f}/back/surface/{j}',group=f'g{f}',target=truth,area='center',box=[0.,0.,1.,1.]);pool.append(row);probabilities.append(score);folds[row['group']]=f
        packet=make_packet(pool,probabilities,folds,{},dict(kind='synthetic'))
        assert packet['summary']['errors']==10 and packet['summary']['correct_controls']==10 and packet['summary']['selected']==20
        other=make_packet(list(reversed(pool)),list(reversed(probabilities)),folds,{},dict(kind='synthetic'))
        assert {e['row']['id'] for e in packet['entries'] if e['selected']}=={e['row']['id'] for e in other['entries'] if e['selected']}
        entry=next(e for e in packet['entries'] if e['selected'] and e['row']['target']);row=entry['row']
        response=dict(id=row['id'],image_sha256=sha,target=1,status='located',point=dict(x=.4,y=.6,label='surface_defect'),category='surface_mark',note='  원문\n<script>그대로</script>  ')
        answer=dict(schema_version=1,kind='surface_grounding_human_evidence',packet_id=packet['packet_id'],responses=[response])
        assert validate_answers(packet,answer)['responses'][0]['note']==response['note']
        for field,value in [('target',0),('target',True),('id','unknown'),('image_sha256','other'),('status','pending'),('note',None)]:
            bad=copy.deepcopy(answer);bad['responses'][0][field]=value;rejects(validate_answers,packet,bad)
        for key,value in [('x',2.),('x',float('nan')),('x',True),('label','edge_defect')]:
            bad=copy.deepcopy(answer);bad['responses'][0]['point'][key]=value;rejects(validate_answers,packet,bad)
        bad=copy.deepcopy(answer);bad['responses']*=2;rejects(validate_answers,packet,bad)
        bad=copy.deepcopy(answer);bad['responses'][0]['new_target']=0;rejects(validate_answers,packet,bad)
        bad=copy.deepcopy(answer);bad['packet_id']='other';rejects(validate_answers,packet,bad)
        rejects(validate_answers,packet,[])
        unknown=copy.deepcopy(answer);unknown['responses'][0].update(status='cannot_localize',point=None,category='unclear');assert validate_answers(packet,unknown)['responses'][0]['point'] is None
        changed=copy.deepcopy(packet);changed['entries'][0]['row']['target']=1-changed['entries'][0]['row']['target'];rejects(validate_answers,changed,answer)
        already=copy.deepcopy(packet);already['entries'][entry['parent_index']]['known_points']=[response['point']];already['packet_id']=packet_digest(already)
        old=copy.deepcopy(answer);old['packet_id']=already['packet_id'];rejects(validate_answers,already,old)
        entry['evidence']=dict(top_index=7,top_geometry=dict(box=[.2,.3,.5,.7]))
        packet['packet_id']=packet_digest(packet);answer['packet_id']=packet['packet_id']
        pp=directory/'packet.json';ap=directory/'answers.json';result=directory/'validated.json';pp.write_text(json.dumps(packet));ap.write_text(json.dumps(answer,ensure_ascii=False));before=ap.read_bytes()
        ingested=ingest(pp,ap,result);assert len(ingested['pending_ids'])==19 and not ingested['region_truth_changed'] and ingested['answers']==answer
        assert ingested['model_support_comparisons'][0]['top_patch_support_contains_human_point'] is True and not ingested['causal_attribution_proven']
        rejects(ingest,pp,ap,result);rejects(ingest,pp,ap,ap);assert ap.read_bytes()==before
        unknown['packet_id']=packet['packet_id'];up=directory/'unknown.json';up.write_text(json.dumps(unknown))
        unclear=ingest(pp,up,directory/'unclear-sidecar.json')
        assert unclear['model_support_comparisons'][0]['top_patch_support_contains_human_point'] is None and unclear['cannot_localize_ids']==[row['id']]
        for e in packet['entries']:
            e['image_size']=[448,448]
            if e['selected']:
                e['evidence']=dict(top_index=0,top_geometry=geometry.token_box((448,448),e['row']['box'],0),second_geometry=None)
                e['patch_scores']=[.1]*1024
        packet['packet_id']=packet_digest(packet)
        render_report(packet,dict(source_sha='synthetic-only'),directory,HERE/'review.js')
        page=(directory/'report.html').read_text();HTMLParser().feed(page)
        assert page.count('<article data-index=')==20 and page.count('<fieldset>')==20 and 'original%20%23%3F.png' in page
        assert 'data:image/png;base64,' in page and 'data-locate="true"' in page and 'value="">선택 전' in page
        assert 'innerHTML' not in (HERE/'review.js').read_text()
        embedded=page.split('<script type="application/json" id="packet">')[1].split('</script>')[0];assert json.loads(embedded)==packet
    subprocess.run(['node',str(HERE/'review_checks.cjs')],check=True)
    counts={p.name:sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)) for n in ast.walk(ast.parse(p.read_text()))) for p in HERE.glob('*.py')}
    assert max(counts.values())<=7
    js=(HERE/'review.js').read_text();assert js.count('function ')==7 and '=>' not in js
    worker=ast.parse((HERE/'worker.py').read_text())
    calls=[n.func.attr for n in ast.walk(worker) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
    assert not set(calls)&{'fit','fit_detail_head','backward','step'}
    print('PASS: typed same-image/group point audit, dedup/conflict/unknown guards; all errors+stratified deterministic controls; frozen score API/geometry; answer binding/note preservation/no-overwrite; HTML original/model separation and encoded paths')
    print(json.dumps(dict(function_counts=counts,javascript_functions=7,real_photo_inference_calls=0,training_calls=0)))
