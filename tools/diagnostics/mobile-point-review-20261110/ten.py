"""Ten candidate judgments in one script-free file with one visible JSON copy field."""
import html
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import textwrap
from candidate import validate_candidates
from manual import load_reviewed
from review import digest,crop_view
from scriptfree import ROOT,CANDIDATE_KIND,CANDIDATE_SCOPE,CANDIDATE_STATES,draft_response


def combined_editor(packet,entries):
    envelope=dict(schema_version=1,kind=CANDIDATE_KIND,scope=CANDIDATE_SCOPE,packet_id=packet['packet_id'],responses=[])
    head,tail=json.dumps(envelope,ensure_ascii=False,indent=2).replace('"responses": []','"responses": [\n\x00\n  ]').split('\x00')
    pieces=[html.escape(head,quote=False)];rules=[]
    for position,(i,e) in enumerate(entries):
        for key,label,judgment in CANDIDATE_STATES:
            value=textwrap.indent(json.dumps(draft_response(e,judgment,True),ensure_ascii=False,indent=2),'    ')+(',' if position<len(entries)-1 else '')+'\n'
            pieces.append(f'<span class="response-variant" id="json-{position}-{key}" data-position="{position}" data-choice="{key}">'+html.escape(value,quote=False)+'</span>')
            rules.append(f'form.review:has(#c{i+1}-{key}:checked) #json-{position}-{key}'+'{display:inline}')
    pieces.append(html.escape(tail,quote=False))
    envelope['responses']=[draft_response(e,None,True) for i,e in entries]
    fallback='<div class="manual-fallback"><p><b>이 뷰어는 선택 결과 연결을 지원하지 않습니다.</b> 아래 칸에는 선택이 자동 반영되지 않습니다. judgment의 null을 normal(점선 안 결함 없음),defect(점선 안 결함 있음),unknown(판단 불가)으로 직접 바꾸거나 번호별 판정을 채팅에 적어주세요.</p><textarea aria-label="수동 전체 JSON">'+html.escape(json.dumps(envelope,ensure_ascii=False,indent=2),quote=False)+'</textarea></div>'
    return '@supports selector(:has(*)){.automatic-json{display:block}.manual-fallback{display:none}'+''.join(rules)+'}', '<div id="copy-json" class="automatic-json" contenteditable="true" role="textbox" aria-label="전체 10건 JSON 복사 칸" aria-multiline="true" spellcheck="false" autocapitalize="off">'+''.join(pieces)+'</div>'+fallback


