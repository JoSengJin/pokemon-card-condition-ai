"""Local diagnostic report: raw crop first, model support separate, missing-only review."""
import base64
import html
import io
import json
import os
from pathlib import Path
from urllib.parse import quote
from PIL import Image


def crop_svg(entry,out,model=False):
    row=entry['row'];width,height=entry['image_size'];l,t,r,b=row['box'];vw=(r-l)*width;vh=(b-t)*height
    src=html.escape(quote(os.path.relpath(Path(row['image']).resolve(),Path(out).resolve()).replace(os.sep,'/'),safe='/'),quote=True)
    view=f'{l*width} {t*height} {vw} {vh}'
    attributes='' if model else f' data-locate="true" data-radius="{vw*.012}"'
    value=f'<svg viewBox="{view}" width="{vw}" height="{vh}"{attributes} role="img" aria-label="'+('모델 패치 반응 지도' if model else '원본 구역 확대, 클릭 또는 아래 좌표 입력')+f'"><image href="{src}" width="{width}" height="{height}"/>'
    if model:
        evidence=entry['evidence'];g=evidence['top_geometry'];left,top,cw,ch=g['crop_pixels'];rw,rh=g['resized'];px,py=g['pad']
        pixels=[]
        for score in entry['patch_scores']:
            pixels.append((0,0,0,0) if score is None else (round(255*score),35,round(255*(1-score)),150))
        image=Image.new('RGBA',(32,32));image.putdata(pixels);stream=io.BytesIO();image.save(stream,format='PNG')
        data=base64.b64encode(stream.getvalue()).decode()
        value+=f'<image href="data:image/png;base64,{data}" x="{left-px*cw/rw}" y="{top-py*ch/rh}" width="{448*cw/rw}" height="{448*ch/rh}" preserveAspectRatio="none" style="image-rendering:pixelated"/>'
        for color,key in [('#ffdd00','top_geometry'),('#00ffff','second_geometry')]:
            if evidence.get(key):
                x0,y0,x1,y1=evidence[key]['box'];value+=f'<rect x="{x0*width}" y="{y0*height}" width="{(x1-x0)*width}" height="{(y1-y0)*height}" fill="none" stroke="{color}" stroke-width="{max(1,vw*.008)}"/>'
    for point in entry['known_points']:
        value+=f'<circle cx="{point["x"]*width}" cy="{point["y"]*height}" r="{max(2,vw*.012)}" class="known-point"><title>기존 확정 표면점</title></circle>'
    return value+'</svg>'


def panel(entry,out):
    row=entry['row'];esc=html.escape;index=entry['parent_index'];w,h=entry['image_size']
    value=f'<article data-index="{index}" data-outcome="{entry["outcome"]}" data-size="{w},{h}"><details><summary>{entry["outcome"]} · fold{entry["fold"]} · {esc(row["area"])} · {esc(row["group"])} · 점수 {entry["saved_score"]:.6f}</summary>'
    value+='<p>기존 사람 정답: <strong>'+('결함 있음' if row['target'] else '정상')+'</strong> · 이 정답은 변경하지 않습니다. 먼저 원본에서 위치를 확인하세요.</p>'+crop_svg(entry,out)
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
    value+='<details class="model"><summary>모델 반응 보기 · 손상 정답 위치가 아님</summary>'+crop_svg(entry,out,True)
    e=entry['evidence'];value+=f'<p>노랑: 최고 반응 patch, 청록: 두 번째. heatmap 빨강=높은 점수, 파랑=낮은 점수. 최고 patch {e["top_index"]}, 원본 픽셀 겹침 {100*e["top_geometry"]["coverage"]:.1f}%. ViT는 다른 위치의 문맥도 사용하므로 이 사각형은 실제 원인이나 제한된 수용영역을 증명하지 않습니다.</p></details></details></article>'
    return value


