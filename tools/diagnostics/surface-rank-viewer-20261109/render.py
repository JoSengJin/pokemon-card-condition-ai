"""Render saved ranking diagnostics only; no model or network calls."""
import argparse
import hashlib
import html
import json
import math
import os
from pathlib import Path
from urllib.parse import quote, urlsplit

LABELS={'same_photo':'같은 사진','cross_photo_same_fold':'다른 사진 · 같은 fold','cross_fold':'다른 fold'}
COLORS={'TP':'#087f5b','TN':'#2459a6','FP':'#a65b00','FN':'#c92a2a'}
CSS="""body{font:16px/1.65 system-ui;margin:auto;max-width:1280px;padding:24px;background:#f3f5f8;color:#172330}h1{line-height:1.3}h2{line-height:1.4}a{color:#1355a3}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border:1px solid #cad2db;padding:8px;text-align:left}th{background:#eef2f7}article,.summary{background:white;border:1px solid #d8dfe7;border-radius:12px;padding:20px;margin:24px 0}.pair{display:grid;grid-template-columns:1fr;gap:16px}.panel{min-width:0;border:1px solid #ccd5df;padding:12px;border-radius:8px}.photo{position:relative;margin:12px 0;overflow:hidden}.photo img{display:block;width:100%;height:auto}.photo svg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}svg text{paint-order:stroke;stroke:white;stroke-width:4px;font-size:19px;font-weight:700}.selected{background:#fff0bd;font-weight:600}.scroll{overflow:auto}.notice{border-left:5px solid #b36400;padding:12px;background:#fff2dd}.missing{background:#ffe8e8;border:1px solid #c92a2a;padding:16px}.muted{color:#526273;font-size:14px}.caption{overflow-wrap:anywhere}.pill{display:inline-block;background:#e8eff8;padding:3px 10px;border-radius:20px}@media(min-width:900px){.pair{grid-template-columns:1fr 1fr}}@media(max-width:600px){body{padding:12px}article,.summary{padding:12px}td,th{padding:5px}}"""


def validate_report(data):
    if (data.get('schema_version')!=1 or data.get('kind')!='saved_oof_rank_partition'
            or data.get('independent') is not False or data.get('new_training_calls')!=0
            or data.get('new_inference_calls')!=0 or data.get('threshold')!=.5):
        raise ValueError('Only frozen v1 saved-score diagnostics are supported')
    lookup={};groups=set();positive=negative=0
    for photo in data['photos']:
        if photo['group'] in groups or type(photo['fold']) is not int or photo['fold']<0:
            raise ValueError('Unique photo groups and integer folds required')
        groups.add(photo['group'])
        if not isinstance(photo['image'],str) or urlsplit(photo['image']).scheme:
            raise ValueError('Only local image paths are supported')
        for z in photo['zones']:
            box=z['box'];score=z['score'];target=z['target']
            if (z['id'] in lookup or type(target) is not int or target not in (0,1)
                    or type(score) not in (int,float) or not math.isfinite(score) or not 0<=score<=1
                    or len(box)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) or not -1e-12<=v<=1+1e-12 for v in box)
                    or box[0]>=box[2] or box[1]>=box[3]):
                raise ValueError('Unique valid region IDs, truth, probabilities and boxes required')
            prediction=int(score>=.5);outcome=('TP' if prediction else 'FN') if target else ('FP' if prediction else 'TN')
            if type(z['prediction']) is not int or z['prediction']!=prediction or z['outcome']!=outcome:
                raise ValueError('Saved outcome is inconsistent with human truth and threshold')
            lookup[z['id']]=(photo,z);positive+=target;negative+=1-target
    if (not positive or not negative or data['positive']!=positive or data['negative']!=negative
            or data['rows_count']!=len(lookup) or data['groups_count']!=len(groups)):
        raise ValueError('Region denominators do not match the saved photos')
    total=data['total'];buckets=data['buckets']
    if len(buckets)!=3 or {b['key'] for b in buckets}!=set(LABELS) or total['pairs']!=positive*negative:
        raise ValueError('All three pair partitions and exact total pairs required')
    for b in [total]+buckets:
        for key in ('pairs','strict_inversions','ties'):
            if type(b[key]) is not int or b[key]<0:raise ValueError('Nonnegative integer pair counts required')
        credit=b['strict_inversions']+b['ties']/2
        if (b['strict_inversions']+b['ties']>b['pairs'] or b['error_credit']!=credit
                or (b['pairs']==0 and b['auc'] is not None)
                or (b['pairs']>0 and (type(b['auc']) not in (int,float) or not math.isfinite(b['auc']) or not math.isclose(b['auc'],1-credit/b['pairs'],abs_tol=1e-12,rel_tol=0)))):
            raise ValueError('Pair credit/AUC identity failed')
        expected=credit/total['error_credit'] if total['error_credit'] else 0
        if not math.isfinite(b['loss_share']) or not math.isclose(b['loss_share'],expected,abs_tol=1e-12,rel_tol=0):
            raise ValueError('Pair error share identity failed')
    for key in ('pairs','strict_inversions','ties','error_credit'):
        if sum(b[key] for b in buckets)!=total[key]:raise ValueError('Pair partition sum failed')
    examples_per_bucket={key:0 for key in LABELS}
    for e in data['examples']:
        dp,dz=lookup[e['defect_id']];np,nz=lookup[e['normal_id']]
        expected='same_photo' if dp['group']==np['group'] else 'cross_photo_same_fold' if dp['fold']==np['fold'] else 'cross_fold'
        if (e['bucket']!=expected or dz['target']!=1 or nz['target']!=0
                or e['defect_score']!=dz['score'] or e['normal_score']!=nz['score']
                or not e['normal_score']>e['defect_score']
                or not math.isclose(e['normal_minus_defect'],nz['score']-dz['score'],abs_tol=1e-12,rel_tol=0)):
            raise ValueError('Example does not match the frozen pair/region data')
        examples_per_bucket[e['bucket']]+=1
    if max(examples_per_bucket.values())>5:raise ValueError('At most five examples per bucket allowed')
    return lookup


