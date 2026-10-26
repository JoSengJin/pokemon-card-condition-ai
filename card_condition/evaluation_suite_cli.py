"""Assess saved role reports against their frozen input/candidate pins, without inference."""
import argparse
import json
import sys
from .evaluation_suite import assess_suite


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m card_condition.evaluation_suite_cli')
    parser.add_argument('manifest')
    parser.add_argument('seal')
    parser.add_argument('candidate')
    parser.add_argument('output')
    parser.add_argument('--seal-sha256', required=True)
    parser.add_argument('--candidate-sha256', required=True)
    for name in ('region', 'side', 'observation'):
        parser.add_argument('--' + name)
        parser.add_argument('--' + name + '-sha256')
    args = parser.parse_args(argv)
    reports = {name + '_final': dict(path=getattr(args, name), sha256=getattr(args, name + '_sha256'))
               for name in ('region', 'side', 'observation') if getattr(args, name)}
    try:
        report = assess_suite(args.manifest, args.seal, args.seal_sha256, args.candidate,
                              args.candidate_sha256, reports, args.output)
    except (ValueError, OSError, RuntimeError) as exc:
        print(json.dumps(dict(error=str(exc)), ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(dict(numeric_gates=report['numeric_gates'], d1_verified=False, d2_verified=False, d3_verified=False)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
