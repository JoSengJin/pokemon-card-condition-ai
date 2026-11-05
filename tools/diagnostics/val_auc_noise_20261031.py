"""저장된 검증 점수만으로 AUC 차이가 검증 표집 잡음 안인지 본다(학습·모델 호출 0)."""
import json, random, sys

EXPS = {
    "o_pair": "20261031T040133-e703ba88",
    "layer8": "20261031T042719-f4e98fbd",
    "fusion": "20261031T050639-c1ab3959",
    "lastblock": "20261031T061633-13476cae",
    "band": "20261031T063300-7e27a882",
}
BASE = "artifacts/experiments/"
DRAWS, SEED = 2000, 20261031


def auc(pos, neg):
    if not pos or not neg:
        return None
    return sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg))


def load(name):
    r = json.load(open(BASE + name + "/result.json"))
    return r["rows"], r["scores"]


def main():
    data = {k: load(v) for k, v in EXPS.items()}
    rows = data["band"][0]
    for k, (rw, _) in data.items():
        assert [x["id"] for x in rw] == [x["id"] for x in rows], k
    t = [x["target"] for x in rows]
    groups = {}
    for i, x in enumerate(rows):
        groups.setdefault(x["group"], []).append(i)
    keys = list(groups)
    rng = random.Random(SEED)
    boots = {k: [] for k in data}
    for _ in range(DRAWS):
        idx = [i for g in (rng.choice(keys) for _ in keys) for i in groups[g]]
        for k, (_, s) in data.items():
            a = auc([s[i] for i in idx if t[i]], [s[i] for i in idx if not t[i]])
            if a is not None:
                boots[k].append(a)
    q = lambda v, p: sorted(v)[int(p * (len(v) - 1))]
    out = {"groups": len(keys), "rows": len(rows), "draws": DRAWS, "single_auc": {}, "ci95": {}, "paired_vs_o_pair": {}}
    for k, (_, s) in data.items():
        out["single_auc"][k] = auc([s[i] for i in range(len(t)) if t[i]], [s[i] for i in range(len(t)) if not t[i]])
        out["ci95"][k] = [q(boots[k], 0.025), q(boots[k], 0.975)]
    rng = random.Random(SEED)
    diffs = {k: [] for k in data if k != "o_pair"}
    for _ in range(DRAWS):
        idx = [i for g in (rng.choice(keys) for _ in keys) for i in groups[g]]
        pa = [i for i in idx if t[i]]; na = [i for i in idx if not t[i]]
        if not pa or not na:
            continue
        base = auc([data["o_pair"][1][i] for i in pa], [data["o_pair"][1][i] for i in na])
        for k in diffs:
            diffs[k].append(auc([data[k][1][i] for i in pa], [data[k][1][i] for i in na]) - base)
    for k, v in diffs.items():
        out["paired_vs_o_pair"][k] = {"mean": sum(v) / len(v), "ci95": [q(v, 0.025), q(v, 0.975)]}
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)


main()
