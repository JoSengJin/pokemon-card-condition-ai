"""Freeze an explicit model bundle for an already sealed test; no inference or training."""
import argparse
import json
import sys
from .frozen_candidate import pin_candidate
from .release import file_sha256


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m card_condition.frozen_candidate_cli')
    parser.add_argument('manifest')
    parser.add_argument('seal')
    parser.add_argument('output')
    parser.add_argument('--seal-sha256', required=True)
    parser.add_argument('--device', required=True, choices=('cpu', 'mps'))
    parser.add_argument('--region')
    parser.add_argument('--side')
    parser.add_argument('--observation')
    args = parser.parse_args(argv)
    models = {role + '_final': getattr(args, role) for role in ('region', 'side', 'observation') if getattr(args, role)}
    try:
        pin_candidate(args.seal, args.seal_sha256, args.manifest, models, args.output, args.device)
    except (ValueError, OSError) as exc:
        print(json.dumps(dict(error=str(exc)), ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(dict(candidate_sha256=file_sha256(args.output), d2_verified=False)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
