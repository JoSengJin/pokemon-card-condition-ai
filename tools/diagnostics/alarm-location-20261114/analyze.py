"""From the input checkout: python /path/to/analyze.py (one fresh output directory)."""
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from statistics import NormalDist

import numpy as np

from inputs import check, load_cards

HERE = Path(__file__).resolve().parent
OUT = Path('artifacts/alarm-location-20261114')


def interval(k, n):
    z = NormalDist().inv_cdf(.975)
    p = k / n
    mid = p + z*z/(2*n)
    width = z * (p*(1-p)/n + z*z/(4*n*n))**.5
    return [(mid-width)/(1+z*z/n), (mid+width)/(1+z*z/n)]


def summarize(zones):
    ranked = sorted(zones, key=lambda z: (-z['score'], z['id']))
    counts = Counter(z['a'] for z in ranked)
    a = 'defect' if counts['defect'] else 'normal' if counts['unknown']+counts['split'] <= 2 else 'undetermined'
    return dict(a=a, top=ranked[0], maximum_ties=[z['id'] for z in ranked if z['score']==ranked[0]['score']], zones=ranked)


def measure(cards, threshold, draws, expected):
    defect = [cards[g] for g in sorted(cards) if cards[g]['a']=='defect']
    alerts = [c for c in defect if c['top']['score'] >= threshold]
    known = [c for c in alerts if c['top']['a'] in ('normal','defect')]
    tops = Counter(c['top']['a'] for c in alerts)
    ids = {g:c['top']['a'] if c['top']['score'] >= threshold else 'miss' for g,c in cards.items() if c['a']=='defect'}
    counts = [len(alerts),len(known),len(alerts)-len(known),len(defect)-len(alerts)]
    if threshold == .5 and counts[2] >= 7:
        raise ValueError(f'측정 불능 · 분모 불일치 {ids} expected={expected} observed={counts}')
    check(f'{threshold} alert/known/unresolved/miss {ids}', expected, counts)
    all_d = np.array([sum(z['a']=='defect' for z in c['zones']) for c in defect])
    hit = np.array([sum(z['a']=='defect' and z['score']>=threshold for z in c['zones']) for c in defect])
    boot = hit[draws].sum(axis=1)/all_d[draws].sum(axis=1)
    k, n = tops['defect'], len(known)
    any_hit = int((hit>0).sum())
    cross = {h:{a:sum(c['top']['human']==h and c['top']['a']==a for c in known)
                for a in ('normal','defect')} for h in ('normal','defect')}
    check('cross total', n, sum(sum(row.values()) for row in cross.values()))
    strata = {}
    for off in (False, True):
        part = [c for c in known if c['top']['off']==off]
        strata[str(off)] = [sum(c['top']['a']=='defect' for c in part),len(part)]
    candidate = {label:dict(Counter(c['top']['candidate'] or 'absent' for c in subset))
                 for label,subset in [('alerts',alerts),('assessable',known)]}
    chance = np.mean([sum(z['a']=='defect' for z in c['zones'])/len(c['zones']) for c in known])
    return dict(counts=counts, unknown=tops['unknown'], split=tops['split'], cross=cross, off=strata,
                candidate=candidate, chance=float(chance), L1=[k,n,interval(k,n)],
                L2=[any_hit,len(alerts),interval(any_hit,len(alerts))],
                L3=[int(hit.sum()),int(all_d.sum()),np.percentile(boot,[2.5,97.5]).tolist()])


def decide(primary):
    k = primary['L1'][0]
    if k >= 14:
        return '②', '표면 오경보 감소 설계'
    if k >= 9:
        return '④', '혼재로 판정 보류'
    cross = primary['cross']
    difference = cross['defect']['normal'] - cross['normal']['normal']
    if difference > 0:
        return '③', '0.5 ≤ 점수 < 0.8의 확대 확인 권장 출력 분리 검토'
    if difference < 0:
        return '③', '위치 근거 부족 해소 설계'
    return '③', '혼재로 판정 보류'


if __name__ == '__main__':
    plan = json.loads((HERE/'prereg.json').read_text())
    sha = subprocess.check_output(['git','-C',str(HERE),'log','-1','--format=%H','--','prereg.json'],text=True).strip()
    hashes = {}
    for source in [HERE/'prereg.json', HERE/'analyze.py', HERE/'inputs.py', Path(plan['inputs']['rule_source_read_only'])]:
        hashes['tools/diagnostics/alarm-location-20261114/'+source.name if source.is_absolute() else str(source)] = hashlib.sha256(source.read_bytes()).hexdigest()
    OUT.mkdir(exist_ok=False)
    try:
        cards = {g:summarize(zones) for g,zones in load_cards(plan,hashes).items()}
        exp = plan['expected']
        card_counts = Counter(c['a'] for c in cards.values())
        zone_counts = Counter(z['a'] for c in cards.values() for z in c['zones'])
        check(f'cards {sorted(cards)}', exp['cards'], len(cards))
        check('sample zones '+str({g:len(c['zones']) for g,c in cards.items()}), exp['zones'], sum(zone_counts.values()))
        check('card A '+str({g:c['a'] for g,c in cards.items()}), exp['card_a'], dict(card_counts))
        check('defect zone IDs '+str([z['id'] for c in cards.values() for z in c['zones'] if z['a']=='defect']),exp['defect_zones'], zone_counts['defect'])
        draws = np.random.default_rng(20261114).integers(26,size=(2000,26))
        metrics = {t:measure(cards,float(t),draws,expected) for t,expected in exp['by_threshold'].items()}
        result = dict(status='completed', decision=decide(metrics['0.5']), metrics=metrics, card_counts=card_counts,
                      zone_counts=zone_counts, tied_cards=sum(len(c['maximum_ties'])>1 for c in cards.values()), cards=cards)
    except (ValueError, KeyError, OSError) as error:
        result = dict(status='stopped', decision=['①','자료 연결 및 분모 확인'],error=str(error))
    result.update(prereg_commit=sha,sha256=hashes)
    (OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(result['status'], result['decision'], result.get('error',''))
    if result['status']=='stopped':
        raise SystemExit(1)
    for t,m in metrics.items():
        print(t, m['counts'], m['L1'], m['L2'], m['L3'])
