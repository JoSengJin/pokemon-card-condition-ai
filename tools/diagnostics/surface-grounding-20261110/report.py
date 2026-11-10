"""Local diagnostic report: raw crop first, model support separate, missing-only review."""
import base64
import hashlib
import html
import io
import json
import math
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw


def crop_view(entry,out,model=False):
    row=entry['row'];width,height=entry['image_size'];l,t,r,b=row['box']
    original_bytes=Path(row['image']).read_bytes()
    if hashlib.sha256(original_bytes).hexdigest()!=row['image_sha256']:raise ValueError('Original photo hash changed')
    with Image.open(io.BytesIO(original_bytes)) as source:
        mime=Image.MIME[source.format];original=ImageOps.exif_transpose(source).convert('RGB')
    if original.size!=(width,height):raise ValueError('Original photo dimensions changed')
    box=(math.floor(l*width),math.floor(t*height),math.ceil(r*width),math.ceil(b*height))
    bounds=[box[0]/width,box[1]/height,box[2]/width,box[3]/height]
    crop=original.crop(box);native_size=crop.size
    if model:
        evidence=entry['evidence'];g=evidence['top_geometry'];left,top,cw,ch=g['crop_pixels'];rw,rh=g['resized'];px,py=g['pad']
        overlay=Image.new('RGBA',crop.size);draw=ImageDraw.Draw(overlay)
        for index,score in enumerate(entry['patch_scores']):
            if score is None:continue
            col,line=index%32,index//32
            x0,y0=max(col*14,px),max(line*14,py);x1,y1=min((col+1)*14,px+rw),min((line+1)*14,py+rh)
            if x1<=x0 or y1<=y0:continue
            region=[left+(x0-px)*cw/rw-box[0],top+(y0-py)*ch/rh-box[1],left+(x1-px)*cw/rw-box[0],top+(y1-py)*ch/rh-box[1]]
            draw.rectangle(region,fill=(round(255*score),35,round(255*(1-score)),95))
        crop=Image.alpha_composite(crop.convert('RGBA'),overlay);draw=ImageDraw.Draw(crop)
        for color,key in [('#ffdd00','top_geometry'),('#00ffff','second_geometry')]:
            if evidence.get(key):
                x0,y0,x1,y1=evidence[key]['box'];draw.rectangle([x0*width-box[0],y0*height-box[1],x1*width-box[0],y1*height-box[1]],outline=color,width=2)
    stream=io.BytesIO();crop.save(stream,format='PNG');data=base64.b64encode(stream.getvalue()).decode()
    attributes='' if model else ' data-locate="true" data-view-box="'+','.join(str(v) for v in bounds)+'"'
    value=f'<div class="raw-frame" style="max-width:{native_size[0]}px"><img{attributes} width="{native_size[0]}" height="{native_size[1]}" alt="'+('모델 반응, 손상 정답 아님' if model else '원본 픽셀 구역, 클릭 또는 아래 좌표 입력')+f'" src="data:image/png;base64,{data}"><div class="point-layer">'
    for point in entry['known_points']:
        x=100*(point['x']-bounds[0])/(bounds[2]-bounds[0]);y=100*(point['y']-bounds[1])/(bounds[3]-bounds[1])
        value+=f'<span class="known-point" style="left:{x}%;top:{y}%" title="기존 확정 표면점"></span>'
    value+='</div></div>'
    if not model:
        value+=f'<p>원본 구역 {native_size[0]}×{native_size[1]}px · 픽셀 보정/확대 없음</p><details class="original-context"><summary>원사진 전체 보기</summary><img alt="원사진 전체" width="{width}" height="{height}" src="data:{mime};base64,{base64.b64encode(original_bytes).decode()}"></details>'
    return value


