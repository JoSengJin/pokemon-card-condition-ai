"""Script-free manual point notes; drafts are never exact point labels."""
import html
import itertools
import json
import math
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE))
from review import digest,crop_view
from manual import SCOPE,load_reviewed

STATES=(("pending","선택 전",None),("normal","정상","normal"),("defect","결함","defect"),("unknown","모르겠음","unknown"))


CANDIDATE_SCOPE='visible_defect_in_model_candidate_box'
CANDIDATE_KIND='surface_candidate_review_manual_draft'
CANDIDATE_STATES=(("pending","선택 전",None),("normal","결함 없음","normal"),("defect","결함 있음","defect"),("unknown","판단 불가","unknown"))


def draft_response(entry,judgment,candidate=False):
    response=dict(id=entry['id'],image_sha256=entry['row']['image_sha256'],region_target=entry['row']['target'],judgment=judgment,point=None,location_description='')
    if candidate:response.update(candidate_token=entry['candidate']['token'],candidate_box=entry['candidate']['box'])
    return response


def combined_outputs(packet,entries,candidate=False):
    rules=[];outputs=[];states=CANDIDATE_STATES if candidate else STATES;kind=CANDIDATE_KIND if candidate else 'surface_point_review_manual_draft';scope=CANDIDATE_SCOPE if candidate else SCOPE
    for combination in itertools.product(states,repeat=len(entries)):
        suffix="-".join(state[0] for state in combination) or "empty"
        selector="form.review"+"".join(f":has(#c{i+1}-{state[0]}:checked)" for (i,e),state in zip(entries,combination))
        rules.append(selector+f" #result-{suffix}"+"{display:block}")
        responses=[draft_response(e,state[2],candidate) for (i,e),state in zip(entries,combination) if state[2] is not None]
        draft=dict(schema_version=1,kind=kind,scope=scope,packet_id=packet["packet_id"],responses=responses)
        summary=" / ".join(f"{i+1}번 {state[1]}" for (i,e),state in zip(entries,combination)) or "확인할 항목 없음"
        outputs.append(f'<div class="answer" id="result-{suffix}"><p><b>{html.escape(summary)}</b> · 포함 {len(responses)}건</p><textarea aria-label="전체 답 JSON" spellcheck="false">'+html.escape(json.dumps(draft,ensure_ascii=False,indent=2))+'</textarea></div>')
    manual=dict(schema_version=1,kind=kind,scope=scope,packet_id=packet["packet_id"],responses=[draft_response(e,None,candidate) for i,e in entries])
    fallback='<div id="manual-fallback"><p><b>이 뷰어는 선택 결과 묶기를 지원하지 않습니다.</b> 아래 JSON의 judgment에 normal / defect / unknown을 직접 적거나 번호와 판정을 채팅에 보내주세요. null은 미확인입니다. 위에서 고른 값은 이 칸에 자동 반영되지 않습니다.</p><textarea aria-label="직접 입력할 전체 답 JSON" spellcheck="false">'+html.escape(json.dumps(manual,ensure_ascii=False,indent=2))+'</textarea></div>'
    return '@supports selector(:has(*)){#manual-fallback{display:none}'+''.join(rules)+'}', ''.join(outputs)+fallback


