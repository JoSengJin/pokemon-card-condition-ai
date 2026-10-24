"""Standalone, opt-in CLI for the side-evidence validator; not wired into card-condition.

Exit codes: 0 accepted, 1 sidecar rejected, 2 usage error, 3 file system error.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

from .side_evidence import validate_sidecar


def write_new(output, report):
    """Publish a complete report without replacing an existing or competing file."""
    output = Path(output)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output.parent,
                                     prefix=f'.{output.name}.', suffix='.tmp') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
        os.link(stream.name, output)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m card_condition.side_evidence_cli',
                                     description='Validate a side-evidence sidecar; inputs are never modified.')
    parser.add_argument('--sidecar', required=True)
    parser.add_argument('--evidence-root', required=True)
    parser.add_argument('--output', required=True, help='new JSON report path; an existing file is never replaced')
    args = parser.parse_args(argv)
    try:
        if os.path.lexists(args.output):
            raise FileExistsError('output already exists; choose a new path')
        report = validate_sidecar(args.sidecar, args.evidence_root)
        write_new(args.output, report)
    except ValueError as error:
        print(f'side-evidence: rejected: {error}', file=sys.stderr)
        return 1
    except OSError as error:
        # The message omits file names so local absolute paths are not echoed.
        print(f'side-evidence: file error: {type(error).__name__}: {error.strerror or error}', file=sys.stderr)
        return 3
    print(f'side-evidence: accepted {len(report["rows"])} rows')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