def panel(entry,out):
    row=entry['row'];esc=html.escape;index=entry['parent_index'];w,h=entry['image_size']
    value=f'<article data-index="{index}" data-outcome="{entry["outcome"]}" data-size="{w},{h}"><details><summary>{entry["outcome"]} · fold{entry["fold"]} · {esc(row["area"])} · {esc(row["group"])} · 점수 {entry["saved_score"]:.6f}</summary>'
    value+='<p>기존 사람 정답: <strong>'+('결함 있음' if row['target'] else '정상')+'</strong> · 이 정답은 변경하지 않습니다. 먼저 원본에서 위치를 확인하세요.</p>'+crop_view(entry,out)
    if entry['known_points']:
        value+=f'<p>기존 확정 표면점 {len(entry["known_points"])}개를 재사용합니다. 위치를 다시 요청하지 않습니다.</p>'
    else:
        prompt='표면 손상이 보이는 위치' if row['target'] else '정상 무늬·반사 등 설명할 위치(판단 가능한 경우)'
        categories=[('surface_mark','표면 손상 위치')] if row['target'] else [('print_pattern','정상 인쇄/무늬'),('reflection_or_cover','반사/케이스로 보임')]
        categories.append(('other','기타, 메모에 설명'))
        value+=f'<fieldset><legend>아직 없는 위치 설명: {prompt}</legend><label>판단 <select name="status"><option value="">선택 전 · 미확인</option><option value="located">위치를 표시할 수 있음</option><option value="cannot_localize">이 사진에서는 위치 판단 불가</option></select></label><label>설명 <select name="category"><option value="">선택 전</option>'
        for key,label in categories:value+=f'<option value="{key}">{label}</option>'
        value+='</select></label><p>원본 확대 위를 클릭하거나 좌표를 직접 입력하세요. 좌표는 원본 사진 기준 0~1입니다.</p>'
        value+=f'<label>X <input name="x" type="number" step="any" min="{row["box"][0]}" max="{row["box"][2]}" aria-label="원본 사진 X좌표"></label><label>Y <input name="y" type="number" step="any" min="{row["box"][1]}" max="{row["box"][3]}" aria-label="원본 사진 Y좌표"></label>'
        value+='<label>설명 메모(입력 원문 보존)<textarea name="note" rows="2"></textarea></label><button type="button" data-action="record">이 설명 기록</button></fieldset><button type="button" data-action="edit" hidden>방금 입력한 설명 수정</button><p class="response-state" role="status">아직 설명 없음 · 정상/결함 정답 유지</p>'
    value+='<details class="model"><summary>모델 반응 보기 · 손상 정답 위치가 아님</summary>'+crop_view(entry,out,True)
    e=entry['evidence'];value+=f'<p>노랑: 최고 반응 patch, 청록: 두 번째. heatmap 빨강=높은 점수, 파랑=낮은 점수. 최고 patch {e["top_index"]}, 원본 픽셀 겹침 {100*e["top_geometry"]["coverage"]:.1f}%. ViT는 다른 위치의 문맥도 사용하므로 이 사각형은 실제 원인이나 제한된 수용영역을 증명하지 않습니다.</p></details></details></article>'
    return value


