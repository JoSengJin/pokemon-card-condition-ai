"""Explicit offline test-input sealing. No model fitting, inference or independence certification."""
import argparse
import json
import sys

from .frozen_test import seal_test
from .release import file_sha256


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m card_condition.frozen_test_cli')
    parser.add_argument('manifest')
    parser.add_argument('output')
    parser.add_argument('--history', action='append', required=True)
    args = parser.parse_args(argv)
    try:
        seal_test(args.manifest, args.history, args.output)
    except (ValueError, OSError) as exc:
        print(json.dumps(dict(error=str(exc)), ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(dict(seal_sha256=file_sha256(args.output), d1_verified=False, d2_verified=False)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
