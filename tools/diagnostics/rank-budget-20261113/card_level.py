"""카드 단위 결함 발견 지표(rank_budget.card_operating_points 사용). 저장 점수만, 새 추론 0. 임계 격자 0.5~0.9는 결과 전에 고정."""
import json
from card_condition.rank_budget import card_operating_points
obs = json.load(open('artifacts/experiments/20261108T215307-941b3aaa/observations.json'))
r = card_operating_points(obs['scores'], [x['group'] for x in obs['rows']], [x['target'] for x in obs['rows']], [.5, .6, .7, .8, .9], label_reliability_interval=(0.234, 0.688))
json.dump(r, open('artifacts/rank-budget-20261113/card_level.json', 'w'), ensure_ascii=False, indent=1)
for p in r['points']: print(p['threshold'], p['defect_cards_found'], round(p['recall'], 3), 'miss_up', round(p['recall_miss_upper95'], 3), '|', p['normal_cards_flagged'], round(p['false_alarm'], 3), 'fa_up', round(p['false_alarm_upper95'], 3))
