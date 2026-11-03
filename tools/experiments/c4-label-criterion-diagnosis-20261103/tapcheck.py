"""Diagnosis only (no model, holdout untouched): compare the user's 'narrow side' answers and tap-line verdicts on 8 discordant train fronts with the human-tapped border widths."""
import json
A = 'artifacts/c4-expansion-20261103/'
rows = {r['id']: r for r in json.load(open(A + 'tapcheck-rows.json'))}
for l in open(A + 'answers-tapcheck.txt', encoding='utf-8'):
    i, _, ln, nw = l.strip().split('|')
    r = rows[i]
    w = dict(top=r['inner_top'] - r['outer_top'], bottom=r['outer_bottom'] - r['inner_bottom'], left=r['inner_left'] - r['outer_left'], right=r['outer_right'] - r['inner_right'])
    tb = abs(w['top'] - w['bottom']) / (w['top'] + w['bottom']); lr = abs(w['left'] - w['right']) / (w['left'] + w['right'])
    print(r['label'], i[-6:], ln, nw, 'tb=%.2f lr=%.2f' % (tb, lr))