def render_report(packet,summary,out,script):
    out=Path(out);esc=html.escape;selected=[e for e in packet['entries'] if e['selected']]
    page="""<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>α0 손상 위치 근거 검토</title><style>body{font:16px/1.5 system-ui;max-width:1050px;margin:auto;padding:16px;background:#f5f7fa;color:#17212b}article{background:white;border:1px solid #cbd2da;padding:12px;margin:14px 0}summary{cursor:pointer;padding:8px;font-weight:600}svg{display:block;width:100%;height:auto;max-width:650px;background:#eee}fieldset{margin:12px 0;border:1px solid #aeb8c4}label{display:block;margin:10px 0}input,select,button,textarea{font:inherit;max-width:100%}textarea{display:block;width:100%;box-sizing:border-box}button{padding:8px 12px;margin:5px 0}table{border-collapse:collapse}td,th{border:1px solid #aaa;padding:7px}.known-point{fill:#008cff;stroke:white;stroke-width:1.5}.new-point{fill:#6c00d9;stroke:white;stroke-width:1.5}.model{border:1px dashed #8d99aa;margin-top:12px}#export{width:100%;height:180px}#message{white-space:pre-wrap;color:#8c2b00}pre,code{overflow-wrap:anywhere;white-space:pre-wrap}#download{display:inline-block;padding:10px 14px;background:#174ba8;color:white;border-radius:5px;text-decoration:none;margin-right:10px}#download[aria-disabled="true"]{opacity:.45;pointer-events:none}[hidden]{display:none!important}</style><h1>개발78/100(v1.13) · α0 손상 위치 근거 검토</h1>"""
    page+=f'<p>재학습0 · 모델/손실/구역 정답 변경0. 검증 소스 <code>{esc(summary["source_sha"])}</code>. 반복 개발자료의 진단이며 독립 시험이 아닙니다. 기존 확정 위치는 재사용하고, 없는 위치 설명만 기록합니다.</p>'
    page+=f'<p>전체1776구역/204사진 · 결함370/정상1406. 기존 α0: AUC0.931924955,누락57/370(15.4054%),오탐167/1406(11.8777%),변화0%p. 원래 품질 기준은 미충족 상태 그대로입니다. 관찰 제한 누락/오탐은 미평가.</p><p>이 화면: 전체 오류224개 + fold·구역별 정답 대조 {packet["summary"]["correct_controls"]}개 = {len(selected)}구역. 모델 점수 크기로 정답 대조를 고르지 않았습니다. 위치·설명 미확인 {packet["summary"]["selected_missing_points"]}개. 기존 위치를 못 찾았다는 것이 사진에 손상이 없다는 뜻은 아닙니다.</p>'
    page+='<p>모델 반응 지도는 각 항목에서 따로 펼칩니다. 먼저 원본을 보세요. 사진 판단 불가는 정상으로 처리하지 않으며, 기록한 설명은 자동으로 학습·원래 라벨에 반영되지 않습니다.</p><label>보기 <select id="filter"><option value="all">오류와 정답 대조 모두</option><option value="FN">누락 FN</option><option value="FP">오탐 FP</option><option value="TP">결함 정답 대조 TP</option><option value="TN">정상 정답 대조 TN</option></select></label><label>저장한 설명 JSON 이어보기 <input id="resume" type="file" accept="application/json,.json"></label><p>기록 <span id="answered">0</span>개. 각 항목의 「이 설명 기록」을 누른 뒤 JSON 파일을 저장해 이 채팅에 첨부하세요. 일부만 검토해도 됩니다. 새로고침·창 닫기 전에 파일 저장 또는 복사가 필요합니다.</p><p><a id="download" aria-disabled="true" tabindex="-1">JSON 파일 저장</a><span>1개 이상 기록하면 저장할 수 있습니다.</span></p><button id="copy" type="button">설명 JSON 선택/복사</button><p id="message" role="status" aria-live="polite"></p><label>복사할 설명 JSON<textarea id="export" readonly aria-label="복사할 위치 설명 JSON"></textarea></label><noscript>설명 입력 기능은 JavaScript가 필요합니다. 원본·모델 반응과 기존 정답은 아래에서 확인할 수 있습니다.</noscript>'
    for entry in selected:page+=panel(entry,out)
    page+='<details><summary>진단 검증·변경·위험·롤백</summary><pre>'+esc(json.dumps(summary,ensure_ascii=False,indent=2))+'</pre><p>변경: 위치근거 감사·진단 재생·원본/모델 반응 비교·설명 sidecar 검증. 모델 개선이나 원인 확정이 아닙니다. 기존 운영 모델·fallback은 변경하지 않았습니다. 새 근거가 실제 모델 성능을 높이는지는 미검증입니다. 소스의 일반 git revert로 도구를 제거할 수 있으며 기존 기록·사람 답은 보존합니다.</p></details>'
    encoded=json.dumps(packet,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('<','\u003c')
    page+='<script type="application/json" id="packet">'+encoded+'</script><script>'+Path(script).read_text()+'</script></html>'
    assert page.count('<article data-index=')==len(selected)
    with (out/'report.html').open('x') as stream:stream.write(page)
