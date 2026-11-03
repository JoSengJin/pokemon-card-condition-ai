"""Command line for the pinned back triage release: JSON request in, JSON out. Any release or input problem is an explicit hold, never a normal verdict."""
import argparse
import json
import sys

from .back_triage_release import load_suite, read_release

REQUIRED = {'id', 'side', 'image', 'box', 'box_reviewed'}


def held(reason, request_id=None):
    return dict(id=request_id, status='held', reason=reason, fallback='existing_path', complete=False)


def main(argv=None):
    ap = argparse.ArgumentParser(prog='card-condition-back-triage')
    ap.add_argument('--release', required=True)
    ap.add_argument('--request', required=True)
    ap.add_argument('--device', default='cpu', choices=('cpu', 'mps'))
    args = ap.parse_args(argv)
    try:
        request = json.loads(open(args.request, 'rb').read())
        if not isinstance(request, dict) or not REQUIRED <= set(request):
            print(json.dumps(held('request_contract_violation')))
            return 3
    except (OSError, ValueError):
        print(json.dumps(held('request_unreadable')))
        return 3
    try:
        release = read_release(args.release)
        suite = load_suite(release, args.device)
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(json.dumps(held(f'release_unavailable:{error}', request.get('id'))))
        return 2
    out = suite.analyze(request)
    fallback = dict(fallback='existing_path') if all(p['status'] == 'held' for p in out['results'].values()) else {}
    print(json.dumps(dict(out, release_id=release['release_id'], manifest_sha256=release['manifest_sha256'], **fallback), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
