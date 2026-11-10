"""Explicit human surface-point judgments; completed region labels stay read-only."""
import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/diagnostics/surface-grounding-20261110'))
from report import crop_view


def digest(packet):
    return hashlib.sha256(json.dumps({k:v for k,v in packet.items() if k!='packet_id'},sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def make_packet(source):
    from audit import packet_digest
    if source.get('packet_id')!=packet_digest(source):raise ValueError('Canonical source packet changed')
    entries=[]
    for old in source['entries']:
        if not old['selected']:continue
        e=dict(old);top=old['evidence']['top_index'];e['id']=old['row']['id']+'/point-review/'+str(top)
        e['completed']=bool(old['known_points']);e['candidate']=dict(state='unreviewed',token=top,box=old['evidence']['top_geometry']['box'])
        entries.append(e)
    p=dict(schema_version=1,kind='surface_point_review_packet',source_packet_id=source['packet_id'],entries=entries,region_labels_read_only=True,automatic_training=False)
    p['packet_id']=digest(p);return p


def validate(packet,answers):
    if not isinstance(packet,dict) or packet.get('packet_id')!=digest(packet) or packet.get('region_labels_read_only') is not True:raise ValueError('Original point-review packet required')
    if not isinstance(answers,dict) or set(answers)!={'schema_version','kind','packet_id','responses'} or type(answers['schema_version']) is not int or answers['schema_version']!=1 or answers['kind']!='surface_point_review_answers' or answers['packet_id']!=packet['packet_id'] or not isinstance(answers['responses'],list):raise ValueError('Explicit point-review answer schema required')
    index={e['id']:e for e in packet['entries']};seen=set()
    for r in answers['responses']:
        if not isinstance(r,dict) or set(r)!={'id','image_sha256','region_target','judgment','point','note'} or not isinstance(r['id'],str) or r['id'] not in index or r['id'] in seen:raise ValueError('Unknown/duplicate response or label override')
        seen.add(r['id']);e=index[r['id']];row=e['row']
        if e['completed'] or r['image_sha256']!=row['image_sha256'] or type(r['region_target']) is not int or r['region_target']!=row['target'] or not isinstance(r['note'],str):raise ValueError('Completed evidence/region truth/image cannot change')
        if r['judgment']=='unknown':
            if r['point'] is not None:raise ValueError('Unknown is not a point truth')
        elif r['judgment'] in ('normal','defect'):
            point=r['point']
            if not isinstance(point,dict) or set(point)!={'x','y'} or any(type(point[k]) not in (int,float) or not math.isfinite(point[k]) for k in ('x','y')):raise ValueError('Explicit finite human point required')
            l,t,rr,b=row['box']
            if not l<=point['x']<=rr or not t<=point['y']<=b:raise ValueError('Point outside confirmed region bounds')
        else:raise ValueError('Unselected judgment is not an answer')
    return answers


def ingest(packet_path,answer_path,output):
    packet=json.loads(Path(packet_path).read_text());answers=json.loads(Path(answer_path).read_text());validate(packet,answers)
    index={e['id']:e for e in packet['entries']};known=[];conflicts=[]
    for r in answers['responses']:
        if r['judgment']=='unknown':continue
        truth=int(r['judgment']=='defect');entry=index[r['id']];box=entry['candidate']['box'];point=r['point']
        known.append(dict(id=r['id'],point=point,truth=truth,source='explicit_human_record',in_model_support=box[0]<=point['x']<=box[2] and box[1]<=point['y']<=box[3]))
        if truth==1 and r['region_target']==0:conflicts.append(r['id'])
    record=dict(kind='validated_surface_point_review',answers=answers,human_point_labels=known,unknown_ids=[r['id'] for r in answers['responses'] if r['judgment']=='unknown'],
        conflicts_with_existing_normal_region=conflicts,region_labels_changed=False,training_applied=False,causal_attribution_proven=False,
        pending_ids=[e['id'] for e in packet['entries'] if not e['completed'] and e['id'] not in {r['id'] for r in answers['responses']}],
        source_answers_sha256=hashlib.sha256(Path(answer_path).read_bytes()).hexdigest())
    with Path(output).open('x') as stream:json.dump(record,stream,ensure_ascii=False,indent=2,allow_nan=False)
    return record


def render(packet,indices,out,filename,source_sha):
    if not 1<=len(indices)<=5 or len(set(indices))!=len(indices) or any(type(i) is not int or not 0<=i<len(packet['entries']) for i in indices):raise ValueError('One to five unique cases required')
    out=Path(out);esc=html.escape
    page="""<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>모바일 위치 확인</title><style>body{font:17px/1.6 system-ui;max-width:850px;padding:16px;margin:auto;color:#17212b}article{border:1px solid #bbc;padding:12px;margin:20px 0}img{display:block;max-width:100%;height:auto}.raw-frame{position:relative;width:100%}.raw-frame>img{width:100%}img[data-locate]{touch-action:pan-y pinch-zoom;user-select:none;-webkit-user-drag:none}#input-status{padding:12px;border:2px solid #b66a00;background:#fff5d6}#input-status[data-state="ready"]{border-color:#198038;background:#e7f7ec}#input-status[data-state="error"]{border-color:#ba1b1b;background:#ffecec}.point-layer{position:absolute;inset:0;pointer-events:none}.new-point,.known-point{position:absolute;width:12px;height:12px;border:2px solid white;border-radius:50%;transform:translate(-50%,-50%);background:#6c00d9}.known-point{background:#008cff}.candidate{position:absolute;border:2px dashed #b95c00;color:#743700;font-size:16px;white-space:nowrap}.candidate>span{position:absolute;bottom:100%;background:#fff3c5}button,input,textarea,select{font-size:18px}input[type="checkbox"]{width:20px;height:20px}button{min-height:44px;min-width:72px;padding:8px;margin:5px}button[aria-pressed="true"]{background:#174ba8;color:white}summary{cursor:pointer;font-size:17px;padding:8px}textarea{display:block;box-sizing:border-box;width:100%;min-height:100px;user-select:text}label{display:block;margin:10px 0}#download{display:inline-block;font-size:18px;min-height:44px;padding:8px;color:#174ba8}#download[aria-disabled="true"]{pointer-events:none;opacity:.4}code{overflow-wrap:anywhere}#message{white-space:pre-wrap;color:#8c2b00}[hidden]{display:none!important}</style><h1>원본 위치 확인</h1>"""
    page+=f'<p>개발78/100(v1.13) 유지 · 이 파일 {len(indices)}건. 기존 구역 정답은 이미 확인됐으므로 다시 묻지 않습니다. <strong>새로 찍은 위치</strong>만 정상/결함/모르겠음으로 기록하세요. 표면 결함 대상이며 모델 제안은 미확인입니다.</p><p>각 항목「기록」→「JSON 복사」또는「JSON 파일 저장」→이 채팅에 붙여넣거나 첨부하세요. 일부만 확인해도 됩니다. 새로고침 전 보관이 필요합니다.</p><label>저장한 답 이어보기 <input id="resume" type="file" accept=".json,application/json"></label><p>기록 <span id="answered">0</span>건</p><p id="input-status" role="status" aria-live="polite" data-state="pending">입력 준비 전 · 이 문구가 계속 보이면 현재 뷰어에서 스크립트가 실행되지 않았거나 초기화에 실패한 상태입니다. 아직 기록하지 마세요.</p><button id="copy" type="button" disabled data-requires-js>JSON 복사</button><a id="download" aria-disabled="true" tabindex="-1">JSON 파일 저장</a><p id="message" role="status" aria-live="polite"></p><label>길게 눌러 복사할 JSON<textarea id="export" readonly></textarea></label>'
    for i in indices:
        e=packet['entries'][i];row=e['row'];w,h=e['image_size'];l,t,rr,b=row['box'];bounds=[math.floor(l*w)/w,math.floor(t*h)/h,math.ceil(rr*w)/w,math.ceil(b*h)/h];candidate=e['candidate']['box']
        x=100*(candidate[0]-bounds[0])/(bounds[2]-bounds[0]);y=100*(candidate[1]-bounds[1])/(bounds[3]-bounds[1]);cw=100*(candidate[2]-candidate[0])/(bounds[2]-bounds[0]);ch=100*(candidate[3]-candidate[1])/(bounds[3]-bounds[1])
        raw=crop_view(e,out).replace('<div class="point-layer">',f'<div class="point-layer"><span class="candidate" hidden style="left:{x}%;top:{y}%;width:{cw}%;height:{ch}%"><span>미확인</span></span>')
        page+=f'<article data-index="{i}"><h2>{i+1}. {esc(row["area"])}</h2><p>기존 구역 정답: <strong>{"결함" if row["target"] else "정상"}</strong> (확인 완료·변경 안 함)</p>'+raw+'<label><input type="checkbox" data-candidate disabled data-requires-js> 미확인 모델 후보 겹쳐 보기</label>'
        if e['completed']:page+='<p>기존 위치 확인 완료 · 다시 묻지 않습니다.</p>'
        else:
            page+='<fieldset disabled data-requires-js><legend>새로 찍은 위치의 판정</legend><p>원본에서 위치를 찍거나 좌표를 입력한 뒤 선택하세요. 후보가 정답이라고 가정하지 마세요.</p><button type="button" data-judgment="normal" aria-pressed="false">정상</button><button type="button" data-judgment="defect" aria-pressed="false">결함</button><button type="button" data-judgment="unknown" aria-pressed="false">모르겠음</button>'
            page+=f'<label>X <input name="x" type="number" step="any" min="{l}" max="{rr}"></label><label>Y <input name="y" type="number" step="any" min="{t}" max="{b}"></label><label>메모<textarea name="note"></textarea></label><button type="button" data-action="record">기록</button></fieldset><button type="button" data-action="edit" hidden>방금 입력 수정</button><p class="response-state" role="status">미기록 · 정답으로 추정하지 않음</p>'
        page+='<details><summary>모델 반응 지도 (미확인)</summary>'+crop_view(e,out,True)+'<p>모델 반응은 실제 손상 위치나 원인을 증명하지 않습니다.</p></details></article>'
    view=dict(packet_id=packet['packet_id'],batch_name=Path(filename).stem,entries=[dict(id=e['id'],row={k:e['row'][k] for k in ('id','target','image_sha256','box')},completed=e['completed']) for e in packet['entries']])
    encoded=json.dumps(view,ensure_ascii=False,separators=(',',':')).replace('<',chr(92)+'u003c')
    page+=f'<p>검증 소스 <code>{esc(source_sha)}</code>. 자동 학습·구역 정답 변경 없음. 새 화면의 실제 폰 조작은 미확인입니다.</p><script id="packet" type="application/json">'+encoded+'</script><script>'+(Path(__file__).parent/'review.js').read_text()+'</script></html>'
    with (out/filename).open('x') as stream:stream.write(page)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packet',required=True);p.add_argument('--answers',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    result=ingest(a.packet,a.answers,a.output);print(json.dumps(dict(confirmed_points=len(result['human_point_labels']),unknown=len(result['unknown_ids']),pending=len(result['pending_ids']),region_labels_changed=False)))
