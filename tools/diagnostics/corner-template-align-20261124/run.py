"""Can phone-photo card-back corners be aligned to a clean reference? Read-only diagnostic.

Run from the repo root:  nice -n 19 .venv/bin/python tools/diagnostics/corner-template-align-20261124/run.py --check | --stage ref | --stage a | --stage b
Stage ref builds references from fit groups only. Stage a never keeps target or scores. Stage b runs only after a passes.
Rules and criteria: docs/collaboration/reports/corner-template-align-20261124.md (fixed before results).
"""
import base64, hashlib, html, importlib.util, io, json, sys
from collections import Counter
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import align as A
spec = importlib.util.spec_from_file_location('corner_size_run', HERE.parent/'corner-size-threshold-20261123/run.py')
PRIOR = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PRIOR)

OBS, OUT = PRIOR.OBS, Path('artifacts/corner-template-align-20261124')
KEYS = ('id', 'group', 'image', 'image_sha256', 'area', 'box')
ROUNDS, MIN_BLOCKS = 2, 3


def inputs(verify=False):
    """(fit rows, check rows) without labels or scores."""
    rows = [{k: r[k] for k in KEYS} for r in json.loads(OBS.read_text())['rows']]
    fit = [r for r in rows if PRIOR.in_fit(r['group'])]
    chk = [r for r in rows if not PRIOR.in_fit(r['group'])]
    assert len(rows) == 946 and not {r['group'] for r in fit} & {r['group'] for r in chk}
    if verify:
        bad, kinds = [], Counter()
        for p, h in sorted({(r['image'], r['image_sha256']) for r in rows}):
            if PRIOR.sha(p) == h:
                kinds['file'] += 1
                continue
            with Image.open(p) as src:   # the other recorded identity: decoded size + RGB pixels (cross_review_auto_results.py)
                pic = ImageOps.exif_transpose(src).convert('RGB')
            same = hashlib.sha256(str(pic.size).encode() + pic.tobytes()).hexdigest() == h
            kinds['decoded' if same else 'mismatch'] += 1
            if not same:
                bad.append(p)
        assert not bad, bad
        print('photo hashes', dict(kinds))
        print('obs sha256', PRIOR.sha(OBS))
        print('photos verified', len({r['image'] for r in rows}))
        for name, rs in (('fit', fit), ('check', chk)):
            print(name, len(rs), 'zones', len({r['group'] for r in rs}), 'groups', dict(sorted(Counter(r['area'] for r in rs).items())))
    return fit, chk


def build_references(fit):
    """Coarse median -> align -> median, ROUNDS times, per area. A zone joins the area whose reference it matches better."""
    prepared, status = [], Counter()
    for r in fit:
        st, im, tip = A.prepare_image(*A.M.oriented_crop(r))
        status[st] += 1
        if st == 'ok':
            prepared.append((r['area'], im, tip))
    stacks = {a: [A.warp(im, np.array(tip) + A.SIZE/2 - A.TIP_AT, 0, 1, A.SIZE)[0] for area, im, tip in prepared if area == a] for a in A.DIAGONAL}
    refs = {a: np.median(s, axis=0) for a, s in stacks.items()}
    log = dict(status=dict(status), start={a: len(s) for a, s in stacks.items()}, rounds=[])
    for _ in range(ROUNDS):
        infos, stacks, used = {a: A.reference_info(v) for a, v in refs.items()}, {a: [] for a in refs}, Counter()
        nccs = []
        for area, im, tip in prepared:
            got = A.best_reference(im, tip, area, refs, infos)
            if got is None:
                used['align_fail'] += 1
                continue
            rgb, _ = A.warp(im, got['center'], got['deg'], got['scale'], A.SIZE)
            stacks[got['ref']].append(A.tip_residual(rgb, refs[got['ref']], infos[got['ref']])[2])
            nccs.append(got['ncc'])
            used['own' if got['ref'] == area else 'diagonal'] += 1
        refs = {a: np.median(s, axis=0).clip(0, 255) for a, s in stacks.items()}
        log['rounds'].append(dict(used=dict(used), stack={a: len(s) for a, s in stacks.items()}, ncc_p10_50_90=np.percentile(nccs, [10, 50, 90]).round(3).tolist()))
    for a, v in refs.items():
        Image.fromarray(v.round().astype(np.uint8)).save(OUT/f'reference-{a}.png')
    (OUT/'reference-log.json').write_text(json.dumps(log, indent=1))
    print(json.dumps(log))


