"""Run an experiment with a frozen plan, code diff, paired evaluation and durable status."""
import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
from uuid import uuid4

from .regression_audit import compare_predictions
from .review import atomic_write

ROOT = Path(__file__).resolve().parents[1]


def stamp():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_file(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Experiment input must be an existing project file')
    return path


class LatestExperimentUnavailable(ValueError):
    pass


def records(root):
    found = []
    for path in (root / 'artifacts/experiments').glob('*/record.json'):
        item = read(path)
        if item.get('schema_version') != 1 or item.get('status') not in ('running', 'completed', 'failed', 'interrupted'):
            raise ValueError('Invalid common experiment record')
        datetime.fromisoformat(item['started_at'])
        if item['status'] == 'running':
            try:
                os.kill(item['pid'], 0)
            except ProcessLookupError:
                item.update(status='interrupted', finished_at=stamp(), error_kind='orphaned_process', end_time_inferred=True)
                save(path, item)
        found.append((path.parent, item))
    return sorted(found, key=lambda pair: (pair[1]['started_at'], pair[0].name), reverse=True)


def verify(folder, item):
    for name, expected in item['files'].items():
        file = (folder / name).resolve()
        if not file.is_relative_to(folder.resolve()) or sha(file) != expected:
            raise ValueError('Frozen experiment evidence changed')


def point_reference(result, rows):
    if 'point_ids' in result:
        ids, scores = result['point_ids'], result['point_scores']
    else:
        peaks = result.get('runs', {}).get('candidate', {}).get('peaks', result.get('peaks', []))
        if peaks and len(peaks) != len(rows):
            raise ValueError('Point reference row alignment is incomplete')
        pairs = [(row['id'] + ':' + str(peak['human_token']), peak['human_score'])
                 for row, peak in zip(rows, peaks)
                 if row['target'] == 1 and peak.get('human_token') is not None and peak.get('human_score') is not None]
        ids, scores = [p[0] for p in pairs], [p[1] for p in pairs]
    if scores:
        compare_predictions([1] * len(ids), scores, scores)
    return ids, scores


def acceptance_rules(rules):
    if (set(rules) != {'max_fp', 'max_fn', 'no_new_errors', 'require_actual_point_guard'}
            or any(type(rules.get(k)) is not int or rules[k] < 0 for k in ('max_fp', 'max_fn'))
            or any(type(rules.get(k)) is not bool for k in ('no_new_errors', 'require_actual_point_guard'))):
        raise ValueError('Explicit numeric acceptance and point guard are required')
    return rules


def freeze_required_cohorts(root, plan):
    from .cross_review_evidence import experiment
    declared = plan.get('required_cohorts', [])
    if not isinstance(declared, list):
        raise ValueError('Required cohorts must be a predeclared list')
    frozen, seen = [], set()
    for entry in declared:
        if (not isinstance(entry, dict) or set(entry) != {'id', 'reference_result', 'acceptance'}
                or not isinstance(entry['id'], str) or not entry['id'].strip() or entry['id'] in seen):
            raise ValueError('Required cohort IDs and references must be explicit and unique')
        seen.add(entry['id'])
        rules = acceptance_rules(entry['acceptance'])
        path = project_file(root, entry['reference_result'])
        if (path.parent / 'record.json').exists():
            previous = read(path.parent / 'record.json')
            if previous['status'] != 'completed':
                raise ValueError('An incomplete required cohort reference cannot be used')
            verify(path.parent, previous)
        reference = experiment(path)
        if reference is None:
            raise ValueError('Unsupported required cohort reference')
        ids, points = point_reference(reference['result'], reference['rows'])
        if bool(points) != rules['require_actual_point_guard']:
            raise ValueError('Required cohort point guard must preserve known actual points')
        frozen.append(dict(id=entry['id'], rows=reference['rows'], before_scores=reference['after'],
                           cohort_sha256=reference['cohort'], point_ids=ids, point_scores=points,
                           acceptance=rules, source=str(path.relative_to(root)), source_sha256=sha(path)))
    return frozen


def required_cohort_results(references, observations):
    if (not isinstance(observations, list) or not all(isinstance(r, dict) for r in observations)
            or [r.get('id') for r in observations] != [r['id'] for r in references]):
        raise ValueError('Required cohort output is missing, extra, or reordered')
    results = []
    for reference, observation in zip(references, observations):
        if (observation.get('rows') != reference['rows']
                or observation.get('point_ids', []) != reference['point_ids']):
            raise ValueError('Required cohort truth, region, or actual point identity changed')
        comparison = compare_predictions([r['target'] for r in reference['rows']], reference['before_scores'], observation['scores'])
        points = None
        if reference['point_ids']:
            points = compare_predictions([1] * len(reference['point_ids']), reference['point_scores'], observation['point_scores'])
        elif observation.get('point_scores', []):
            raise ValueError('Unconfirmed required cohort points cannot be added')
        rules, counts = reference['acceptance'], comparison['after']
        passed = (counts['fp'] <= rules['max_fp'] and counts['fn'] <= rules['max_fn']
                  and (not rules['no_new_errors'] or comparison['no_new_errors'])
                  and (not rules['require_actual_point_guard'] or points is not None and not points['new_misses']))
        results.append(dict(reference, scores=observation['scores'], comparison=comparison,
                            point_scores=observation.get('point_scores', []), point_comparison=points,
                            acceptance_passed=passed))
    return results


def prepare(root, plan, command):
    from .cross_review_evidence import experiment
    root = root.resolve()
    if plan.get('threshold', .5) != .5 or plan.get('independent', False) is not False:
        raise ValueError('Only threshold 0.5 development evaluations are supported')
    for key in ('hypothesis_id', 'hypothesis', 'change', 'success_criterion', 'failure_criterion'):
        if not isinstance(plan.get(key), str) or not plan[key].strip():
            raise ValueError('Missing experiment plan field: ' + key)
    rules = acceptance_rules(plan.get('acceptance', {}))
    reference_path = project_file(root, plan['reference_result'])
    registered_reference = reference_path.parent / 'record.json'
    if registered_reference.exists():
        prior = read(registered_reference)
        if prior.get('status') != 'completed':
            raise ValueError('An incomplete experiment cannot be the evaluation reference')
        verify(reference_path.parent, prior)
    reference = experiment(reference_path)
    if reference is None:
        raise ValueError('Unsupported paired reference result')
    ids, points = point_reference(reference['result'], reference['rows'])
    if points and not rules['require_actual_point_guard']:
        raise ValueError('Known actual human point guard cannot be disabled')
    if rules['require_actual_point_guard'] and not points:
        raise ValueError('Actual human point reference is required; do not infer missing truth')
    required = freeze_required_cohorts(root, plan)
    for previous in reference['result'].get('required_cohorts', []):
        current = next((r for r in required if r['id'] == previous['id'] and r['cohort_sha256'] == previous['cohort_sha256']
                        and r['point_ids'] == previous['point_ids'] and r['acceptance'] == previous['acceptance']), None)
        if current is None:
            raise ValueError('Existing required cohorts and criteria cannot be dropped or changed')
        current.update(before_scores=previous['scores'], point_scores=previous['point_scores'],
                       score_reference=str(reference_path.relative_to(root)))
    changes = plan.get('code_changes')
    if not isinstance(changes, list) or not changes or not command:
        raise ValueError('Code changes and an executable command are required')
    snapshots, patches = {}, []
    for index, change in enumerate(changes):
        after = project_file(root, change['path'])
        if after.suffix != '.py' or not after.is_relative_to(root / 'card_condition') and not after.is_relative_to(root / 'artifacts'):
            raise ValueError('Only explicit project Python sources may be captured')
        before = project_file(root, change['baseline']) if change['baseline'] is not None else None
        if before is not None and (before.suffix != '.py' or not before.is_relative_to(root / 'artifacts')):
            raise ValueError('Baseline must be an explicit Python snapshot in artifacts')
        old, new = before.read_text() if before else '', after.read_text()
        snapshots[f'code/{index}-before.py'] = old
        snapshots[f'code/{index}-after.py'] = new
        patches.extend(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                       fromfile=str(change['baseline'] or '/dev/null'), tofile=str(after.relative_to(root))))
    folder = root / 'artifacts/experiments' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8])
    folder.mkdir(parents=True)
    frozen = dict(plan, schema_version=1, threshold=.5, independent=False, production_adopted=False)
    save(folder / 'plan.json', frozen)
    save(folder / 'reference.json', dict(rows=reference['rows'], before_scores=reference['after'],
                                       cohort_sha256=reference['cohort'], point_ids=ids, point_scores=points,
                                       required_cohorts=required,
                                       source=str(reference_path.relative_to(root)), source_sha256=sha(reference_path)))
    for name, text in snapshots.items():
        (folder / name).parent.mkdir(exist_ok=True)
        atomic_write(folder / name, text)
    atomic_write(folder / 'changes.diff', ''.join(patches))
    files = {name: sha(folder / name) for name in ('plan.json', 'reference.json', 'changes.diff', *snapshots)}
    item = dict(schema_version=1, experiment_id=folder.name, hypothesis_id=plan['hypothesis_id'],
                status='running', stage='launch', started_at=stamp(), finished_at=None, return_code=None, pid=os.getpid(),
                command=command, files=files, source_hashes={change['path']: sha(project_file(root, change['path'])) for change in changes})
    save(folder / 'record.json', item)
    return folder, item


