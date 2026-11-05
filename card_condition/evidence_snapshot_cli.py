"""Standalone, opt-in CLI for the snapshot integrity audit; not wired into card-condition.

Exit codes: 0 verified, 1 snapshot rejected, 2 usage error, 3 file system error.
"""
import argparse
import os
import sys

from .evidence_snapshot import audit_snapshot
from .side_evidence_cli import write_new


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m card_condition.evidence_snapshot_cli',
                                     description='Check snapshot payload bytes against an index; inputs are never modified.')
    parser.add_argument('--index', required=True)
    parser.add_argument('--evidence-root', required=True)
    parser.add_argument('--output', required=True, help='new JSON report path; an existing file is never replaced')
    args = parser.parse_args(argv)
    try:
        if os.path.lexists(args.output):
            raise FileExistsError('output already exists; choose a new path')
        report = audit_snapshot(args.index, args.evidence_root)
        write_new(args.output, report)
    except ValueError as error:
        print(f'evidence-snapshot: rejected: {error}', file=sys.stderr)
        return 1
    except OSError as error:
        # The message omits file names so local absolute paths are not echoed.
        print(f'evidence-snapshot: file error: {type(error).__name__}: {error.strerror or error}', file=sys.stderr)
        return 3
    print(f'evidence-snapshot: verified {report["entries_verified"]} payloads (integrity only)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
