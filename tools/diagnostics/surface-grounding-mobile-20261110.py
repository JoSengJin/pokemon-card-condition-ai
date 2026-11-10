"""Package existing grounding evidence into self-contained five-case mobile pages."""
import hashlib
import html
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/diagnostics/surface-grounding-20261110'))
from audit import packet_digest
from report import render_report

if __name__=='__main__':
    canonical=ROOT/'artifacts/surface-grounding-20261110/packet.json'
    raw=canonical.read_bytes();packet=json.loads(raw)
    if packet['packet_id']!=packet_digest(packet):raise ValueError('Canonical packet changed')
    out=ROOT/'artifacts/surface-grounding-mobile-20261110';out.mkdir(exist_ok=True)
    ids=[e['parent_index'] for e in packet['entries'] if e['selected']]
    if len(ids)!=313 or len(set(ids))!=313:raise ValueError('Original313-case selection required')
    run=ROOT/'artifacts/experiments/20261109T234706-4aeb730c'
    record=json.loads((run/'record.json').read_text())
    if record['status']!='completed':raise ValueError('Frozen replay incomplete')
    for file,digest in record['source_hashes'].items():
        if hashlib.sha256((ROOT/file).read_bytes()).hexdigest()!=digest:raise ValueError('Frozen runtime changed')
    source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    pages=[]
    for start in range(0,len(ids),5):
        number=start//5+1;name=f'review-{number:02d}.html';chunk=ids[start:start+5]
        summary=json.loads((run/'diagnostics.json').read_text())
        summary.update(replay_source_sha=summary['source_sha'],source_sha=source_sha,
            task='native_pixel_mobile_review',batch_number=number,batch_total=(len(ids)+4)//5,
            batch_cases=len(chunk),no_new_inference=True,no_new_training=True,
            original_packet_id=packet['packet_id'],display_projection_not_canonical_packet=True,
            user_confirmed_calibration_only=True,new_review_mobile_behavior_verified=False)
        render_report(packet,summary,out,ROOT/'tools/diagnostics/surface-grounding-20261110/review.js',case_indices=chunk,filename=name)
        pages.append(dict(filename=name,parent_indices=chunk,bytes=(out/name).stat().st_size,sha256=hashlib.sha256((out/name).read_bytes()).hexdigest()))
        if number%10==0 or start+5>=len(ids):print(json.dumps(dict(stage='packaging',completed_pages=number,total_pages=(len(ids)+4)//5)),flush=True)
    index='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>원본 픽셀 검토 묶음</title><style>body{font:18px/1.6 system-ui;padding:20px;max-width:800px;margin:auto}a{display:block;padding:8px}code{overflow-wrap:anywhere}</style><h1>원본 픽셀 검토 묶음</h1><p>개발 진척78/100(v1.13) 유지 · 학습/추론0.</p><p>전체313구역을최대5개씩63파일로나눴습니다. 각파일은사진을직접포함합니다. 일부묶음만검토해도됩니다. 기존정상/결함정답은바꾸지않습니다. 기록뒤JSON파일을저장해채팅에첨부하세요.</p><p>휴대폰에서한파일만전달받은경우다른파일로가는이목록의링크는동작하지않을수있습니다. 해당묶음의파일을채팅에서직접받아사용하세요. 저장한JSON은다른묶음에서도불러와이어갈수있습니다.</p>'
    for number,page in enumerate(pages,1):index+=f'<a href="{html.escape(page["filename"],quote=True)}">묶음{number:02d} · {len(page["parent_indices"])}구역 · {page["bytes"]/1024/1024:.2f}MiB</a>'
    with (out/'index.html').open('x') as stream:stream.write(index+'</html>')
    if canonical.read_bytes()!=raw:raise ValueError('Canonical packet changed during packaging')
    manifest=dict(source_sha=source_sha,packet_id=packet['packet_id'],canonical_packet_sha256=hashlib.sha256(raw).hexdigest(),cases=313,pages=pages,
        new_inference_calls=0,new_training_calls=0,labels_changed=False,previous_feedback='10개정도 무작위로 확인해봤는데 판정할 수 없는 상태야',
        calibration_feedback='화질 점검 자료는 잘 보이네 여하튼 다음 개발 진행해',calibration_user_confirmed=True,new_mobile_ui_user_confirmed=False)
    with (out/'postflight.json').open('x') as stream:json.dump(manifest,stream,ensure_ascii=False,indent=2)
    print(json.dumps(dict(pages=len(pages),cases=313,max_page_bytes=max(p['bytes'] for p in pages),training=0,inference=0)),flush=True)
