"""승격 판정(탐색 → 확증 전 단계, 설계 6-3). 통과/미달과 사유 목록을 돌려준다. 순수 함수, stdlib만 쓴다.

확증(McNemar·순열 검정), 봉인 평가 실행, 승격 예산·조회 장부, Champion 승격은 이 파일의 범위 밖이다.
"""
import hashlib
import json
import math
from operator import itemgetter

from .bootstrap import paired_bootstrap, sensitivity
from .scoring import ABSTAIN_ABSOLUTE, ABSTAIN_MARGIN, abstain_cap, report
from .scoring_rows import check_group_overlap

QUANTILE = 0.10  # 80% 구간의 하한 = 개선량 분포의 10번째 백분위
_TOLERANCE = 1e-12


def _why(code, message):
    return {"code": code, "message": message}


def _check_config(noise_rate, direction_min_fraction, replicates, trials, delta):
    for name, value in (("noise_rate", noise_rate), ("direction_min_fraction", direction_min_fraction), ("delta", delta)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError("%s는 0 이상의 유한한 숫자여야 한다: %r" % (name, value))
    if noise_rate > 1 or direction_min_fraction > 1:
        raise ValueError("noise_rate와 direction_min_fraction은 1 이하여야 한다")
    if replicates < 1 or trials < 1:
        raise ValueError("replicates와 trials는 1 이상이어야 한다")


def _fingerprint(rows):
    """입력 행 전체의 sha256(id 순 정렬, 행 순서 무관). 같은 입력을 다시 모아 재현할 때 대조한다."""
    text = json.dumps(sorted(rows, key=itemgetter("id")), sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _reasons(base, cand, boot, sens, cap, min_fraction, delta):
    """깨진 조건을 코드와 함께 모은다. 분모 0(미측정)은 통과로 세지 않고 사유로 남긴다."""
    out = []
    lower = boot["lower"]
    if not isinstance(lower, float):
        out.append(_why("bootstrap_unmeasured", "결함 구역이 없어 누락 감소를 측정할 수 없다"))
    elif not lower > 0:
        out.append(_why("bootstrap_lower_not_positive", "카드 단위 부트스트랩 80%% 구간 하한 %.4f이 0보다 크지 않다" % lower))
    if isinstance(boot["point"], float) and sens["fraction"] < min_fraction:
        out.append(_why("direction_unstable", "라벨 잡음 시행에서 개선 방향 유지 비율 %.4f < 기준 %.4f" % (sens["fraction"], min_fraction)))
    rate_b, rate_c = base["false_alarm"]["rate"], cand["false_alarm"]["rate"]
    if not (isinstance(rate_b, float) and isinstance(rate_c, float)):
        out.append(_why("false_alarm_unmeasured", "정상 구역이 없어 오탐 비열등을 측정할 수 없다"))
    elif rate_c - rate_b > delta + _TOLERANCE:
        out.append(_why("false_alarm_not_noninferior", "후보 오탐률 %.4f − 기준 %.4f > 허용 %.4f" % (rate_c, rate_b, delta)))
    if not cap["checked"]:
        out.append(_why("abstain_unmeasured", "보류율을 측정한 층이 없다"))
    for item in cap["violations"]:
        out.append(_why("abstain_cap", "층 %s 보류율 %.4f > 상한 %.4f(기준 %.4f)" % (
            item["layer"], item["candidate"], item["limit"], item["baseline"])))
    return out


def evaluate(rows, *, noise_rate, direction_min_fraction, replicates=2000, trials=1000, seed=0, delta=0.05):
    """A(pred_a, 기준)와 B(pred_b, 후보)를 같은 구역에서 비교해 승격 가능 여부를 판정한다.

    noise_rate·direction_min_fraction은 사전 등록 값이라 기본값이 없다. 사유 목록이 비어 있어야 "통과".
    """
    _check_config(noise_rate, direction_min_fraction, replicates, trials, delta)
    check_group_overlap(rows)
    base, cand = report(rows, "pred_a"), report(rows, "pred_b")
    boot = paired_bootstrap(rows, replicates, seed, QUANTILE)
    sens = sensitivity(rows, noise_rate, trials, seed)
    cap = abstain_cap(base, cand)
    reasons = _reasons(base, cand, boot, sens, cap, direction_min_fraction, delta)
    return {
        "verdict": "미달" if reasons else "통과", "reasons": reasons,
        "baseline": base, "candidate": cand, "bootstrap": boot, "sensitivity": sens, "abstain_cap": cap,
        "config": {"noise_rate": noise_rate, "direction_min_fraction": direction_min_fraction,
                   "replicates": replicates, "trials": trials, "seed": seed, "delta": delta, "quantile": QUANTILE,
                   "abstain_margin": ABSTAIN_MARGIN, "abstain_absolute": ABSTAIN_ABSOLUTE},
        "inputs": {"rows_sha256": _fingerprint(rows), "n_rows": len(rows), "gold_n": base["gold_n"],
                   "n_cards": boot["n_cards"], "layers": sorted(base["abstain_by_layer"])},
    }
