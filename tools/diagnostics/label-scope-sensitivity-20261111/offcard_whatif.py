"""기준 3 what-if(사전 정의): 마스크상 카드 밖 후보 구역은 판단불가로 보고 평가에서 제외. 나머지는 기존 S1 규칙(defect 판정→결함 가정).
변경 변수 1개 = 카드 밖 제외. 학습·추론·라벨 변경 0, 저장 점수 재계산만. 마스크 근사 → 참고용."""
import json
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from analyze import load, scenario, OUT
MASK = Path('artifacts/card-foreground-diagnostic-20261111/rows2.json')


def main():
    rows, judg = load(); mask = {r['id']: bool(r['bad'] or r['center_out']) for r in json.load(open(MASK))}
    miss = [i for i in judg if i not in mask]; assert not miss, miss[:3]
    off = {i for i in judg if mask[i]}
    cnt = Counter((rows[i]['target'], judg[i], mask[i]) for i in judg)
    kept = {i: r for i, r in rows.items() if i not in off}
    res = dict(candidates=len(judg), off_card=len(off), by_judgment_off=dict(Counter(judg[i] for i in off)),
               breakdown={f'target{t}/{j}/{"off" if o else "on"}': c for (t, j, o), c in sorted(cnt.items())},
               S0_baseline=scenario(rows, {}, False), S1_defect_as_target=scenario(rows, judg, False),
               N1_offcard_excluded=scenario(kept, judg, False), N1b_offcard_and_unknown_excluded=scenario(kept, judg, True))
    (OUT / 'offcard_whatif.json').write_text(json.dumps(res, indent=1, ensure_ascii=False)); print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