def load_references():
    refs = {a: np.asarray(Image.open(OUT/f'reference-{a}.png'), float) for a in A.DIAGONAL}
    return refs, {a: A.reference_info(v) for a, v in refs.items()}


def recovery(refs, infos):
    """A1: 24 seeded corner-of-range transforms per reference; mean point error (px) of each trial."""
    rng, errs = np.random.default_rng(20261124), []
    o = np.array([x + 1j*y for x in (-40, 0, 50) for y in (-40, 0, 50)])
    for a, ref in refs.items():
        # border pixels are repeated outward so the moved window never reads outside the reference
        big = Image.fromarray(np.pad(ref, ((60, 60), (60, 60), (0, 0)), 'edge').astype(np.uint8))
        for _ in range(24):
            t, deg, k = complex(*rng.uniform(-3, 3, 2)), rng.uniform(-2, 2), rng.uniform(.97, 1.03)
            u = np.exp(-1j*np.radians(deg))/k
            c0 = 120 + 120j - u*(120 + 120j + t)   # photo point -> reference point
            im = big.transform(big.size, Image.AFFINE, (u.real, -u.imag, c0.real, u.imag, u.real, c0.imag), Image.BICUBIC)
            got = A.align(im, (120, 120), ref, infos[a]['card'])
            want = 120 + 120j + t + o/u
            errs.append(99.0 if got is None else float(np.abs(complex(*got['center']) + o*np.exp(1j*np.radians(got['deg']))/got['scale'] - want).mean()))
    return errs


def stage_a(chk, refs, infos):
    """Align every check zone and write measures.json, tables.md, view.html."""
    errs, zones = recovery(refs, infos), []
    for r in chk:
        st, im, tip = A.prepare_image(*A.M.oriented_crop(r))
        z = dict(id=r['id'], group=r['group'], area=r['area'], status=st)
        got = A.best_reference(im, tip, r['area'], refs, infos) if st == 'ok' else None
        if st == 'ok' and got is None:
            z['status'] = 'align_fail'
        if got:
            info, ref = infos[got['ref']], refs[got['ref']]
            _, gray = A.warp(im, got['center'], got['deg'], got['scale'], A.SIZE + 2*A.REACH)
            rgb, _ = A.warp(im, got['center'], got['deg'], got['scale'], A.SIZE)
            res = A.block_residuals(gray, ref, info)
            z.update(got, blocks=[round(v, 2) for v in res])
            if len(res) < MIN_BLOCKS:
                z['status'] = 'few_blocks'
            else:
                z.update(median=float(np.median(res)), max=max(res), aligned=bool(np.median(res) <= 1.0 and max(res) <= 2.0))
            z['residual'], diff, matched = A.tip_residual(rgb, ref, info)
            strip = np.hstack([rgb, matched, ref, np.repeat(np.minimum(diff*3, 255)[..., None], 3, 2)])
            buf = io.BytesIO()
            Image.fromarray(strip.clip(0, 255).astype(np.uint8)).save(buf, 'JPEG', quality=80)
            z['_img'] = base64.b64encode(buf.getvalue()).decode()
        zones.append(z)
    n, meas, ok = len(zones), [z for z in zones if z['status'] == 'ok'], [z for z in zones if z.get('aligned')]
    med, mx = np.array([z['median'] for z in meas]), np.array([z['max'] for z in meas])
    own = Counter('own' if z['ref'] == z['area'] else 'diagonal' for z in meas)
    s = dict(inputs={str(p): PRIOR.sha(p) for p in (OBS, HERE/'align.py', HERE/'run.py', *(OUT/f'reference-{a}.png' for a in refs))},
             a1=dict(n=len(errs), median=float(np.median(errs)), p90=float(np.percentile(errs, 90)), passed=bool(np.median(errs) <= .5)),
             zones=n, photos=len({z['group'] for z in zones}), measurable=PRIOR.rate(len(meas), n), aligned=PRIOR.rate(len(ok), n),
             status=PRIOR.count(z['status'] for z in zones), matched_reference=dict(own), median_shift_p10_50_90=np.percentile(med, [10, 50, 90]).round(2).tolist(),
             max_shift_p10_50_90=np.percentile(mx, [10, 50, 90]).round(2).tolist(),
             ncc_p10_50_90=np.percentile([z['ncc'] for z in meas], [10, 50, 90]).round(3).tolist(),
             fail_split=dict(median_only=int(((med > 1) & (mx <= 2)).sum()), max_only=int(((med <= 1) & (mx > 2)).sum()), both=int(((med > 1) & (mx > 2)).sum())),
             by_area={a: dict(zones=sum(z['area'] == a for z in zones), measurable=sum(z['area'] == a for z in meas), aligned=sum(z['area'] == a for z in ok)) for a in refs},
             blocks={a: i['blocks'] for a, i in infos.items()})
    s['a2_pass'] = len(meas) >= .7*n and len(ok) >= .6*n
    s['a_pass'] = bool(s['a1']['passed'] and s['a2_pass'])
    (OUT/'measures.json').write_text(json.dumps(dict(summary=s, zones=[{k: v for k, v in z.items() if k != '_img'} for z in zones]), ensure_ascii=False, indent=1))
    (OUT/'tables.md').write_text('# corner-template-align stage A (generated)\n\n' + '\n'.join(f'- {k}: {json.dumps(v, ensure_ascii=False)}' for k, v in s.items()) + '\n')
    write_view(s, zones)
    print((OUT/'tables.md').read_text())


