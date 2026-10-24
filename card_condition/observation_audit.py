"""Train-only descriptive input signals; never a visibility or defect classifier."""
import html
import json
from pathlib import Path
from statistics import median

from .observation_signals import pixel_signals, spatial_signals

from .point_probe import digest
from .regions import VISIBILITY_ISSUES
from .side_experiment import side_image
from .visibility_model import TARGET, visibility_rows


METRICS = ('luminance_mean','luminance_std','gradient_energy',
           'bright_fraction','dark_fraction','cell_luminance_spread')


def reason_summary(rows):
    result={}
    for side in ('front','back'):
        clear=[r for r in rows if r['side']==side and r['labels'][TARGET]==0]
        result[side]={}
        for reason in VISIBILITY_ISSUES:
            limited=[r for r in rows if r['side']==side and reason in r['visibility_issues']]
            summary=dict(faces=len(limited),physical_groups=len({r['group'] for r in limited}),
                clear_faces=len(clear),clear_groups=len({r['group'] for r in clear}),views={})
            for view in ('native','input224'):
                stats={}
                for key in METRICS:
                    positive=[r[view]['signals'][key] for r in limited]
                    negative=[r[view]['signals'][key] for r in clear]
                    stats[key]=dict(limited_median=median(positive) if positive else None,
                        clear_median=median(negative) if negative else None,
                        clear_min=min(negative) if negative else None,
                        clear_max=max(negative) if negative else None,
                        limited_within_clear_range=sum(min(negative)<=v<=max(negative) for v in positive) if negative else None)
                summary['views'][view]=stats
            result[side][reason]=summary
    return result


def audit_inputs(manifest, output):
    output=Path(output)
    if output.exists():
        raise ValueError('Output exists: choose a new input audit directory')
    hashes={str(Path(manifest).resolve()):digest(manifest)}
    selected,skipped=visibility_rows(manifest,splits={'train'})
    if not selected:
        raise ValueError('No known training observation labels')
    rows=[]
    for row in selected:
        hashes[row['image']]=digest(row['image'])
        native=side_image(row['image'],row['box'],True,None)
        resized=side_image(row['image'],row['box'],True,224)
        rows.append(dict(**row,native=spatial_signals(native),input224=spatial_signals(resized)))
    if any(digest(path)!=value for path,value in hashes.items()):
        raise ValueError('Input audit source changed')
    output.mkdir(parents=True,exist_ok=False)
    sections=[]
    for index,row in enumerate(rows):
        preview=side_image(row['image'],row['box'],True,None)
        preview.thumbnail((448,448))
        preview.save(output/f'{index}-preview.png')
        side_image(row['image'],row['box'],True,224).save(output/f'{index}-224.png')
        title=html.escape(row['card_id']+' / '+row['side'])
        reasons=html.escape(', '.join(row['visibility_issues']) or '사람이 명시한 관찰 제한 없음')
        metrics=html.escape(json.dumps({view:row[view]['signals'] for view in ('native','input224')},ensure_ascii=False,indent=2))
        sections.append(f'<section><h2>{title}</h2><p>{reasons}</p><img src="{index}-preview.png" alt="카드 영역 미리보기"><img src="{index}-224.png" alt="실제224px 입력"><details><summary>입력 신호</summary><pre>{metrics}</pre></details></section>')
    if any(digest(path)!=value for path,value in hashes.items()):
        raise ValueError('Input audit source changed; discard output')
    report=dict(split='train',faces=len(rows),physical_groups=len({r['group'] for r in rows}),
        clear_faces=sum(r['labels'][TARGET]==0 for r in rows),limited_faces=sum(r['labels'][TARGET]==1 for r in rows),
        rows=rows,skipped=skipped,reason_summary=reason_summary(rows),input_hashes=hashes,
        thresholds=dict(bright_luminance_at_least=245,dark_luminance_at_most=25),
        labels_modified=False,trained_model=False,production_ready=False,actual_calls_saved=0,
        limitations=['Signals describe pixels, not glare, shadow, blur or card damage truth.',
            'Grid cells have no inherited labels. Parent reasons apply only to the image.',
            '224px includes existing gray padding; native resolution/print/detail affect gradients.',
            'Per-face medians/ranges are descriptive, not independent tests or fitted decision thresholds.',
            'No validation/test photos or labels loaded; no calibration or model selection performed.'])
    table=[]
    for side,reasons in report['reason_summary'].items():
        for reason,summary in reasons.items():
            mean=summary['views']['input224']['luminance_mean']['limited_within_clear_range']
            table.append(f'<tr><td>{side}</td><td>{reason}</td><td>{summary["faces"]} / {summary["physical_groups"]}</td><td>{summary["clear_faces"]}</td><td>{mean if mean is not None else "비교 불가"}</td></tr>')
    summary_html='<table border="1"><tr><th>면</th><th>기록된 제한</th><th>면 / 실물 수</th><th>관찰 제한 없음 면 수</th><th>224px 평균 밝기가 관찰 제한 없음 범위와 겹치는 면 수</th></tr>'+''.join(table)+'</table>'
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))
    (output/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>학습 입력 근거 진단</title><style>body{font:17px system-ui;margin:24px}section{border-top:1px solid #ccc;margin:24px 0}img{max-width:100%;vertical-align:top;margin:8px}pre{white-space:pre-wrap}</style><h1>학습 입력 근거 진단</h1><p>학습 사진만 사용. 왼쪽은 최대448px 미리보기, 오른쪽은 실제224px 입력입니다. 밝기·명암·픽셀 차이는 반사/하자 판정이 아니며, 구역별 정답을 만들지 않습니다. 표의 범위 겹침은 기술 통계이며 판정 임계값이 아닙니다.</p>'+summary_html+''.join(sections)+'</html>')
    return report
