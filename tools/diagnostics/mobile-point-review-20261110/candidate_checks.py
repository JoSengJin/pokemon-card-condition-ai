"""Static candidate scope/identity/export checks; not phone/model performance."""
import ast
import copy
import html
import itertools
import json
from pathlib import Path
import re
import tempfile
from candidate import validate_candidates
from scriptfree import ROOT,HERE,render,CANDIDATE_KIND,CANDIDATE_SCOPE,CANDIDATE_STATES
from scriptfree_checks import Audit
from review import digest
from manual import validate_manual


def rejects(fn,*args):
    try:fn(*args)
    except ValueError:return
    raise AssertionError('Invalid/cross-scope evidence accepted')


if __name__=='__main__':
    source=json.loads((ROOT/'artifacts/mobile-point-review-20261110/packet.json').read_text());packet=copy.deepcopy(source);packet['entries']=packet['entries'][10:15];packet['packet_id']=digest(packet)
    with tempfile.TemporaryDirectory() as temp:
        out=Path(temp);assert render(packet,list(range(5)),out,'candidate.html','synthetic-contract-check',candidate=True)==5
        text=(out/'candidate.html').read_text();a=Audit();a.feed(text)
        assert len(a.images)==10 and all(src.startswith('data:image/') for src in a.images) and 'script' not in a.tags and 'svg' not in a.tags
        assert text.count('class="overlay-toggle" type="checkbox" checked')==5 and '점선 안팎과 무관하게' not in text and '판정 범위와 무관' not in text
        assert '점선 밖의 결함은 이번 답에 포함하지 않습니다' in text and '결함 있음' in text and '결함 없음' in text and '판단 불가' in text
        rows=re.findall(r'<div class="answer" id="result-([^"]+)"><p>.*?</p><textarea[^>]*>(.*?)</textarea></div>',text,re.S);assert len(rows)==1024
        example=None
        for (suffix,raw),combination in zip(rows,itertools.product(CANDIDATE_STATES,repeat=5)):
            answers=json.loads(html.unescape(raw));validate_candidates(packet,answers)
            assert answers['kind']==CANDIDATE_KIND and answers['scope']==CANDIDATE_SCOPE and suffix=='-'.join(s[0] for s in combination)
            assert len(answers['responses'])==sum(s[2] is not None for s in combination)
            for e,state in zip(packet['entries'],combination):
                matches=[r for r in answers['responses'] if r['id']==e['id']]
                if state[2] is None:assert matches==[]
                else:
                    assert len(matches)==1 and matches[0]['judgment']==state[2] and matches[0]['candidate_token']==e['candidate']['token'] and matches[0]['candidate_box']==e['candidate']['box'] and matches[0]['point'] is None
            if suffix=='defect-defect-defect-defect-defect':example=answers
        rejects(validate_manual,packet,example)
        for key,value in [('scope','visible_defect_in_displayed_crop'),('kind','surface_point_review_manual_draft'),('packet_id','other')]:
            bad=copy.deepcopy(example);bad[key]=value;rejects(validate_candidates,packet,bad)
        for key,value in [('candidate_token',True),('candidate_token',-1),('candidate_box',[0,0,0,0]),('image_sha256','other'),('region_target',True),('point',dict(x=.1,y=.1))]:
            bad=copy.deepcopy(example);bad['responses'][0][key]=value;rejects(validate_candidates,packet,bad)
        bad=copy.deepcopy(example);bad['responses'].append(bad['responses'][0]);rejects(validate_candidates,packet,bad)
        assert len(text.encode())<9*1024*1024
    counts={name:sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)) for n in ast.walk(ast.parse((HERE/name).read_text()))) for name in ('scriptfree.py','candidate.py','candidate_checks.py')};assert max(counts.values())<=7
    print('PASS: all1024 candidate-box JSON combinations bind packet/photo/token/box;pending omitted/unknown distinct;crop validator rejects;overlay visible;explicit inside-only wording;tamper rejected;10 native images/noJS;no labels/model calls')
    print(json.dumps(dict(function_counts=counts,phone_render_verified=False)))
