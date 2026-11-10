"""Script-free manual point notes; drafts are never exact point labels."""
import html
import json
import math
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE))
from review import digest,crop_view

STATES=(("pending","선택 전",None),("normal","정상","normal"),("defect","결함","defect"),("unknown","모르겠음","unknown"))


def render(packet,indices,out,filename,source_sha):
    if packet.get("packet_id")!=digest(packet):raise ValueError("Original packet required")
    if not 1<=len(indices)<=5 or len(set(indices))!=len(indices) or any(type(i) is not int or not 0<=i<len(packet["entries"]) for i in indices):raise ValueError("One to five unique cases required")
    entries=[(i,packet["entries"][i]) for i in indices if not packet["entries"][i]["completed"]]
    esc=html.escape;rules=[];cards=[]
    for i,e in entries:
        row=e["row"];n=i+1;choices=[];outputs=[]
        for key,label,judgment in STATES:
            choices.append(f'<input class="choice" type="radio" name="choice-{n}" id="c{n}-{key}"'+(' checked' if key=='pending' else '')+f'><label class="choice-label" for="c{n}-{key}">{label}</label>')
            draft=dict(schema_version=1,kind="surface_point_review_manual_draft",packet_id=packet["packet_id"],responses=[dict(id=e["id"],image_sha256=row["image_sha256"],region_target=row["target"],judgment=judgment,point=None,location_description="")])
            outputs.append(f'<div class="answer result-{key}"><h3>{label} · 수동 입력 JSON</h3><p>이 칸은 자동 저장되지 않습니다.</p><textarea aria-label="{n}번 {label} 수동 답" spellcheck="false">'+esc(json.dumps(draft,ensure_ascii=False,indent=2))+'</textarea></div>')
            rules.append(f'#c{n}-{key}:checked ~ .answers .result-{key}'+'{display:block}')
        raw=crop_view(e,out).replace('원본 픽셀 구역, 클릭 또는 아래 좌표 입력','원본 픽셀 구역, 위치를 문장으로 설명하세요');w,h=e['image_size'];l,t,r,b=row['box'];bounds=[math.floor(l*w)/w,math.floor(t*h)/h,math.ceil(r*w)/w,math.ceil(b*h)/h];box=e['candidate']['box']
        x=100*(box[0]-bounds[0])/(bounds[2]-bounds[0]);y=100*(box[1]-bounds[1])/(bounds[3]-bounds[1]);cw=100*(box[2]-box[0])/(bounds[2]-bounds[0]);ch=100*(box[3]-box[1])/(bounds[3]-bounds[1])
        raw=raw.replace('<div class="point-layer">',f'<div class="point-layer"><span class="candidate" style="left:{x}%;top:{y}%;width:{cw}%;height:{ch}%"><span>미확인</span></span>')
        cards.append(f'<article data-index="{i}"><h2>{n}. {esc(row["area"])}</h2><p>기존 구역 정답: <b>{"결함" if row["target"] else "정상"}</b> · 확인 완료, 변경하지 않습니다.</p><input class="overlay-toggle" type="checkbox" id="overlay-{n}"><label for="overlay-{n}">미확인 모델 후보 겹쳐 보기</label>'+raw+f'<h3>새로 설명할 위치의 판정</h3><p>아래 선택은 기존 구역 정답을 다시 묻는 것이 아닙니다. 확인한 위치만 설명하세요. 위치를 못 찾았다고 정상을 선택하지 마세요.</p>'+''.join(choices)+f'<p><a href="#answers-{n}">답 JSON 보기</a></p><div class="answers" id="answers-{n}"><p><b>수동 답 초안</b>: 선택하면 해당 초안이 보입니다. location_description의 빈 따옴표 안에 위치를 적고, 이 칸 전체를 길게 눌러 복사해 채팅에 붙여넣으세요. 예: &quot;확대 사진 가운데보다 조금 위의 가로 긁힘&quot;. 좌표를 모르면 point:null을 유지하세요. 문장으로 &quot;{n}번: 결함, 가운데 위 가로 긁힘&quot;처럼 답해도 됩니다.</p>'+''.join(outputs)+'</div></article>')
    style='body{font:18px/1.65 system-ui;max-width:850px;margin:auto;padding:16px;color:#17212b}article{border:1px solid #aab;padding:12px;margin:22px 0}img{display:block;max-width:100%;height:auto}.raw-frame{position:relative}.raw-frame>img{width:100%}.point-layer{position:absolute;inset:0;pointer-events:none}.candidate{display:none;position:absolute;border:2px dashed #a50;background:transparent}.candidate span{position:absolute;bottom:100%;background:#fff3c5;color:#743700}.overlay-toggle:checked ~ .raw-frame .candidate{display:block}.overlay-toggle{width:22px;height:22px}.choice{position:static;width:22px;height:22px;margin:16px 8px 16px 0}.choice-label{display:inline-block;font-size:18px;min-height:44px;line-height:44px;padding:6px 12px;border:1px solid #aac;margin-right:10px}.choice:checked+label{background:#174ba8;color:white}textarea{box-sizing:border-box;width:100%;height:390px;font:16px/1.5 monospace;user-select:text}summary,a{font-size:18px;min-height:44px;padding:10px;display:block}code{overflow-wrap:anywhere}.answer{display:none}.notice{background:#fff3c5;border:2px solid #b66a00;padding:12px}'
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>스크립트 없는 모바일 답 전달</title><style>'+style+''.join(rules)+'</style><h1>스크립트 없는 답 전달</h1><p class="notice">입력 준비를 기다릴 필요가 없습니다. 일반 선택 버튼과 복사할 텍스트만 사용합니다. 사진 터치 좌표 계산·자동 기록·자동 저장은 지원하지 않습니다.</p><p>개발78/100(v1.13) 유지 · 모델 평가 없음. 최대5건 · 원본 먼저, 전체 사진은 펼쳐 보기. 사진과 후보는 이전 묶음 그대로입니다. 후보는 미확인입니다.</p><p>선택 → 답 JSON 보기 → location_description에 위치를 직접 적기 → 칸 전체를 길게 눌러 복사 → 이 채팅에 붙여넣기. 선택을 바꾸면 다른 초안이 보이며 이전에 적은 설명은 자동으로 옮겨지지 않습니다. 사진 판단이 안 되면 모르겠음, 아직 안 봤으면 선택 전 그대로 두세요.</p><p>이 JSON은 수동 설명 초안이며 정밀 좌표 정답으로 자동 저장하지 않습니다. 설명은 원문으로 보존하고 좌표가 불명확하면 별도 확인합니다. 미확인을 정상/결함으로 추정하지 않습니다.</p>'+''.join(cards)+f'<p>packet <code>{packet["packet_id"]}</code><br>source <code>{esc(source_sha)}</code> · 실제 휴대폰 조작 미확인. 새로고침 전 답을 복사하세요.</p></html>'
    with (Path(out)/filename).open('x') as stream:stream.write(page)
    return len(entries)


if __name__=='__main__':
    out=ROOT/'artifacts/mobile-scriptfree-fallback-20261110';out.mkdir(exist_ok=True)
    packet=json.loads((ROOT/'artifacts/mobile-point-review-20261110/packet.json').read_text());sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    count=render(packet,list(range(5,10)),out,'review-02-scriptfree.html',sha)
    print(json.dumps(dict(cases=count,source_sha=sha,packet_id=packet['packet_id'],scripts=0,new_labels=0,phone_verified=False)))
