"""Static script-free fallback checks; no device-render or human truth claims."""
import ast
import copy
import html
import json
from html.parser import HTMLParser
from pathlib import Path
import re
import tempfile
from scriptfree import ROOT,HERE,render
from review import digest,validate


class Audit(HTMLParser):
    def __init__(self):super().__init__();self.images=[];self.radios=[];self.tags=[];self.ids=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);self.tags.append(tag)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='img':self.images.append(a['src'])
        if tag=='input' and a.get('type')=='radio':self.radios.append(a)


if __name__=='__main__':
    packet=json.loads((ROOT/'artifacts/mobile-point-review-20261110/packet.json').read_text());before=digest(packet)
    with tempfile.TemporaryDirectory() as temp:
        out=Path(temp);assert render(packet,list(range(5,10)),out,'test.html','synthetic-check')==5
        text=(out/'test.html').read_text();a=Audit();a.feed(text)
        old=Audit();old.feed((ROOT/'artifacts/mobile-point-review-20261110/review-02.html').read_text())
        assert a.images==[src for j,src in enumerate(old.images) if j%3!=2]
        assert len(a.images)==10 and all(src.startswith('data:image/') for src in a.images)
        assert 'script' not in a.tags and 'svg' not in a.tags and 'iframe' not in a.tags and 'form' not in a.tags
        assert len(a.radios)==20 and len(a.ids)==len(set(a.ids)) and sum('checked' in r for r in a.radios)==5
        assert all('disabled' not in r for r in a.radios)
        texts=re.findall(r'<textarea[^>]*>(.*?)</textarea>',text,re.S);assert len(texts)==20
        drafts=[json.loads(html.unescape(t)) for t in texts]
        for offset,draft in enumerate(drafts):
            r=draft['responses'][0];e=packet['entries'][5+offset//4]
            assert draft['kind']=='surface_point_review_manual_draft' and draft['packet_id']==packet['packet_id']
            assert r['id']==e['id'] and r['image_sha256']==e['row']['image_sha256'] and r['region_target']==e['row']['target']
            assert r['point'] is None and r['location_description']=='' and r['judgment']==[None,'normal','defect','unknown'][offset%4]
            try:validate(packet,draft)
            except ValueError:pass
            else:raise AssertionError('Draft accepted as exact point truth')
        for n in range(6,11):
            for key in ('pending','normal','defect','unknown'):
                assert f'#c{n}-{key}:checked ~ .answers .result-{key}' in text
        assert ':has(' not in text and 'localStorage' not in text and '자동 저장은 지원하지 않습니다' in text
        completed=copy.deepcopy(packet);completed['entries'][5]['completed']=True;completed['packet_id']=digest(completed)
        assert render(completed,list(range(5,10)),out,'done.html','synthetic-check')==4
        assert '<article data-index="5">' not in (out/'done.html').read_text()
        try:render(packet,list(range(6)),out,'too-many.html','synthetic-check')
        except ValueError:pass
        else:raise AssertionError('More than five allowed')
    assert digest(packet)==before
    counts={name:sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)) for n in ast.walk(ast.parse((HERE/name).read_text()))) for name in ('scriptfree.py','scriptfree_checks.py')};assert max(counts.values())<=7
    print('PASS: five cases;10 inline native images identical;zero script/SVG/external image;20 explicit manual drafts;unknown/pending not point truth;draft rejected by exact point validator;completed skipped;CSS sibling selectors without :has;no labels/model calls')
    print(json.dumps(dict(function_counts=counts,device_render_verified=False)))
