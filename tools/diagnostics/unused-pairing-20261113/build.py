"""미사용·비봉인·비예약 eBay 그룹 중 사진 2~12장 그룹을 시드 표본 200개 뽑아 번호 붙인 모자이크와 판정 배치 생성. 학습·추론 0."""
import glob, hashlib, json, os, random, re
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps
OUT = Path('artifacts/unused-pairing-20261113'); SEED = 20261113; N = 200; ABS = Path.cwd() / OUT
used = set()
for f in glob.glob('artifacts/experiments/*/observations.json'):
    try:
        for r in json.load(open(f))['rows']:
            if isinstance(r, dict) and 'group' in r: used.add(r['group'])
    except Exception: pass
seal = set()
for f in glob.glob('artifacts/d1*/SEALED.json'): seal |= set(re.findall(r'ebay-pair-[0-9a-f]+', open(f).read()))
reserved = set()
for f in glob.glob('artifacts/ebay-intake-*/candidates*.jsonl'):
    for line in open(f): reserved.add(json.loads(line)['group'])
dirs = {}
for d in sorted(glob.glob('artifacts/ebay-intake-*/ebay-pair-*')):
    g = os.path.basename(d)
    if g in used or g in seal or g in reserved: continue
    ph = sorted(glob.glob(d + '/photo-*.jpg'), key=lambda p: int(re.findall(r'photo-(\d+)', p)[0]))
    if 2 <= len(ph) <= 12: dirs[g] = ph
rng = random.Random(SEED); pick = rng.sample(sorted(dirs), min(N, len(dirs)))
(OUT / 'sheets').mkdir(parents=True, exist_ok=True); meta = []
for g in pick:
    ph = dirs[g]; code = 'p' + hashlib.sha256(f'{SEED}:{g}'.encode()).hexdigest()[:8]; T = 300; cols = 4; rows_ = (len(ph) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * T, rows_ * T), (40, 40, 40))
    for i, p in enumerate(ph):
        with Image.open(p) as im: im = ImageOps.exif_transpose(im).convert('RGB'); im.thumbnail((T - 8, T - 8))
        x, y = (i % cols) * T + 4, (i // cols) * T + 4; sheet.paste(im, (x, y)); d = ImageDraw.Draw(sheet); d.rectangle([x, y, x + 34, y + 26], fill=(200, 0, 0)); d.text((x + 6, y + 6), str(i + 1), fill=(255, 255, 255))
    sheet.save(OUT / 'sheets' / f'{code}.jpg', 'JPEG', quality=88); meta.append(dict(group=g, code=code, photos=[os.path.basename(p) for p in ph], intake=os.path.basename(os.path.dirname(ph[0]))))
json.dump(meta, open(OUT / 'sample_meta.json', 'w'), indent=1)
for b in range(10):
    part = meta[b * 20:(b + 1) * 20]; json.dump(dict(batch=b + 1, items=[str(ABS / 'sheets' / f"{m['code']}.jpg") for m in part], codes=[m['code'] for m in part]), open(OUT / f'batch_{b + 1}.json', 'w'), indent=1)
(OUT / 'responses').mkdir(exist_ok=True)
print('eligible', len(dirs), 'picked', len(pick), 'excluded reserved/used/sealed', len(reserved), len(used), len(seal))
