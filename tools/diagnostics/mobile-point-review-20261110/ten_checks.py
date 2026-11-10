"""Synthetic visible-fragment serialization checks; native mobile clipboard is unverified."""
import ast
import copy
import html
import json
from pathlib import Path
import random
import re
import tempfile
from ten import render_ten
from scriptfree import ROOT,HERE,CANDIDATE_STATES
from scriptfree_checks import Audit
from review import digest,crop_view
from candidate import validate_candidates


if __name__=='__main__':
    source=json.loads((ROOT/'artifacts/mobile-point-review-20261110/packet.json').read_text());packet=copy.deepcopy(source);packet['entries']=packet['entries'][20:30];packet['packet_id']=digest(packet)
    with tempfile.TemporaryDirectory() as temp:
        out=Path(temp);result=render_ten(packet,list(range(10)),out,'ten.html','synthetic-contract-check');text=(out/'ten.html').read_text();audit=Audit();audit.feed(text)
        assert result['cases']==10 and result['unique_full_photos']==6 and len(audit.images)==16 and len(audit.radios)==40 and sum('checked' in r for r in audit.radios)==10
        assert 'script' not in audit.tags and 'svg' not in audit.tags and all(src.startswith('data:image/') for src in audit.images)
        expected=[];seen=set()
        for entry in packet['entries']:
            old=Audit();old.feed(crop_view(entry,out));expected.append(old.images[0])
            if entry['row']['image_sha256'] not in seen:expected.append(old.images[1]);seen.add(entry['row']['image_sha256'])
        assert audit.images==expected and len(set(audit.ids))==len(audit.ids)
        articles=re.findall(r'<article data-index="[0-9]+">(.*?)</article>',text,re.S);assert len(articles)==10
        for n,article in enumerate(articles,1):
            checkbox=f'<input class="overlay-toggle" id="overlay-{n}" type="checkbox" checked>'
            assert checkbox in article and f'for="overlay-{n}"' in article and article.index(checkbox)<article.index('<div class="raw-frame"')
        assert '.candidate{display:none;' in text and '.overlay-toggle:checked~.raw-frame .candidate{display:block}' in text
        assert '미확인 모델 후보 보기 · 점선 켜기/끄기' in text
        assert text.count('id="copy-json"')==1 and 'contenteditable="true"' in text and 'role="textbox"' in text
        content=re.search(r'<div id="copy-json"[^>]*>(.*?)</div>',text,re.S)[1]
        matches=list(re.finditer(r'<span class="response-variant" id="json-([0-9]+)-([^"]+)" data-position="[0-9]+" data-choice="[^"]+">(.*?)</span>',content,re.S));assert len(matches)==40
        head=html.unescape(content[:matches[0].start()]);tail=html.unescape(content[matches[-1].end():]);fragments={(int(m[1]),m[2]):html.unescape(m[3]) for m in matches}
        keys=[s[0] for s in CANDIDATE_STATES];vectors=[(key,)*10 for key in keys]
        for position in range(10):
            for key in keys:
                vector=['pending']*10;vector[position]=key;vectors.append(tuple(vector))
        rng=random.Random(42)
        vectors.extend(tuple(rng.choice(keys) for i in range(10)) for _ in range(32))
        for vector in vectors:
            answer=json.loads(head+''.join(fragments[(i,key)] for i,key in enumerate(vector))+tail);validate_candidates(packet,answer)
            assert len(answer['responses'])==10
            for i,(response,key) in enumerate(zip(answer['responses'],vector)):
                assert response['id']==packet['entries'][i]['id'] and response['judgment']==dict((s[0],s[2]) for s in CANDIDATE_STATES)[key]
                assert f'form.review:has(#c{i+1}-{key}:checked) #json-{i}-{key}'+'{display:inline}' in text
        fallback=json.loads(html.unescape(re.search(r'<textarea aria-label="수동 전체 JSON">(.*?)</textarea>',text,re.S)[1]));validate_candidates(packet,fallback)
        assert all(r['judgment'] is None for r in fallback['responses']) and '.automatic-json{display:none' in text and '@supports selector(:has(*))' in text
        assert '선택 전은 judgment:null이며 정답으로 저장하지 않습니다' in text and '점선 밖 결함은 이번 답에 포함하지 않습니다' in text and '점선 안만 확인합니다' in text
        assert result['bytes']<7_000_000
    counts={name:sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)) for n in ast.walk(ast.parse((HERE/name).read_text()))) for name in ('ten.py','ten_checks.py')};assert max(counts.values())<=7
    print('PASS:10 native overlay checkboxes/label bindings/defaulton/CSS hide-show;10 cases/one editable JSON field/40 native choices;76 choice vectors yield valid bound candidateJSON;null pending/unknown preserved;CSS mapping/support fallback;16 native image URIs exact/6 shared fullphotos;noJS/SVG;under7MB')
    print(json.dumps(dict(function_counts=counts,actual_phone_selection_and_copy_verified=False)))
