"""승격 판정(탐색 → 확증 전 단계, 설계 6-3). 통과/미달과 사유 목록을 돌려준다. 순수 함수, stdlib만 쓴다.

확증(McNemar·순열 검정), 봉인 평가 실행, 승격 예산·조회 장부, Champion 승격은 이 파일의 범위 밖이다.
eval_tier=="sealed" 행은 확증 단계 몫이라 받지 않는다.
"""
import hashlib
import json
from operator import itemgetter

from .bootstrap import paired_bootstrap, sensitivity
from .promotion_config import check_config
from .promotion_reasons import alarm_reasons, bootstrap_reasons
from .scoring import ABSTAIN_ABSOLUTE, ABSTAIN_MARGIN, abstain_cap, improvement_split, report
from .scoring_rows import check_group_overlap

QUANTILE = 0.10  # 80% 구간의 하한 = 개선량 분포의 10번째 백분위


def _fingerprint(rows):
    """입력 행 전체의 sha256(id 순 정렬, 행 순서 무관). 같은 입력을 다시 모아 재현할 때 대조한다."""
    text = json.dumps(sorted(rows, key=itemgetter("id")), sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def evaluate(rows, *, noise_rate, direction_min_fraction, min_defect_cards, min_valid_fraction,
             replicates=2000, trials=1000, seed=0, delta=0.05):
    """A(pred_a, 기준)와 B(pred_b, 후보)를 같은 구역에서 비교해 승격 가능 여부를 판정한다.

    noise_rate·direction_min_fraction·min_defect_cards·min_valid_fraction은 사전 등록 값이라 기본값이 없다.
    사유 목록이 비어 있어야 "통과". improvement_split은 보고만 하며 판정에 쓰지 않는다.
    """
    config = {"noise_rate": noise_rate, "direction_min_fraction": direction_min_fraction,
              "min_defect_cards": min_defect_cards, "min_valid_fraction": min_valid_fraction,
              "replicates": replicates, "trials": trials, "seed": seed, "delta": delta, "quantile": QUANTILE,
              "abstain_margin": ABSTAIN_MARGIN, "abstain_absolute": ABSTAIN_ABSOLUTE}
    check_config(config)
    check_group_overlap(rows)
    if any(row["eval_tier"] == "sealed" for row in rows):
        raise ValueError("eval_tier=sealed 행은 탐색(승격) 판정에 쓸 수 없다(봉인 평가는 확증 단계 몫)")
    base, cand = report(rows, "pred_a"), report(rows, "pred_b")
    boot = paired_bootstrap(rows, replicates, seed, QUANTILE)
    sens = sensitivity(rows, noise_rate, trials, seed)
    cap = abstain_cap(base, cand)
    reasons = bootstrap_reasons(boot, sens, config) + alarm_reasons(base, cand, cap, delta)
    return {
        "verdict": "미달" if reasons else "통과", "reasons": reasons,
        "baseline": base, "candidate": cand, "bootstrap": boot, "sensitivity": sens, "abstain_cap": cap,
        "improvement_split": improvement_split(rows), "config": config,
        "inputs": {"rows_sha256": _fingerprint(rows), "n_rows": len(rows), "gold_n": base["gold_n"],
                   "n_cards": boot["n_cards"], "strata": sorted(base["abstain_by_stratum"]),
                   "eval_tiers": sorted({row["eval_tier"] for row in rows})},
    }
