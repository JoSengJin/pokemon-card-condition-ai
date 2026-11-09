"""Synthetic renderer tests; no real photos, data, training or inference."""
import ast
import base64
import copy
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import render


def reject(data):
    try:render.validate_report(data)
    except (ValueError,KeyError,TypeError):return
    raise AssertionError('Invalid saved diagnostic accepted')


if __name__=='__main__':
    fixture=json.loads((HERE/'fixture.json').read_text())
    frozen=json.dumps(fixture,sort_keys=True)
    progress=dict(score=78,max_score=100,criterion_version='usable-card-analysis-v1.13')
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);source=root/'input'/'rank.json';target=root/'site'/'report.html';source.parent.mkdir();target.parent.mkdir()
        image=source.parent/'images'/'normal #?.png';image.parent.mkdir()
        image.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII='))
        source.write_text(json.dumps(fixture,ensure_ascii=False));original_hash=hashlib.sha256(source.read_bytes()).hexdigest()
        text=render.render_document(fixture,source,target,progress);HTMLParser().feed(text)
        assert json.dumps(fixture,sort_keys=True)==frozen
        assert text.count('data-pair=')==3 and text.count('class="pair"')==3
        assert text.count('data-gallery=')==3
        assert sum(map(int,re.findall(r'data-gallery-zones="(\d+)"',text)))==5
        assert {html.unescape(z) for z in re.findall(r'data-zone-id="([^"]*)"',text)}=={z['id'] for p in fixture['photos'] for z in p['zones']}
        assert '<A & "group">' not in text and '&lt;A &amp; &quot;group&quot;&gt;' in text
        assert 'defect&lt;&amp;&quot;' in text and '<script' not in text
        assert '../input/images/normal%20%23%3F.png' in text
        assert '사진 없음' in text and '0.416666667' in text and '동점 수 × 0.5' in text
        assert text.count('대상 구역:')==6 and '같은 사진' in text and '다른 fold' in text
        assert 'width="0.000"' not in text and '@media' in text
        completed=subprocess.run([sys.executable,str(HERE/'render.py'),'--input',str(source),'--output',str(target)],capture_output=True,text=True)
        assert completed.returncode==0,completed.stderr
        assert json.loads(completed.stdout)['pairs_displayed']==3 and target.is_file()
        blocked=subprocess.run([sys.executable,str(HERE/'render.py'),'--input',str(source),'--output',str(source)],capture_output=True,text=True)
        assert blocked.returncode!=0 and hashlib.sha256(source.read_bytes()).hexdigest()==original_hash
        tiny=copy.deepcopy(fixture);tiny['photos']=tiny['photos'][:1];tiny.update(rows_count=2,groups_count=1,positive=1,negative=1)
        tiny['total']=dict(pairs=1,strict_inversions=1,ties=0,error_credit=1.,auc=0.,loss_share=1.)
        tiny['buckets']=[dict(tiny['total'],key='same_photo')]+[dict(key=k,pairs=0,strict_inversions=0,ties=0,error_credit=0.,auc=None,loss_share=0.) for k in ('cross_photo_same_fold','cross_fold')]
        tiny['examples']=tiny['examples'][:1]
        assert '해당 없음 (쌍 0개)' in render.render_document(tiny,source,target,progress)
        print('PASS: synthetic paired photos/same-photo zones/cross-fold examples, gallery, tie credit, empty/null AUC, escaping, local relative URL encoding, missing images, responsive layout, CLI and source-overwrite protection')
    for field,value in [('schema_version',2),('new_training_calls',1),('independent',True),('rows_count',99),('positive',99)]:
        bad=copy.deepcopy(fixture);bad[field]=value;reject(bad)
    for change in ('nan','box','truth','credit','auc','share','example','remote'):
        bad=copy.deepcopy(fixture)
        if change=='nan':bad['photos'][0]['zones'][0]['score']=float('nan')
        elif change=='box':bad['photos'][0]['zones'][0]['box'][3]=1.01
        elif change=='truth':bad['photos'][0]['zones'][0]['outcome']='TP'
        elif change=='credit':bad['total']['error_credit']=0
        elif change=='auc':bad['buckets'][0]['auc']=.9
        elif change=='share':bad['buckets'][0]['loss_share']=.9
        elif change=='example':bad['examples'][0]['bucket']='cross_fold'
        elif change=='remote':bad['photos'][0]['image']='https://example.invalid/private.jpg'
        reject(bad)
    counts={p.name:sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)) for n in ast.walk(ast.parse(p.read_text()))) for p in HERE.glob('*.py')}
    assert max(counts.values())<=7
    tree=ast.parse((HERE/'render.py').read_text());functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    calls={name:{n.func.id for n in ast.walk(node) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in functions} for name,node in functions.items()}
    frontier=[('main',0)];maximum=0
    while frontier:
        name,depth=frontier.pop();maximum=max(maximum,depth)
        assert depth<=4
        frontier.extend((callee,depth+1) for callee in calls[name])
    print('PASS: invalid provenance/metrics/labels/box/remote images rejected; original immutable; function counts',counts,'project call transitions',maximum)
