"""Paired development metrics and local photo evidence, distinct from full C3."""
import html
import json
from pathlib import Path
from PIL import ImageDraw
from card_condition.side_experiment import side_image


def compare(rows, points, before, after, before_points, after_points, unsupported):
    if len(rows) != len(before) or len(rows) != len(after) or len(points) != len(before_points) or len(points) != len(after_points):
        raise ValueError('Paired denominators differ')
    result = dict(independent=False, production_adopted=False, threshold=.5, sides={})
    for side in ('front', 'back'):
        indexes = [i for i,r in enumerate(rows) if r['side']==side]
        pindexes = [i for i,r in enumerate(points) if r['side']==side]
        positives = [i for i in indexes if rows[i]['target']==1]
        negatives = [i for i in indexes if rows[i]['target']==0]
        counts = dict(positives=len(positives), negatives=len(negatives), points=len(pindexes),
                      positive_groups=len({rows[i]['group'] for i in positives}),
                      negative_groups=len({rows[i]['group'] for i in negatives}),
                      point_groups=len({points[i]['group'] for i in pindexes}))
        metrics = {}
        for name, scores, ps in [('before',before,before_points),('after',after,after_points)]:
            fn = sum(scores[i]<.5 for i in positives); fp = sum(scores[i]>=.5 for i in negatives); misses = sum(ps[i]<.5 for i in pindexes)
            metrics[name] = dict(fn=fn, fp=fp, point_fn=misses,
                                fn_rate=fn/len(positives) if positives else None,
                                fp_rate=fp/len(negatives) if negatives else None,
                                point_fn_rate=misses/len(pindexes) if pindexes else None)
        new_errors = [rows[i]['id'] for i in indexes if (before[i]>=.5)==bool(rows[i]['target']) and (after[i]>=.5)!=bool(rows[i]['target'])]
        new_points = [points[i]['id'] for i in pindexes if before_points[i]>=.5>after_points[i]]
        delta = {key: 100*(metrics['after'][key]-metrics['before'][key]) if metrics['before'][key] is not None else None for key in ('fn_rate','fp_rate','point_fn_rate')}
        enough = counts['positives']>=20 and counts['negatives']>=20 and counts['points']>=20 and min(counts['positive_groups'],counts['negative_groups'],counts['point_groups'])>=5
        quality = enough and metrics['after']['fn_rate']<=.05 and metrics['after']['fp_rate']<=.10 and metrics['after']['point_fn_rate']<=.05
        result['sides'][side] = dict(denominators=counts, **metrics, delta_pp=delta, new_errors=new_errors, new_point_misses=new_points, scored_subset_quality_met=quality)
    before_errors = sum(v['before'][k] for v in result['sides'].values() for k in ('fn','fp','point_fn'))
    after_errors = sum(v['after'][k] for v in result['sides'].values() for k in ('fn','fp','point_fn'))
    result['comparison_advance'] = after_errors<before_errors and all(not v['new_errors'] and not v['new_point_misses'] for v in result['sides'].values())
    result['full_surface_quality_met'] = not unsupported and all(v['scored_subset_quality_met'] for v in result['sides'].values())
    result['unsupported'] = unsupported
    return result


def render(out, rows, points, masks, maps, before, after, point_before, point_after, metrics, progress, source_sha):
    out = Path(out); (out/'images').mkdir(); panels = []
    for i, row in enumerate(rows):
        image = side_image(row['image'], row['box'], True, 224); draw = ImageDraw.Draw(image)
        for name, color in [('baseline','orange'),('candidate','blue')]:
            peak = int(maps[name][i].masked_fill(~masks[i], -1).argmax())
            draw.rectangle((peak%16*14,peak//16*14,peak%16*14+13,peak//16*14+13),outline=color,width=2)
        clicks = []
        for j, point in enumerate(points):
            if point['parent_index'] == i:
                x,y = point['input_pixel']; draw.ellipse((x-3,y-3,x+3,y+3),outline='red',width=2)
                clicks.append(f"{html.escape(point['id'])}: {point_before[j]:.4f} → {point_after[j]:.4f}")
        image.save(out/'images'/f'{i}.png')
        truth = '표면 손상' if row['target'] else '표면 정상'
        panels.append(f'<article><h3>{html.escape(row["id"])}</h3><img loading="lazy" src="images/{i}.png"><p>사람: {truth}<br>기존 {before[i]:.4f} → 후보 {after[i]:.4f}</p><p>'+ '<br>'.join(clicks)+'</p></article>')
    page = '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>A3 표면 비교</title><style>body{font:16px/1.6 system-ui;margin:24px;background:#f5f7fa}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}article,section{background:white;margin:8px;padding:14px}h3,p,pre{overflow-wrap:anywhere}pre{white-space:pre-wrap}img{max-width:100%}</style>'
    page += f'<h1>개발 진척 {progress}/100 · A3 표면 후보 비교</h1><section><p>검증 source {source_sha} · usable-card-analysis-v1.0. 개발val·모델선택 자료이며 독립시험/운영채택 아님. 새학습0.</p><p>빨강=사람 실제점, 주황/파랑=기존/후보 최대반응(위치정답 아님). 확인되지 않은 영역은 미지원 목록에 남긴다. 표면 외 질문/관찰제한 탐지 성능은 미측정.</p><a href="evaluation.json">전체 점수/정답/미지원</a> · <a href="result.json">기존147/51/11cohort 공통판정</a><pre>'
    page += html.escape(json.dumps(metrics,ensure_ascii=False,indent=2))+'</pre></section><div class="grid">'+''.join(panels)+'</div></html>'
    (out/'index.html').write_text(page)
    return len(panels)