def render_report(packet,summary,out,script,case_indices=None,filename="report.html"):
    out=Path(out);esc=html.escape;selected=[e for e in packet['entries'] if e['selected']]
    if case_indices is not None:
        requested=list(case_indices);index={e['parent_index']:e for e in selected}
        if len(set(requested))!=len(requested) or any(i not in index for i in requested):raise ValueError('Unique originally selected cases required')
        selected=[index[i] for i in requested]
    page="""<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>α0 손상 위치 근거 검토</title><style>body{font:16px/1.5 system-ui;max-width:1050px;margin:auto;padding:16px;background:#f5f7fa;color:#17212b}article{background:white;border:1px solid #cbd2da;padding:12px;margin:14px 0}summary{cursor:pointer;padding:8px;font-weight:600}img{display:block;max-width:100%;height:auto}.raw-frame{position:relative;width:100%}.raw-frame>img{width:100%;height:auto}.point-layer{position:absolute;inset:0;pointer-events:none}.known-point,.new-point{position:absolute;width:12px;height:12px;border:2px solid white;border-radius:50%;transform:translate(-50%,-50%)}fieldset{margin:12px 0;border:1px solid #aeb8c4}label{display:block;margin:10px 0}input,select,button,textarea{font:inherit;max-width:100%}textarea{display:block;width:100%;box-sizing:border-box}button{padding:8px 12px;margin:5px 0}table{border-collapse:collapse}td,th{border:1px solid #aaa;padding:7px}.known-point{background:#008cff}.new-point{background:#6c00d9}.model{border:1px dashed #8d99aa;margin-top:12px}#export{width:100%;height:180px}#message{white-space:pre-wrap;color:#8c2b00}pre,code{overflow-wrap:anywhere;white-space:pre-wrap}#download{display:inline-block;padding:10px 14px;background:#174ba8;color:white;border-radius:5px;text-decoration:none;margin-right:10px}#download[aria-disabled="true"]{opacity:.45;pointer-events:none}[hidden]{display:none!important}</style><h1>개발78/100(v1.13) · α0 손상 위치 근거 검토</h1>"""
    page+=f'<p>재학습0 · 모델/손실/구역 정답 변경0. 검증 소스 <code>{esc(summary["source_sha"])}</code>. 반복 개발자료의 진단이며 독립 시험이 아닙니다. 기존 확정 위치는 재사용하고, 없는 위치 설명만 기록합니다.</p>'
    page+=f'<p>전체1776구역/204사진 · 결함370/정상1406. 기존 α0: AUC0.931924955,누락57/370(15.4054%),오탐167/1406(11.8777%),변화0%p. 원래 품질 기준은 미충족 상태 그대로입니다. 관찰 제한 누락/오탐은 미평가.</p><p>전체 검토 대상: 오류224개 + 정답 대조 {packet["summary"]["correct_controls"]}개. 이 파일은 그중 {len(selected)}구역입니다. 모델 점수 크기로 정답 대조를 고르지 않았습니다. 위치·설명 미확인 {packet["summary"]["selected_missing_points"]}개. 기존 위치를 못 찾았다는 것이 사진에 손상이 없다는 뜻은 아닙니다.</p>'
    page+='<p>모델 반응 지도는 각 항목에서 따로 펼칩니다. 먼저 원본을 보세요. 사진 판단 불가는 정상으로 처리하지 않으며, 기록한 설명은 자동으로 학습·원래 라벨에 반영되지 않습니다.</p><label>보기 <select id="filter"><option value="all">오류와 정답 대조 모두</option><option value="FN">누락 FN</option><option value="FP">오탐 FP</option><option value="TP">결함 정답 대조 TP</option><option value="TN">정상 정답 대조 TN</option></select></label><label>저장한 설명 JSON 이어보기 <input id="resume" type="file" accept="application/json,.json"></label><p>기록 <span id="answered">0</span>개. 각 항목의 「이 설명 기록」을 누른 뒤 JSON 파일을 저장해 이 채팅에 첨부하세요. 일부만 검토해도 됩니다. 새로고침·창 닫기 전에 파일 저장 또는 복사가 필요합니다.</p><p><a id="download" aria-disabled="true" tabindex="-1">JSON 파일 저장</a><span>1개 이상 기록하면 저장할 수 있습니다.</span></p><button id="copy" type="button">설명 JSON 선택/복사</button><p id="message" role="status" aria-live="polite"></p><label>복사할 설명 JSON<textarea id="export" readonly aria-label="복사할 위치 설명 JSON"></textarea></label><noscript>설명 입력 기능은 JavaScript가 필요합니다. 원본·모델 반응과 기존 정답은 아래에서 확인할 수 있습니다.</noscript>'
    for entry in selected:page+=panel(entry,out)
    page+='<details><summary>진단 검증·변경·위험·롤백</summary><pre>'+esc(json.dumps(summary,ensure_ascii=False,indent=2))+'</pre><p>변경: 위치근거 감사·진단 재생·원본/모델 반응 비교·설명 sidecar 검증. 모델 개선이나 원인 확정이 아닙니다. 기존 운영 모델·fallback은 변경하지 않았습니다. 새 근거가 실제 모델 성능을 높이는지는 미검증입니다. 소스의 일반 git revert로 도구를 제거할 수 있으며 기존 기록·사람 답은 보존합니다.</p></details>'
    projection=dict(kind='surface_grounding_display_projection',packet_id=packet['packet_id'],entries=[dict(row={k:e['row'][k] for k in ('id','target','image_sha256','box')},selected=e['selected'],known_points=e['known_points']) for e in packet['entries']])
    if summary.get('batch_number'):
        projection['batch_name']=f"{summary['batch_number']:02d}"
        page=page.replace('<h1>개발78/100(v1.13) · α0 손상 위치 근거 검토</h1>',f"<h1>원본 픽셀 검토 · 묶음 {summary['batch_number']:02d}/{summary['batch_total']}</h1><p>개발 진척78/100(v1.13) 유지 · 모델 개선 미평가.</p><p>이 파일은 {len(selected)}구역입니다. 기록 후 JSON을 저장해 채팅에 첨부하세요. 이전 묶음의 JSON을 불러오면 답을 합쳐 저장할 수 있습니다.</p>")
    encoded=json.dumps(projection,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('<',chr(92)+'u003c')
    page+='<script type="application/json" id="packet">'+encoded+'</script><script>'+Path(script).read_text()+'</script></html>'
    assert page.count('<article data-index=')==len(selected)
    with (out/filename).open('x') as stream:stream.write(page)
