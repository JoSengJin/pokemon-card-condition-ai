"""Static script-free fallback checks; no device-render or human truth claims."""
import ast
import copy
import html
import itertools
import json
from html.parser import HTMLParser
from pathlib import Path
import re
import tempfile
from scriptfree import ROOT,HERE,STATES,render
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
        assert 'script' not in a.tags and 'svg' not in a.tags and 'iframe' not in a.tags and a.tags.count('form')==1
        assert len(a.radios)==20 and len(a.ids)==len(set(a.ids)) and sum('checked' in r for r in a.radios)==5
        assert all('disabled' not in r for r in a.radios)
        texts=re.findall(r'<div class="answer" id="result-([^"]+)"><p>.*?</p><textarea[^>]*>(.*?)</textarea></div>',text,re.S);assert len(texts)==1024
        for (suffix,raw),combination in zip(texts,itertools.product(STATES,repeat=5)):
            draft=json.loads(html.unescape(raw));expected=[]
            assert suffix=='-'.join(state[0] for state in combination)
            selector='form.review'+''.join(f':has(#c{n}-{state[0]}:checked)' for n,state in zip(range(6,11),combination))
            assert selector+f' #result-{suffix}'+'{display:block}' in text
            for e,state in zip(packet['entries'][5:10],combination):
                if state[2] is not None:expected.append(dict(id=e['id'],image_sha256=e['row']['image_sha256'],region_target=e['row']['target'],judgment=state[2],point=None,location_description=''))
            assert draft==dict(schema_version=1,kind='surface_point_review_manual_draft',packet_id=packet['packet_id'],responses=expected)
            try:validate(packet,draft)
            except ValueError:pass
            else:raise AssertionError('Draft accepted as exact point truth')
        fallback=json.loads(html.unescape(re.search(r'aria-label="직접 입력할 전체 답 JSON"[^>]*>(.*?)</textarea>',text,re.S)[1]))
        assert len(fallback['responses'])==5 and all(r['judgment'] is None for r in fallback['responses'])
        assert '@supports selector(:has(*)){#manual-fallback{display:none}' in text and 'localStorage' not in text
        assert 'href="#results"' in text and 'href="#answers-' not in text and '선택 전 항목은 JSON에서 빠집니다' in text
        assert len(text.encode())<8*1024*1024
        completed=copy.deepcopy(packet);completed['entries'][5]['completed']=True;completed['packet_id']=digest(completed)
        assert render(completed,list(range(5,10)),out,'done.html','synthetic-check')==4
        assert '<article data-index="5">' not in (out/'done.html').read_text()
        try:render(packet,list(range(6)),out,'too-many.html','synthetic-check')
        except ValueError:pass
        else:raise AssertionError('More than five allowed')
    assert digest(packet)==before
    counts={name:sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)) for n in ast.walk(ast.parse((HERE/name).read_text()))) for name in ('scriptfree.py','scriptfree_checks.py')};assert max(counts.values())<=7
    print('PASS: all1024 combinations map to one selected full JSON;pending omitted/unknown explicit;draft rejected by exactpoint validator;CSS :has mapping/support fallback;completed skipped;max5;10 native images identical;noJS;under8MiB;no labels/model calls')
    print(json.dumps(dict(function_counts=counts,device_render_verified=False)))
