"""Local-only report; token boxes identify responses, not human defect locations."""
import os
import html
import json
from pathlib import Path


def render_report(entries,summary,out,plan):
    root=next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
    fold_names=['baseline','arithmetic','lme','mixture']
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>동결 모델 패치 근거</title><style>body{font:15px/1.5 system-ui;max-width:1400px;margin:auto;padding:16px}.cards{display:flex;flex-wrap:wrap;gap:12px}.card{width:300px}.photo{position:relative;line-height:0}.photo img{width:100%}.box{position:absolute;border:2px solid orange;box-sizing:border-box}.top{border-color:red}.second{border-color:cyan}.region{border-color:orange}table{border-collapse:collapse;font-size:12px;width:100%}td,th{border:1px solid #aaa;padding:5px;overflow-wrap:anywhere}pre{white-space:pre-wrap}summary{cursor:pointer}</style><h1>개발78/100(v1.13) · 재학습0 / 동결 모델 패치 진단</h1><p>공통오탐160·신규누락6·신규오탐17은 중복태그이며 합집합172구역/98사진입니다. 오류로 선택한 개발 진단 자료로, 독립시험/새 정확도 측정이 아닙니다. 기존점수·출력·정답·분할을 유지합니다.</p><p>주황: 사람정답 구역, 빨강: 최고 반응token, 청록: 두번째token. 반응 위치는 실제 결함의 위치/원인을 증명하지 않습니다. ViT의 token은 전역문맥도 사용합니다. 패딩부분은 원사진 겹침영역으로 자릅니다.</p><pre>'''+html.escape(json.dumps(summary,ensure_ascii=False,indent=2))+'</pre>'
    page+='<p>검증 소스 SHA: '+html.escape(plan.get('source_sha','uncommitted'))+'</p>'
    image_cache={}
    for entry in entries:
        row=entry['row'];path=row['image']
        if path not in image_cache:
            image_cache[path]=html.escape(os.path.relpath(path,out),quote=True)
        page+='<details data-id="'+html.escape(row['id'])+'"><summary>'+str(entry['parent_index'])+' · '+html.escape(row['id'])+' · '+','.join(entry['tags'])+' · 사람:'+('결함' if row['target'] else '정상')+'</summary><div class="cards">'
        for name in fold_names:
            e=entry['models'][name]
            page+='<div class="card"><h3>'+name+f' · {e["score"]:.6f}</h3><div class="photo"><img loading="lazy" alt="원사진 반응 token 비교" src="'+image_cache[path]+'">'
            for cls,box in [('region',row['box']),('top',e['top_geometry']['box']),('second',e['second_geometry']['box'] if e['second_geometry'] else None)]:
                if box is None:continue
                l,t,r,b=box
                page+=f'<div class="box {cls}" style="left:{l*100}%;top:{t*100}%;width:{(r-l)*100}%;height:{(b-t)*100}%"></div>'
            page+='</div></div>'
        page+='</div><table><tr><th>모델</th><th>기존저장점수/재현오차</th><th>최고/두번째 점수</th><th>logit 간격</th><th>token위치/유효수</th><th>0.5이상token</th><th>smooth상한−max</th><th>최고soft가중치</th><th>원사진겹침비율</th></tr>'
        for name in fold_names:
            e=entry['models'][name]
            page+='<tr><td>'+name+'</td><td>'+str(e['saved_score'])+' / '+str(e['replay_error'])+'</td><td>'+str(e['score'])+' / '+str(e['second_score'])+'</td><td>'+str(e['margin'])+'</td><td>'+str(e['top_geometry']['grid'])+' / '+str(e['valid_tokens'])+'</td><td>'+str(e['above_half_tokens'])+'</td><td>'+str(e['upper_gap'])+'</td><td>'+str(e['top_soft_weight'])+'</td><td>'+str(e['top_geometry']['coverage'])+'</td></tr>'
        page+='</table></details>'
    page+='<p>추적소스:'+html.escape(plan['tracked_directory'])+' · 실제실행source SHA는 같은폴더record.json의snapshot/입력hash와task를 참조. 출력은진단sidecar이며운영score API는변경하지않았습니다.</p></html>'
    assert page.count('<details data-id=')==len(entries)
    (out/'report.html').write_text(page)
    fields=['parent_index','id','tags','model','target','saved_score','score','replay_error','top_index','second_index','margin','valid_tokens','above_half_tokens','upper_gap','top_soft_weight']
    import csv
    with (out/'comparison.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for entry in entries:
            for model,e in entry['models'].items():writer.writerow(dict(parent_index=entry['parent_index'],id=entry['row']['id'],tags=','.join(entry['tags']),model=model,target=entry['row']['target'],**{k:e[k] for k in fields[5:]}))