def complete(root, folder, item):
    from .cross_review_evidence import experiment
    verify(folder, item)
    if any(sha(project_file(root, name)) != expected for name, expected in item['source_hashes'].items()):
        raise ValueError('Experiment source changed during execution')
    ref, observation = read(folder / 'reference.json'), read(folder / 'observations.json')
    result = dict(rows=observation['rows'], before_scores=ref['before_scores'], scores=observation['scores'],
                  comparison=compare_predictions([row['target'] for row in observation['rows']], ref['before_scores'], observation['scores']),
                  independent=False, production_adopted=False)
    save(folder / 'result.json', result)
    parsed = experiment(folder / 'result.json')
    if parsed['cohort'] != ref['cohort_sha256']:
        raise ValueError('Evaluation identity/order changed; no paired comparison permitted')
    points = None
    if ref['point_ids']:
        if observation.get('point_ids') != ref['point_ids']:
            raise ValueError('Actual human point identity changed or missing')
        points = compare_predictions([1] * len(ref['point_ids']), ref['point_scores'], observation['point_scores'])
        result.update(point_ids=ref['point_ids'], point_scores=observation['point_scores'], point_comparison=points)
    plan = read(folder / 'plan.json')
    rules, counts = plan['acceptance'], result['comparison']['after']
    accepted = (counts['fp'] <= rules['max_fp'] and counts['fn'] <= rules['max_fn']
                and (not rules['no_new_errors'] or result['comparison']['no_new_errors'])
                and (not rules['require_actual_point_guard'] or points is not None and not points['new_misses']))
    required = ref.get('required_cohorts', [])
    if required or 'required_cohorts' in observation:
        evaluated = required_cohort_results(required, observation.get('required_cohorts'))
        result.update(primary_acceptance_passed=accepted, required_cohorts=evaluated)
        accepted = accepted and all(r['acceptance_passed'] for r in evaluated)
    diagnostic = observation.get('diagnostic_evidence')
    if diagnostic is not None:
        if (plan.get('experiment_kind') != 'diagnostic' or not isinstance(diagnostic,dict)
                or len(json.dumps(diagnostic,ensure_ascii=False,allow_nan=False).encode()) > 4000):
            raise ValueError('Diagnostic evidence requires a diagnostic plan and bounded finite JSON')
        result['diagnostic_evidence'] = diagnostic
        if (folder/'diagnostics.json').exists():
            item['files']['diagnostics.json'] = sha(folder/'diagnostics.json')
    result.update(acceptance_passed=accepted, hypothesis_id=plan['hypothesis_id'])
    save(folder / 'result.json', result)
    item['files']['result.json'] = sha(folder / 'result.json')