def zone_table(photo,selected):
    result='<div class="scroll"><table><tr><th>번호 / 구역</th><th>사람 정답</th><th>저장 점수 / 출력</th><th>판정</th></tr>'
    for i,z in enumerate(photo['zones']):
        marked=' class="selected"' if z['id']==selected else ''
        truth='결함' if z['target'] else '정상';prediction='결함' if z['prediction'] else '정상'
        result+=f'<tr{marked} data-zone-id="{html.escape(z["id"],quote=True)}"><td>{i} / {html.escape(z["area"])}</td><td>{truth}</td><td>{z["score"]:.9f} / {prediction}</td><td>{z["outcome"]}</td></tr>'
    return result+'</table></div>'


def photo_panel(photo,selected,input_path,output_path):
    result=f'<section class="panel"><p class="caption"><strong>{html.escape(photo["group"])}</strong> · fold {photo["fold"]}</p>'
    if selected is not None:
        z=next(z for z in photo['zones'] if z['id']==selected)
        truth='결함' if z['target'] else '정상'
        result+=f'<p class="selected">대상 구역: {html.escape(z["area"])} · 사람 정답 {truth} · 점수 {z["score"]:.9f} · {z["outcome"]}</p>'
    image=Path(photo['image'])
    image=image.resolve() if image.is_absolute() else (input_path.parent/image).resolve()
    if image.is_file():
        src=quote(os.path.relpath(image,output_path.parent),safe='/')
        result+=f'<div class="photo"><img src="{html.escape(src,quote=True)}" loading="lazy" alt="{html.escape(photo["group"],quote=True)}"><svg viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label="저장된 구역과 출력">'
        for i,z in enumerate(photo['zones']):
            x1,y1,x2,y2=[max(0.,min(1.,v))*1000 for v in z['box']]
            chosen=z['id']==selected;color=COLORS[z['outcome']];width=7 if chosen else 2
            result+=f'<rect x="{x1:.3f}" y="{y1:.3f}" width="{x2-x1:.3f}" height="{y2-y1:.3f}" fill="{color}" fill-opacity="{.22 if chosen else .03}" stroke="{color}" stroke-width="{width}"/><text x="{x1+4:.3f}" y="{y1+24:.3f}" fill="{color}">{i}{" ★" if chosen else ""} {z["outcome"]}</text>'
        result+='</svg></div>'
    else:
        result+='<p class="missing">사진 없음 — 입력에 지정된 로컬 파일을 찾을 수 없습니다. 점수와 정답만 표시합니다.</p>'
    result+='<p class="muted">박스는 평가 구역입니다. 사람 결함점이나 모델 최고반응 patch가 아닙니다. ★는 이 사례의 대상 구역입니다.</p>'
    return result+zone_table(photo,selected)+'</section>'


def summary(data,lookup):
    fn=sum(z['outcome']=='FN' for _,z in lookup.values());fp=sum(z['outcome']=='FP' for _,z in lookup.values())
    total=data['total'];result='<section class="summary"><h2>전체 구역과 순위 진단</h2>'
    result+=f'<p>구역 {data["rows_count"]:,}개 · 사진 {data["groups_count"]:,}장 · 결함 {data["positive"]:,} / 정상 {data["negative"]:,}. 누락 {fn}/{data["positive"]} ({100*fn/data["positive"]:.4f}%), 오탐 {fp}/{data["negative"]} ({100*fp/data["negative"]:.4f}%). 저장 점수 표시만 하므로 모델 성능 변화는 없습니다.</p>'
    result+='<div class="scroll"><table><tr><th>비교 관계</th><th>쌍 수 / 전체 쌍 비중</th><th>오순위 / 동점</th><th>오류 credit / 전체 오류 비중</th><th>AUC</th></tr>'
    for b in [dict(total,key='total')]+data['buckets']:
        label='전체' if b['key']=='total' else LABELS[b['key']]
        auc='해당 없음 (쌍 0개)' if b['auc'] is None else f'{b["auc"]:.9f}'
        result+=f'<tr><td>{label}</td><td>{b["pairs"]:,} / {100*b["pairs"]/total["pairs"]:.4f}%</td><td>{b["strict_inversions"]:,} / {b["ties"]:,}</td><td>{b["error_credit"]:g} / {100*b["loss_share"]:.4f}%</td><td>{auc}</td></tr>'
    result+='</table></div><p class="muted">AUC = 1 − (오순위 수 + 동점 수 × 0.5) / 쌍 수. 전체 AUC는 구간별 AUC의 쌍 수 가중평균입니다. 순위 오차와 threshold 0.5의 누락·오탐은 다른 지표입니다.</p></section>'
    return result


