"""Command line for the pinned back triage release: JSON request in, JSON out. Any release or input problem is an explicit hold, never a normal verdict."""
import argparse
import json
import sys
import time

from .back_triage_release import load_suite, read_release
from .back_triage_usage import entry_for, record, summarize

REQUIRED = {'id', 'side', 'image', 'box', 'box_reviewed'}


def held(reason, request_id=None):
    return dict(id=request_id, status='held', reason=reason, fallback='existing_path', complete=False)


def main(argv=None):
    ap = argparse.ArgumentParser(prog='card-condition-back-triage')
    ap.add_argument('--release')
    ap.add_argument('--request')
    ap.add_argument('--device', default='cpu', choices=('cpu', 'mps'))
    ap.add_argument('--usage-log', help='Append one JSON usage record per request (timing, outcome, hold reasons); no photo paths or messages')
    ap.add_argument('--summary', help='Summarize a usage log against the F2 conditions and exit (measurement only)')
    args = ap.parse_args(argv)
    if args.summary:
        print(json.dumps(summarize(args.summary), ensure_ascii=False, indent=2))
        return 0
    if not args.release or not args.request:
        ap.error('--release and --request are required')
    clock, began = time.perf_counter(), time.time()
    code, request, out = run(args)
    print(json.dumps(out, ensure_ascii=False))
    record(args.usage_log, entry_for(request, code, out, time.perf_counter()-clock, began))
    return code


def run(args):
    """One request: returns (exit code, request or None, output dict). Nothing is printed here."""
    try:
        request = json.loads(open(args.request, 'rb').read())
    except (OSError, ValueError):
        return 3, None, held('request_unreadable')
    if not isinstance(request, dict) or not REQUIRED <= set(request):
        return 3, None, held('request_contract_violation')
    try:
        release = read_release(args.release)
        suite = load_suite(release, args.device)
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        # only our own ValueError messages (fixed codes) are shown; OS/torch messages can contain paths
        detail = str(error) if isinstance(error, ValueError) and '/' not in str(error) else type(error).__name__
        return 2, request, held(f'release_unavailable:{detail}', request.get('id'))
    out = suite.analyze(request)
    fallback = dict(fallback='existing_path') if all(p['status'] == 'held' for p in out['results'].values()) else {}
    return 0, request, dict(out, release_id=release['release_id'], manifest_sha256=release['manifest_sha256'], **fallback)


if __name__ == '__main__':
    sys.exit(main())