def render_ten(packet,indices,out,filename,source_sha):
    if packet.get('packet_id')!=digest(packet):raise ValueError('Original packet required')
    if not 1<=len(indices)<=10 or len(set(indices))!=len(indices) or any(type(i) is not int or not 0<=i<len(packet['entries']) or packet['entries'][i]['completed'] for i in indices):raise ValueError('One to ten uncompleted unique cases required')
    entries=[(i,packet['entries'][i]) for i in indices];cards=[];photos={};esc=html.escape
    for i,e in entries:
        row=e['row'];n=i+1;raw=crop_view(e,out);raw,full=raw.split('<details class="original-context">',1);photo=row['image_sha256']
        if photo not in photos:
            anchor=f'photo-{len(photos)+1}';photos[photo]=anchor;context=f'<details class="original-context" id="{anchor}">'+full
        else:context=f'<p><a href="#{photos[photo]}">같은 원사진 전체 보기 · 이동 후 펼치기</a></p>'
        raw=raw.replace('원본 픽셀 구역, 클릭 또는 아래 좌표 입력','점선 안에 실제 결함이 있는지 확인하세요')
        w,h=e['image_size'];l,t,r,b=row['box'];bounds=[math.floor(l*w)/w,math.floor(t*h)/h,math.ceil(r*w)/w,math.ceil(b*h)/h];box=e['candidate']['box']
        x=100*(box[0]-bounds[0])/(bounds[2]-bounds[0]);y=100*(box[1]-bounds[1])/(bounds[3]-bounds[1]);cw=100*(box[2]-box[0])/(bounds[2]-bounds[0]);ch=100*(box[3]-box[1])/(bounds[3]-bounds[1])
        raw=raw.replace('<div class="point-layer">',f'<div class="point-layer"><span class="candidate" style="left:{x}%;top:{y}%;width:{cw}%;height:{ch}%"><span>미확인</span></span>')
        choices=''.join(f'<label><input type="radio" id="c{n}-{key}" name="choice-{n}"'+(' checked' if key=='pending' else '')+f'><span>{label}</span></label>' for key,label,judgment in CANDIDATE_STATES)
        cards.append(f'<article data-index="{i}"><h2>{n}. {esc(row["area"])}</h2><input class="overlay-toggle" id="overlay-{n}" type="checkbox" checked><label class="overlay-label" for="overlay-{n}">미확인 모델 후보 보기 · 점선 켜기/끄기</label>'+raw+context+'<h3>점선 안에 실제 결함이 있나요?</h3><p>점선 안만 확인합니다. 손상이 보이면 결함 있음, 충분히 보이고 없으면 결함 없음, 너무 작거나 흐리면 판단 불가입니다. 점선 밖 결함은 이번 답에 포함하지 않습니다.</p><div class="choices">'+choices+'</div></article>')
    rules,output=combined_editor(packet,entries)
    style='body{font:18px/1.6 system-ui;max-width:850px;margin:auto;padding:16px 16px 110px}article{border:1px solid #aab;margin:20px 0;padding:12px}img{display:block;max-width:100%;height:auto}.raw-frame{position:relative}.raw-frame>img{width:100%}.point-layer{position:absolute;inset:0;pointer-events:none}.candidate{display:none;position:absolute;border:2px dashed #b65a00}.overlay-toggle:checked~.raw-frame .candidate{display:block}.overlay-toggle{width:22px;height:22px}.overlay-label{display:inline-block;font-size:18px;min-height:44px;padding:8px}.candidate span{position:absolute;bottom:100%;right:0;white-space:nowrap;font-size:16px;background:#fff3c5;color:#743700}.choices{display:flex;flex-wrap:wrap;gap:8px}.choices label{display:flex;align-items:center;min-height:48px;gap:8px;border:1px solid #abc;padding:8px}.choices input{width:22px;height:22px}.choices input:checked+span{background:#174ba8;color:white;padding:5px}.automatic-json{display:none;white-space:pre-wrap;overflow-wrap:anywhere;user-select:text;border:2px solid #174ba8;padding:12px;font:16px/1.5 monospace;min-height:200px}.response-variant{display:none}textarea{width:100%;height:500px;box-sizing:border-box;font-size:16px;user-select:text}summary,a{display:block;font-size:18px;padding:10px;min-height:44px}.dock{position:fixed;bottom:0;left:0;right:0;background:#f5f7fb;padding:8px;border-top:1px solid #aab}.dock a{max-width:800px;margin:auto;text-align:center;background:#174ba8;color:white;text-decoration:none}code{overflow-wrap:anywhere}#results{scroll-margin-top:12px}'
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>10건 한 번에 · 점선 안 확인</title><style>'+style+rules+'</style><h1>10건 한 파일 · JSON 한 번 복사</h1><p>점선 안의 결함 유무를 선택하고 하단「마치고 전체 JSON 보기」를 누르세요. 마지막 파란 테두리 결과 칸 안을 길게 눌러 전체 선택 → 복사 → 채팅에 한 번 붙여넣으세요.</p><p>선택 전은 judgment:null이며 정답으로 저장하지 않습니다. 판단이 어려우면 판단 불가입니다. 정밀 손상점이나 카드 전체 판정으로 해석하지 않습니다. 기존 답은 유지하며 이미 답한 항목은 제외했습니다.</p><p>스크립트·서버 없이 동작합니다. 동일 원사진은 화질 그대로 한 번만 내장했습니다. 같은 원사진 링크는 앞의 접힌 사진으로 이동합니다. 개발78/100(v1.13) 유지 · 새학습/추론 없음.</p><form class="review">'+''.join(cards)+'<section id="results"><h2>전체 JSON · 여기서 한 번만 복사</h2><p>이 칸 안을 길게 눌러 전체 선택·복사하세요. 선택을 마친 뒤 필요하면 location_description에 설명을 적으세요. 다시 선택하면 그 항목의 다른 초안이 표시되며 설명이 자동 이동하지 않습니다. 입력은 자동 저장되지 않습니다.</p>'+output+'</section></form><div class="dock"><a href="#results">마치고 전체 JSON 보기 · 10건 한 번에</a></div><p>실제 폰의 결과 칸 선택·복사는 미확인입니다. 복사한 내용이 JSON인지 확인한 뒤 보내주세요.</p><p>검증 소스 <code>'+esc(source_sha)+'</code></p></html>'
    with (Path(out)/filename).open('x') as stream:stream.write(page)
    return dict(cases=len(entries),unique_full_photos=len(photos),bytes=len(page.encode()))


if __name__=='__main__':
    packet=json.loads((ROOT/'artifacts/mobile-point-review-20261110/packet.json').read_text());reviewed=set(load_reviewed(packet,ROOT/'artifacts/mobile-human-review-ledger-20261110'))
    for path in (ROOT/'artifacts/mobile-candidate-human-ledger-20261110').glob('*.json'):
        receipt=json.loads(path.read_text());validate_candidates(packet,receipt['answers'])
        if hashlib.sha256(receipt['source_text'].encode()).hexdigest()!=receipt['source_answers_sha256'] or json.loads(receipt['source_text'])!=receipt['answers']:raise ValueError('Candidate receipt source changed')
        reviewed.update(r['id'] for r in receipt['answers']['responses'] if r['judgment'] is not None)
    indices=[i for i,e in enumerate(packet['entries']) if not e['completed'] and e['id'] not in reviewed][:10]
    out=ROOT/'artifacts/mobile-ten-onefile-20261110';out.mkdir(exist_ok=True);sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();result=render_ten(packet,indices,out,'review-10.html',sha);result.update(indices=indices,source_sha=sha,phone_copy_verified=False)
    with (out/'manifest.json').open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result))
