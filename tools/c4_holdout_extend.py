"""Extend the C4 holdout with the next N candidates of the SAME seeded shuffle (no model, no measurer score, no auto box). Asserts the first 240 equal the existing pool so nothing overlaps."""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from c4_expansion_pool import N_HOLDOUT, N_TRAIN, SEED, candidates  # noqa: E402


def main(pool_json, out_json, count):
    used = json.loads(Path(pool_json).read_text())
    pool = candidates()
    random.Random(SEED).shuffle(pool)
    n = N_HOLDOUT + N_TRAIN
    assert [r['id'] for r in pool[:n]] == [r['id'] for r in used], 'pool order changed'
    ext = [dict(r, role='holdout_ext', side='front') for r in pool[n:n + count]]
    Path(out_json).write_text(json.dumps(ext, ensure_ascii=False, indent=1))
    return len(ext), len(pool)


if __name__ == '__main__':
    print(main(sys.argv[1], sys.argv[2], int(sys.argv[3])))
