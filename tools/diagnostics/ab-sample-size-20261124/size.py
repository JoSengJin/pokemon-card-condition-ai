import argparse
import json
import math
import sys

CRIT = 1.6448536269514722
PC_GRID = (0, 0.001, 0.002, 0.005, 0.01, 0.02, 0.03, 0.05)
NOTES = ['계획용 계산이며 시험 결과가 아니다.',
         '가정한 pb·pc가 틀리면 장수도 틀린다. pc는 A의 오류율을 넘을 수 없다.',
         'false_pass는 pc 0~0.05 격자 8점의 값이며 그 밖은 계산하지 않았다.']


def worse_limit(m: int) -> int:
    """Largest b (b < c, b+c = m) whose two-sided exact McNemar p is below 0.05, or -1."""
    b, term, total = -1, 1, 1
    while 40 * total < 2 ** m:
        b += 1
        term = term * (m - b) // (b + 1)
        total += term
    return b


def binom(n: int, p: float) -> list[float]:
    if p in (0, 1):
        return [float(k == n * p) for k in range(n + 1)]
    top, yes, no = math.lgamma(n + 1), math.log(p), math.log1p(-p)
    return [math.exp(top - math.lgamma(k + 1) - math.lgamma(n - k + 1) + k * yes + (n - k) * no) for k in range(n + 1)]


def power_curve(pb: float, pc: float, n_max: int) -> list[float]:
    if pc == 0:
        return [0.] * (n_max + 1)
    ratio = pb / (pb + pc)
    detect = [math.fsum(binom(m, ratio)[:worse_limit(m) + 1]) for m in range(n_max + 1)]
    return [math.fsum(p * d for p, d in zip(binom(n, pb + pc), detect)) for n in range(n_max + 1)]


def tango_z(b: int, c: int, n: int, delta: float) -> float:
    lead = delta * (2 * n - b + c) - b - c
    q = (math.sqrt(lead * lead + 8 * n * c * delta * (1 - delta)) - lead) / (4 * n)
    return (b - c - n * delta) / math.sqrt(n * (2 * q + delta * (1 - delta)))


def pass_probability(n: int, delta: float, truths: list[tuple[float, float]], crit: float = CRIT) -> list[float]:
    fact = [math.lgamma(k + 1) for k in range(n + 1)]
    region = [(b, c, n - b - c, fact[n] - fact[b] - fact[c] - fact[n - b - c])
              for b in range(n + 1) for c in range(n - b + 1) if tango_z(b, c, n, delta) <= -crit]
    result = []
    for pb, pc in truths:
        # k * log(p) per category; a zero-probability category contributes only when its count is 0
        worse, better, same = [[k * math.log(p) if p > 0 else (-math.inf if k else 0.) for k in range(n + 1)]
                               for p in (pb, pc, 1 - pb - pc)]
        result.append(math.fsum(math.exp(coef + worse[b] + better[c] + same[s]) for b, c, s, coef in region))
    return result


def report(args) -> dict:
    values = vars(args)
    if not all(math.isfinite(v) for v in values.values() if isinstance(v, float)):
        raise ValueError('every number must be finite')
    if args.pb < 0 or args.pc < 0 or args.pb + args.pc >= 1:
        raise ValueError('need pb >= 0, pc >= 0, pb+pc < 1')
    result = dict(notes=NOTES, **values)
    if args.command == 'power':
        if not 1 <= args.n <= 5000:
            raise ValueError('need N 1..5000')
        result['power'] = power_curve(args.pb, args.pc, args.n)[args.n]
    elif args.command == 'need':
        if not (0 < args.target < 1 and 0 <= args.window <= 500 and 1 <= args.max_n <= 5000):
            raise ValueError('need 0 < target < 1, window 0..500, max-n 1..5000')
        curve = power_curve(args.pb, args.pc, args.max_n + args.window)
        lows = (min(curve[n:n + args.window + 1]) for n in range(1, args.max_n + 1))
        found = next(((n, low) for n, low in enumerate(lows, 1) if low >= args.target), (None, None))
        result['cards'], result['min_power_in_window'] = found
    else:
        if not (1 <= args.n <= 2000 and 0 < args.delta < 1 and args.crit > 0):
            raise ValueError('need N 1..2000, 0 < DELTA < 1, crit > 0')
        grid = [pc for pc in PC_GRID if args.delta + 2 * pc < 1]
        truths = [(args.pb, args.pc)] + [(args.delta + pc, pc) for pc in grid]
        passed, *false = pass_probability(args.n, args.delta, truths, args.crit)
        top = max(false)
        result['pass_probability'] = passed
        result['false_pass'] = dict(max=top, at_pc=float(grid[false.index(top)]),
                                    by_pc={str(pc): v for pc, v in zip(grid, false)})
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    for command, names in (('power', ('n', 'pb', 'pc')), ('need', ('pb', 'pc')), ('noninferior', ('n', 'delta', 'pb', 'pc'))):
        sub = commands.add_parser(command)
        for name in names:
            sub.add_argument(name, type=int if name == 'n' else float)
    commands.choices['need'].add_argument('--target', type=float, default=0.80)
    commands.choices['need'].add_argument('--window', type=int, default=50)
    commands.choices['need'].add_argument('--max-n', type=int, default=2000)
    commands.choices['noninferior'].add_argument('--crit', type=float, default=CRIT)
    try:
        result = report(parser.parse_args(argv))
    except (ValueError, ZeroDivisionError) as error:
        print(error, file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