def write_view(s, zones):
    verdict = {True: '통과', False: '불통과'}
    reason = {'no_blue_border': '파란 테두리 아님', 'corner_cut': '끝이 크롭 밖', 'window_outside': '12mm 창이 크롭 밖', 'align_fail': '정렬 실패', 'few_blocks': '무늬 블록 부족'}
    cards = []
    for z in sorted(zones, key=lambda z: (z['status'] != 'ok', not z.get('aligned'), z.get('max', 0), z['id'])):
        if z['status'] == 'ok':
            line = f"{'정렬됨' if z['aligned'] else '정렬 안 됨'} · 잔여 이동 중앙 {z['median']:.2f}px 최대 {z['max']:.2f}px · 맞춘 기준 {z['ref']}{'' if z['ref'] == z['area'] else ' (대각)'}"
        else:
            line = '제외: ' + reason.get(z['status'], z['status'])
        img = f'<img loading="lazy" alt="" src="data:image/jpeg;base64,{z["_img"]}">' if '_img' in z else ''
        cards.append(f"<article><b>{html.escape(z['id'])}</b><p>{line}</p>{img}</article>")
    m, a = s['measurable'], s['aligned']
    excl = ', '.join(f"{reason[k]} {v}" for k, v in s['status'].items() if k != 'ok') or '없음'
    (OUT/'view.html').write_text(
        '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>모서리 기준 이미지 정렬</title>'
        '<style>body{font:16px/1.5 system-ui;margin:12px;max-width:560px;background:#fff;color:#111}img{width:100%;display:block}article{border:1px solid #bbb;border-radius:8px;padding:8px;margin:8px 0;overflow-wrap:anywhere}p{margin:4px 0}</style>'
        f"<h1>모서리 기준 이미지 정렬: A단계 {verdict[s['a_pass']]}</h1><p><b>개발 자료 진단, 모델 성능 아님.</b> 개발 진척률 78/100 불변(usable-card-analysis-v1.14). 모델 학습·추론 0, 사람 정답·모델 점수를 읽지 않았습니다.</p>"
        f"<ul><li>검증 구역 {s['zones']}개(사진 {s['photos']}장)</li><li>측정 가능 {m['k']}/{m['n']} = {m['rate']:.1%} (기준 70%)</li><li>정렬됨 {a['k']}/{a['n']} = {a['rate']:.1%} (기준 60%)</li>"
        f"<li>제외: {excl}</li><li>합성 복원 오차 중앙값 {s['a1']['median']:.2f}px (기준 0.5px): {verdict[s['a1']['passed']]}</li></ul>"
        f"<p>검증 소스 SHA256: align.py {s['inputs'][str(HERE/'align.py')][:12]}, run.py {s['inputs'][str(HERE/'run.py')][:12]}. 검사 명령·변경 파일·리스크·롤백: docs/collaboration/reports/corner-template-align-20261124.md</p>"
        '<p>각 줄 그림: 정렬한 크롭 · 밝기 맞춘 크롭 · 기준 이미지 · 차이(잔차, 3배 밝게). 정렬이 안 된 구역의 차이는 결함을 뜻하지 않습니다.</p>' + ''.join(cards) + '</html>')


if __name__ == '__main__':
    OUT.mkdir(exist_ok=True)
    stage = sys.argv[sys.argv.index('--stage') + 1] if '--stage' in sys.argv else None
    fit_rows, check_rows = inputs(verify='--check' in sys.argv)
    if stage == 'ref':
        build_references(fit_rows)
    elif stage == 'a':
        stage_a(check_rows, *load_references())
    elif stage == 'b':
        sys.exit('stage b is not open: stage A must pass first')