def render_document(data,input_path,output_path,progress):
    input_path=Path(input_path).resolve();output_path=Path(output_path).resolve()
    lookup=validate_report(data)
    result='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>오순위 사진쌍 검토</title><style>'+CSS+'</style><main><h1>오순위 사진쌍 검토</h1>'
    result+=f'<p><span class="pill">저장 점수 진단</span> <span class="pill">새 학습·추론 0회</span> <span class="pill">독립 평가 아님</span></p><p>개발 진척 {progress["score"]}/{progress["max_score"]} ({html.escape(progress["criterion_version"])}). 고정 관리 점수이며 정확도와 다릅니다.</p>'
    result+=f'<p class="muted">진단 소스: {html.escape(data["source_sha"])}<br>viewer 소스 SHA256: {hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}</p>'
    result+='<p class="notice">각 비교 관계의 오순위 margin 상위 사례입니다. 전체 오류를 대표하거나 원인을 증명하지 않습니다. 다른 fold는 서로 다른 학습 head의 점수 비교입니다. 큰 구간의 오류 수는 전체 쌍 비중과 함께 해석하세요. 라벨·모델·threshold·손실 가중치는 변경하지 않았습니다.</p>'
    result+=summary(data,lookup)
    result+=f'<h2>오순위 사례 {len(data["examples"])}쌍</h2><p>왼쪽은 사람 정답이 결함인 구역, 오른쪽은 정상인 구역입니다. 모델이 정상 구역에 더 높은 점수를 준 경우를 나란히 표시합니다.</p><nav>'
    for i,e in enumerate(data['examples'],1):result+=f'<a href="#pair{i}">사례 {i}</a> · '
    result+='</nav>'
    for i,e in enumerate(data['examples'],1):
        dp,dz=lookup[e['defect_id']];np,nz=lookup[e['normal_id']]
        result+=f'<article class="pair-case" data-pair="{i}" id="pair{i}"><h2>사례 {i} · {LABELS[e["bucket"]]}</h2><p>정상 − 결함 점수차: <strong>{e["normal_minus_defect"]:.9f}</strong> · 결함 {e["defect_score"]:.9f} / 정상 {e["normal_score"]:.9f}</p><div class="pair">'
        result+=photo_panel(dp,dz['id'],input_path,output_path)+photo_panel(np,nz['id'],input_path,output_path)
        result+='</div><p><a href="#gallery">전체 사진·구역 보기</a></p></article>'
    result+='<h2 id="gallery">전체 사진·구역</h2><p>기존 사람 정답과 저장 점수입니다. 구역 박스의 경계 반올림 오차는 화면 안에서만 잘라 표시하며 원본 JSON을 바꾸지 않습니다.</p>'
    for i,photo in enumerate(data['photos']):
        result+=f'<article class="gallery-photo" data-gallery="{i}" data-gallery-zones="{len(photo["zones"])}"><h2>사진 {i+1}</h2>'+photo_panel(photo,None,input_path,output_path)+'</article>'
    result+='<section class="summary"><h2>범위와 한계</h2><p>새 학습·사진 추론·정상 통계 추정은 하지 않았습니다. 관찰 제한의 누락·오탐, 독립 일반화, 개별 시각 원인은 이 화면으로 검증하지 않았습니다. 원래 모델 채택 기준을 바꾸지 않았고 운영 모델 변경도 없습니다. 조회에 사용한 원본 JSON과 사진을 보존했습니다.</p></section></main></html>'
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();input_path=args.input.resolve();output_path=args.output.resolve()
    if input_path==output_path:raise ValueError('Output must not overwrite the source JSON')
    data=json.loads(input_path.read_text())
    root=Path(__file__).resolve().parents[3]
    progress=json.loads((root/'development-progress.json').read_text())
    document=render_document(data,input_path,output_path,progress)
    output_path.parent.mkdir(parents=True,exist_ok=True);output_path.write_text(document)
    print(json.dumps(dict(photos=data['groups_count'],regions=data['rows_count'],pairs_displayed=len(data['examples']),new_training_calls=0,new_inference_calls=0),ensure_ascii=False))


if __name__=='__main__':
    main()
