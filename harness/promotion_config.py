"""승격 판정 설정 검사. 사전 등록 값(기본값 없음)과 실행 값의 형식·범위를 확인한다. 순수 함수, stdlib만 쓴다."""
import math

# 이름: (0을 허용하나, 1을 허용하나). 모두 0~1 구간의 유한한 숫자.
_UNIT = {"noise_rate": (False, False), "direction_min_fraction": (False, True),
         "min_valid_fraction": (False, True), "delta": (True, True)}
_INTEGERS = ("seed", "replicates", "trials", "min_defect_cards")


def check_config(config):
    """설정 dict의 값을 검사한다. 범위 밖이면 ValueError. bool·NaN·무한대는 숫자로 받지 않는다."""
    for name in _INTEGERS:
        value = config[name]
        if isinstance(value, bool) or not isinstance(value, int) or (name != "seed" and value < 1):
            raise ValueError("%s는 정수여야 하고 seed 외에는 1 이상이어야 한다: %r" % (name, value))
    for name, (zero_ok, one_ok) in _UNIT.items():
        value = config[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("%s는 유한한 숫자여야 한다: %r" % (name, value))
        if not ((value >= 0 if zero_ok else value > 0) and (value <= 1 if one_ok else value < 1)):
            raise ValueError("%s는 구간 %s0, 1%s 안이어야 한다: %r" % (name, "[" if zero_ok else "(", "]" if one_ok else ")", value))