def run(root, plan, command, prepared=None, timeout=None):
    from .workspace_lock import workspace_lock
    from .development_review import after_experiment
    root = root.resolve()
    with workspace_lock(root, 'common experiment and review handoff'):
        execution = prepared if prepared is not None else prepare(root, plan, command)
        code = _run(root, plan, command, prepared=execution, timeout=timeout)
        after_experiment(root, execution[0])
        return code


def _run(root, plan, command, prepared=None, timeout=None):
    root = root.resolve()
    folder, item = prepared if prepared is not None else prepare(root, plan, command)
    if prepared is not None:
        verify(folder, item)
        if item['status'] != 'running' or item['command'] != command or read(folder / 'plan.json')['hypothesis_id'] != plan['hypothesis_id']:
            raise ValueError('Prepared execution does not match selected experiment')
    child = None
    received = signal.SIGINT
    def interrupted(signum, frame):
        nonlocal received
        received = signum
        raise KeyboardInterrupt
    handlers = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        env = dict(os.environ, CARD_CONDITION_EXPERIMENT_DIR=str(folder),
                   CARD_CONDITION_EXPERIMENT_REFERENCE=str(folder / 'reference.json'))
        child = subprocess.Popen(command, cwd=root, env=env, start_new_session=True)
        item['child_pid'] = child.pid
        item['stage'] = 'execute'
        save(folder / 'record.json', item)
        item['return_code'] = child.wait(timeout=timeout)
        if item['return_code'] != 0:
            if item['return_code'] < 0:
                received = -item['return_code']
            item.update(status='interrupted' if item['return_code'] < 0 else 'failed', error_kind='child_exit')
        else:
            item['stage'] = 'validate_result'
            complete(root, folder, item)
            item['status'] = 'completed'
            item['stage'] = 'finished'
    except subprocess.TimeoutExpired:
        received = signal.SIGTERM
        item.update(status='interrupted', error_kind='time_budget')
    except KeyboardInterrupt:
        item.update(status='interrupted', error_kind='signal', signal=received)
    except Exception as exc:
        item.update(status='failed', error_kind=type(exc).__name__)
    finally:
        if child is not None and child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
            except ProcessLookupError:
                child.wait()
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
        if child is not None:
            item['return_code'] = child.returncode
        item['finished_at'] = stamp()
        save(folder / 'record.json', item)
    print('실험 기록:', folder / 'record.json', '/ 상태:', item['status'])
    return 0 if item['status'] == 'completed' else 128 + received if item['status'] == 'interrupted' else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    try:
        return run(ROOT, read(args.plan), command)
    except BlockingIOError:
        print('다른 개발·실험·검토가 진행 중입니다. 새 실험을 실행하지 않았습니다.')
        return 1
    except (OSError, ValueError, KeyError):
        print('실험 계획·기준 결과·코드 경로를 확인하세요. 원문 오류는 출력하지 않습니다.')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