def render(packet,indices,out,filename,source_sha,reviewed=None,candidate=False):
    if packet.get("packet_id")!=digest(packet):raise ValueError("Original packet required")
    if not 1<=len(indices)<=5 or len(set(indices))!=len(indices) or any(type(i) is not int or not 0<=i<len(packet["entries"]) for i in indices):raise ValueError("One to five unique cases required")
    reviewed=reviewed or {}
    entries=[(i,packet["entries"][i]) for i in indices if not packet["entries"][i]["completed"] and packet["entries"][i]["id"] not in reviewed]
    esc=html.escape;cards=[]
    for i,e in entries:
        row=e["row"];n=i+1;choices=[]
        for key,label,judgment in (CANDIDATE_STATES if candidate else STATES):
            choices.append(f'<input class="choice" type="radio" name="choice-{n}" id="c{n}-{key}"'+(' checked' if key=='pending' else '')+f'><label class="choice-label" for="c{n}-{key}">{label}</label>')
        raw=crop_view(e,out).replace('원본 픽셀 구역, 클릭 또는 아래 좌표 입력','원본 픽셀 구역, 점선과 무관하게 보이는 결함을 확인하세요');w,h=e['image_size'];l,t,r,b=row['box'];bounds=[math.floor(l*w)/w,math.floor(t*h)/h,math.ceil(r*w)/w,math.ceil(b*h)/h];box=e['candidate']['box']
        x=100*(box[0]-bounds[0])/(bounds[2]-bounds[0]);y=100*(box[1]-bounds[1])/(bounds[3]-bounds[1]);cw=100*(box[2]-box[0])/(bounds[2]-bounds[0]);ch=100*(box[3]-box[1])/(bounds[3]-bounds[1])
        raw=raw.replace('<div class="point-layer">',f'<div class="point-layer"><span class="candidate" style="left:{x}%;top:{y}%;width:{cw}%;height:{ch}%"><span>미확인</span></span>')
        cards.append(f'<article data-index="{i}"><h2>{n}. {esc(row["area"])}</h2><p>기존 구역 정답: <b>{"결함" if row["target"] else "정상"}</b> · 확인 완료, 변경하지 않습니다.</p><input class="overlay-toggle" type="checkbox" id="overlay-{n}"><label for="overlay-{n}">모델 후보 위치 보기 · 미확인, 판정 범위와 무관</label>'+raw+f'<h3>이 확대 사진에서 결함이 보이나요?</h3><p>점선 안팎과 무관하게 이 확대 사진 안에 실제 결함이 하나라도 보이면 결함입니다. 충분히 보이고 결함이 없으면 정상, 판단하기 어려우면 모르겠음입니다. 카드 전체나 점선 위치의 정답으로 해석하지 않습니다.</p>'+''.join(choices)+'</article>')
    rules,outputs=combined_outputs(packet,entries,candidate)
    style='body{font:18px/1.65 system-ui;max-width:850px;margin:auto;padding:16px;color:#17212b}article{border:1px solid #aab;padding:12px;margin:22px 0}img{display:block;max-width:100%;height:auto}.raw-frame{position:relative}.raw-frame>img{width:100%}.point-layer{position:absolute;inset:0;pointer-events:none}.candidate{display:none;position:absolute;border:2px dashed #a50;background:transparent}.candidate span{position:absolute;bottom:100%;background:#fff3c5;color:#743700;white-space:nowrap;left:0;font-size:16px}.overlay-toggle:checked ~ .raw-frame .candidate{display:block}.overlay-toggle{width:22px;height:22px}.choice{position:static;width:22px;height:22px;margin:16px 8px 16px 0}.choice-label{display:inline-block;font-size:18px;min-height:44px;line-height:44px;padding:6px 12px;border:1px solid #aac;margin-right:10px}.choice:checked+label{background:#174ba8;color:white}textarea{box-sizing:border-box;width:100%;height:550px;font:16px/1.5 monospace;user-select:text}summary,a{font-size:18px;min-height:44px;padding:10px;display:block}code{overflow-wrap:anywhere}.answer{display:none}.dock{position:fixed;bottom:0;left:0;right:0;background:#f5f7fb;padding:8px;border-top:1px solid #aab}.dock a{max-width:800px;margin:auto;text-align:center;background:#174ba8;color:white;text-decoration:none}#results{scroll-margin-top:12px}body{padding-bottom:110px}.notice{background:#fff3c5;border:2px solid #b66a00;padding:12px}'
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>마치고 JSON 한 번에 복사</title><style>'+style+rules+'</style><h1>마치고 JSON 한 번에 복사</h1><p class="notice">사진별로 선택한 뒤 아래 고정 버튼「마치고 JSON 보기」를 누르세요. 마지막 JSON 칸 하나를 길게 눌러 전체 선택 → 복사 → 채팅에 붙여넣으면 됩니다. 스크립트 실행은 필요하지 않습니다.</p><p>개발78/100(v1.13) 유지 · 모델 평가 없음. 최대5건 · 원본 먼저, 전체 사진은 펼쳐 보기. 미확인 후보는 정답이 아닙니다.</p><p>아직 안 봤으면 선택 전, 판단이 안 되면 모르겠음으로 두세요. 선택 전 항목은 JSON에서 빠집니다. 이미 받은 답은 다시 묻지 않습니다. 저장된 기존 구역 라벨은 참고 정보이며 이번 선택으로 자동 변경하지 않습니다.</p><p>위치 설명은 마지막 JSON의 location_description 빈 따옴표 안에 한 번만 적으세요. 좌표를 모르면 point:null을 유지하세요. 이 초안은 정밀 좌표 정답으로 자동 저장되지 않습니다. 사진 터치 좌표 계산·자동 저장은 지원하지 않습니다.</p><form class="review">'+''.join(cards)+'<section id="results"><h2>전체 답 JSON · 한 번만 복사</h2><p>아래 요약이 선택한 내용과 같은지 확인하세요. JSON 칸 전체를 길게 눌러 복사하세요. 필요하면 location_description에 위치를 적으세요. 예: &quot;가운데 위 가로 긁힘&quot;. 판정을 다시 바꾸면 다른 초안이 표시되며 적어 둔 설명은 자동으로 옮겨지지 않습니다. 선택을 마친 뒤 설명을 적어주세요.</p>'+outputs+'</section></form><div class="dock"><a href="#results">마치고 JSON 보기 · 한 번에 복사</a></div>'+f'<p>packet <code>{packet["packet_id"]}</code><br>source <code>{esc(source_sha)}</code> · 실제 휴대폰 조작 미확인. 새로고침 전 답을 복사하세요.</p></html>'
    if candidate:
        page=page.replace('마치고 JSON 한 번에 복사','점선 안 결함 확인 · 마치고 JSON 복사').replace('이 확대 사진에서 결함이 보이나요?','점선 안에 실제 결함이 있나요?')
        page=page.replace('점선 안팎과 무관하게 이 확대 사진 안에 실제 결함이 하나라도 보이면 결함입니다. 충분히 보이고 결함이 없으면 정상, 판단하기 어려우면 모르겠음입니다. 카드 전체나 점선 위치의 정답으로 해석하지 않습니다.','이번에는 점선 안만 확인합니다. 실제 손상이 보이면 결함 있음, 충분히 보이는데 손상이 없으면 결함 없음, 흐리거나 너무 작으면 판단 불가입니다. 점선 밖의 결함은 이번 답에 포함하지 않습니다. 점선은 최고 점수 후보 하나이며 모든 결함 위치를 뜻하지 않습니다.')
        page=page.replace('모델 후보 위치 보기 · 미확인, 판정 범위와 무관','미확인 모델 후보 점선 보기 · 이 안만 확인').replace('class="overlay-toggle" type="checkbox"','class="overlay-toggle" type="checkbox" checked')
        page=page.replace('점선과 무관하게 보이는 결함을 확인하세요','점선 안에 실제 결함이 있는지 확인하세요').replace('판단이 안 되면 모르겠음으로 두세요','판단이 안 되면 판단 불가로 두세요')
        page=page.replace('normal / defect / unknown','normal(점선 안 결함 없음) / defect(점선 안 결함 있음) / unknown(판단 불가)')
    with (Path(out)/filename).open('x') as stream:stream.write(page)
    return len(entries)


if __name__=='__main__':
    out=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'artifacts/mobile-followup-review-20261110';out.mkdir(exist_ok=True)
    packet=json.loads((ROOT/'artifacts/mobile-point-review-20261110/packet.json').read_text());sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    reviewed=load_reviewed(packet,ROOT/'artifacts/mobile-human-review-ledger-20261110')
    indices=[i for i,e in enumerate(packet['entries']) if not e['completed'] and e['id'] not in reviewed][:5]
    if not indices:raise SystemExit('No unreviewed judgments remain')
    count=render(packet,indices,out,'review-next.html',sha,reviewed)
    print(json.dumps(dict(cases=count,indices=indices,reviewed_skipped=len(reviewed),source_sha=sha,packet_id=packet['packet_id'],scripts=0,new_labels=0,phone_verified=False)))
