"""Synthetic-only mobile point review contracts; no human answers/model calls."""
import ast
import base64
import copy
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from PIL import Image

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE))
from review import make_packet,digest,validate,ingest,render
from audit import packet_digest


def rejects(fn,*args):
    try:fn(*args)
    except (ValueError,FileExistsError):return
    raise AssertionError('Invalid/overwriting input accepted')


class Audit(HTMLParser):
    def __init__(self):super().__init__();self.images=[];self.forms=0;self.svg=0;self.choices=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='img':self.images.append(a)
        if tag=='svg':self.svg+=1
        if tag=='fieldset':self.forms+=1
        if 'data-judgment' in a:self.choices.append(a['data-judgment'])


if __name__=='__main__':
    canonical=json.loads((ROOT/'artifacts/surface-grounding-20261110/packet.json').read_text())
    # Reuse source shape,replace photo and metadata with a synthetic fixture only.
    with tempfile.TemporaryDirectory() as temp:
        out=Path(temp);image=out/'fixture.png';im=Image.new('RGB',(448,448));im.putpixel((200,200),(255,0,0));im.save(image)
        import hashlib
        old=copy.deepcopy(next(e for e in canonical['entries'] if e['selected']));old['row'].update(id='fixture/back/surface/center',group='fixture',image=str(image),image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),target=0,box=[0.,0.,1.,1.]);old['image_size']=[448,448];old['known_points']=[];old['selected']=True
        g=dict(box=[.4,.4,.5,.5],crop_pixels=[0,0,448,448],resized=[448,448],pad=[0,0],coverage=1)
        old['evidence']=dict(top_index=1,top_geometry=g,second_geometry=None);old['patch_scores']=[.1]*1024
        source=dict(entries=[old],training_allowed=False);source['packet_id']=packet_digest(source)
        packet=make_packet(source);assert packet['entries'][0]['candidate']['state']=='unreviewed' and packet['region_labels_read_only']
        e=packet['entries'][0];r=dict(id=e['id'],image_sha256=e['row']['image_sha256'],region_target=0,judgment='defect',point=dict(x=.45,y=.45),note='  원문\n<script>메모</script>  ')
        answer=dict(schema_version=1,kind='surface_point_review_answers',packet_id=packet['packet_id'],responses=[r]);validate(packet,answer)
        for key,value in [('region_target',1),('region_target',True),('judgment',''),('id','other'),('image_sha256','other'),('point',None)]:
            bad=copy.deepcopy(answer);bad['responses'][0][key]=value;rejects(validate,packet,bad)
        bad=copy.deepcopy(answer);bad['responses']*=2;rejects(validate,packet,bad)
        for value in (float('nan'),True,2.):
            bad=copy.deepcopy(answer);bad['responses'][0]['point']['x']=value;rejects(validate,packet,bad)
        unknown=copy.deepcopy(answer);unknown['responses'][0].update(judgment='unknown',point=None);validate(packet,unknown)
        empty=dict(answer,responses=[]);validate(packet,empty)
        done=copy.deepcopy(packet);done['entries'][0]['completed']=True;done['packet_id']=digest(done);bad=copy.deepcopy(answer);bad['packet_id']=done['packet_id'];rejects(validate,done,bad)
        pp=out/'packet.json';aa=out/'answers.json';pp.write_text(json.dumps(packet));aa.write_text(json.dumps(answer));result=ingest(pp,aa,out/'sidecar.json')
        assert len(result['human_point_labels'])==1 and result['conflicts_with_existing_normal_region']==[r['id']] and not result['region_labels_changed'] and not result['training_applied'] and result['answers']['responses'][0]['note']==r['note']
        rejects(ingest,pp,aa,out/'sidecar.json');rejects(ingest,pp,aa,aa)
        up=out/'unknown.json';up.write_text(json.dumps(unknown));unclear=ingest(pp,up,out/'unknown-sidecar.json');assert unclear['human_point_labels']==[] and unclear['unknown_ids']==[r['id']]
        render(packet,[0],out,'test.html','synthetic-only');text=(out/'test.html').read_text();a=Audit();a.feed(text)
        assert a.forms==1 and a.choices==['normal','defect','unknown'] and a.svg==0 and len(a.images)==3
        assert 'id="input-status"' in text and 'data-state="pending"' in text and '<fieldset disabled data-requires-js>' in text
        assert all(i['src'].startswith('data:image/') for i in a.images) and '미확인' in text and 'min-height:44px' in text
        raw=next(i for i in a.images if 'data-locate' in i)
        with Image.open(io.BytesIO(base64.b64decode(raw['src'].split(',')[1]))) as decoded:assert decoded.convert('RGB').tobytes()==im.tobytes()
        render(done,[0],out,'done.html','synthetic-only');assert '<fieldset>' not in (out/'done.html').read_text()
        rejects(render,packet,[0]*6,out,'bad.html','synthetic')
        js=(HERE/'review.js').read_text();assert 'execCommand("copy")' in js and 'navigator.clipboard' not in js and 'localStorage' not in js
        assert js.count('function ')==7
    subprocess.run(['node',str(HERE/'checks.cjs')],check=True)
    subprocess.run(['node',str(HERE/'touch_checks.cjs')],check=True)
    counts={p.name:sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)) for n in ast.walk(ast.parse(p.read_text()))) for p in HERE.glob('*.py')};assert max(counts.values())<=7
    print('PASS: explicit-point truth only,unknown/pending not binary,conflicts preserved without region overwrite,no overwrite,completed not reasked,native pixels,≤5 static inline img/mobile controls')
    print(json.dumps(dict(function_counts=counts,javascript_functions=7,model_calls=0,human_answers_created=0)))
