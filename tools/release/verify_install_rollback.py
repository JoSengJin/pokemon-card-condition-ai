"""Build two fixture wheels, install them outside the repository and roll back A -> B -> A.

Synthetic random-init checkpoints and a generated photo only: no real photos, labels,
training, downloads or external calls. Dependencies (torch, Pillow) are read from the
caller's venv via a .pth file (the site folder holding torch) that exists only while the installed CLI runs, never while
pip modifies the isolated environment.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
import subprocess
import sys

import torch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tests'))
from test_release import fixture_release  # noqa: E402  same synthetic fixture as the unit tests


def run(command, cwd, check=True):
    done = subprocess.run([str(part) for part in command], cwd=cwd, capture_output=True, text=True)
    if check and done.returncode:
        raise SystemExit(f'{command[0]} failed: {done.stderr[-2000:]}')
    return done


def build_wheel(work, local):
    """Copy the package source, stamp a local version and build a no-deps wheel offline."""
    source = work / f'src-{local}'
    shutil.rmtree(source, ignore_errors=True)
    shutil.copytree(REPO / 'card_condition', source / 'card_condition',
                    ignore=shutil.ignore_patterns('__pycache__'))
    base = (REPO / 'pyproject.toml').read_text()
    marker = 'version = "0.5.0"'
    if base.count(marker) != 1:
        raise SystemExit('pyproject version anchor missing')
    (source / 'pyproject.toml').write_text(base.replace(marker, f'version = "0.5.0+{local}"'))
    run([sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation', '--no-index',
         '-w', work / 'wheels', source], work)
    return next((work / 'wheels').glob(f'pokemon_card_condition-0.5.0+{local}-*.whl'))


def installed_run(env, release, request, step):
    """pip-install nothing here; only add the deps path, run the CLI outside the repo, remove it."""
    site = Path(run([env / 'bin/python', '-c', 'import sysconfig;print(sysconfig.get_paths()["purelib"])'],
                    env).stdout.strip())
    deps = site / 'zz_fixture_deps.pth'
    deps.write_text(str(Path(torch.__file__).resolve().parents[1]) + '\n')
    try:
        probe = run([env / 'bin/python', '-I', '-c',
            'import card_condition,importlib.metadata as m,importlib.resources as r,json;'
            'print(json.dumps(dict(file=card_condition.__file__,version=m.version("pokemon-card-condition"),'
            'resources=all((r.files("card_condition")/n).is_file() for n in ("review.html","review_chat.html")))))'],
            env.parent)
        done = run([env / 'bin/card-condition', 'listing-predict', request, '--release', release,
                    '--device', 'cpu'], env.parent, check=False)
    finally:
        deps.unlink()
    info = json.loads(probe.stdout)
    record = dict(step=step, release_manifest=str(release.relative_to(env.parent)), exit_code=done.returncode,
                  installed_version=info['version'], resources_present=info['resources'],
                  module_outside_repo=not Path(info['file']).resolve().is_relative_to(REPO))
    if done.returncode == 0:
        report = json.loads(done.stdout)
        record.update(release=report['release'], model_sha256=report['model_sha256'],
                      inferred_regions=report['inferred_regions'],
                      predictions_sha256=hashlib.sha256(json.dumps(report['predictions'], sort_keys=True)
                                                        .encode()).hexdigest(),
                      blockers=report['listing_readiness']['records'][0]['whole_listing_blockers'])
    else:
        record.update(stdout_empty=done.stdout == '', error=json.loads(done.stderr)['error'])
    return record


def render_html(results, path):
    rows = ''.join(
        f"<tr><td>{html.escape(r['step'])}</td><td>{r['installed_version']}</td>"
        f"<td>{html.escape(r['release_manifest'])}</td><td>{r['exit_code']}</td>"
        f"<td><code>{(r.get('model_sha256') or '-')[:16]}</code></td>"
        f"<td><code>{(r.get('predictions_sha256') or '-')[:16]}</code></td>"
        f"<td>{html.escape(r.get('error', 'ok'))}</td></tr>" for r in results['steps'])
    checks = ''.join(f"<li>{'PASS' if ok else 'FAIL'} — {html.escape(name)}</li>"
                     for name, ok in results['checks'].items())
    path.write_text(f"""<!doctype html><meta charset="utf-8"><title>F1 Release Rollback</title>
<style>body{{font:15px system-ui;margin:24px;max-width:1100px;color:#1d1d1f;background:#fff}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:6px;text-align:left}}
.note{{background:#fff4d6;padding:10px;border-radius:6px}}code{{font-size:13px}}</style>
<h1>F1 릴리스 고정·설치·복구 (합성 fixture)</h1>
<p><b>검증 코드</b>: {html.escape(results['source'])}<br><b>전체 진척</b>: 30/100 (usable-card-analysis-v1.0, 변화 0%p). F1은 pending 유지.</p>
<p class="note">합성 무작위 checkpoint와 생성 이미지로 실행 경로만 검증했다. 모델 학습·실사진 추론·성능 비교 없음. 정확도/FN/FP 변화 미평가.</p>
<h2>설치본 실행 순서 (저장소 밖 격리 venv)</h2>
<table><tr><th>단계</th><th>설치 패키지</th><th>manifest</th><th>exit</th><th>model_sha256</th><th>predictions sha</th><th>결과</th></tr>{rows}</table>
<h2>판정</h2><ul>{checks}</ul>
<h2>남은 F1 조건</h2><ul><li>C·D 품질 통과 후보 없음 — 고정할 운영 릴리스 후보가 없다.</li>
<li>승인된 소비 경로(PokeCollector) 통합 검증과 배포 승인 없음.</li>
<li>centering_not_evaluated · whole_listing_observability_not_validated 유지.</li></ul>""")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', required=True, help='Scratch folder outside the repository')
    parser.add_argument('--output', default=str(REPO / 'artifacts/release-rollback-20261025'))
    args = parser.parse_args()
    work, output = Path(args.work).resolve(), Path(args.output)
    if work.is_relative_to(REPO):
        raise SystemExit('work folder must be outside the repository')
    shutil.rmtree(work, ignore_errors=True)
    wheels = {key: build_wheel(work, f'fixture.{key}') for key in ('a', 'b')}
    releases = {}
    for seed, key in enumerate(('a', 'b')):
        folder = work / f'release-{key}'
        folder.mkdir()
        releases[key] = fixture_release(folder, seed, release_id=f'fixture-{key}',
                                        package_version=f'0.5.0+fixture.{key}')[0]
    env = work / 'env'
    run([sys.executable, '-m', 'venv', env], work)
    pip = [env / 'bin/python', '-m', 'pip', 'install', '-q', '--no-deps', '--no-index', '--force-reinstall']
    request = releases['a'].parent / 'request.json'
    steps = []
    for step, key in (('1 install A', 'a'), ('2 upgrade B', 'b'), ('3 rollback A', 'a')):
        run(pip + [wheels[key]], work)
        steps.append(installed_run(env, releases[key], request, step))
        if step.startswith('2'):
            steps.append(installed_run(env, releases['a'], request, '2x B install + A manifest'))
    tampered = releases['a'].parent / json.loads(releases['a'].read_text())['checkpoints']['region']['file']
    original = tampered.read_bytes()
    tampered.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
    steps.append(installed_run(env, releases['a'], request, '3x A install + tampered checkpoint'))
    tampered.write_bytes(original)
    one, two, cross, three, broken = steps
    checks = {
        'all installed runs import card_condition outside the repo with resources': all(
            s['module_outside_repo'] and s['resources_present'] for s in steps),
        'A run identifies release fixture-a': one.get('release', {}).get('release_id') == 'fixture-a',
        'B differs from A in package, checkpoint SHA and predictions': two['exit_code'] == 0 and (
            two['installed_version'], two['model_sha256'], two['predictions_sha256']) != (
            one['installed_version'], one['model_sha256'], one['predictions_sha256']),
        'A manifest on B install is rejected with empty stdout': cross['exit_code'] == 1 and cross['stdout_empty'],
        'rollback restores A package, checkpoint SHA, release and predictions': three['exit_code'] == 0 and all(
            three[k] == one[k] for k in ('installed_version', 'model_sha256', 'release', 'predictions_sha256')),
        'tampered checkpoint is rejected before inference': broken['exit_code'] == 1 and broken['stdout_empty']
            and 'SHA256 mismatch' in broken['error'],
        'whole-listing blockers kept': all('centering_not_evaluated' in s.get('blockers', ['centering_not_evaluated'])
                                           for s in steps),
    }
    source = run(['git', 'rev-parse', 'HEAD'], REPO).stdout.strip()
    dirty = bool(run(['git', 'status', '--porcelain', '--', 'card_condition', 'pyproject.toml'], REPO).stdout)
    results = dict(source=source + (' + uncommitted source changes' if dirty else ''),
                   wheels={k: dict(file=w.name, sha256=hashlib.sha256(w.read_bytes()).hexdigest())
                           for k, w in wheels.items()},
                   steps=steps, checks=checks, passed=all(checks.values()),
                   synthetic_only=True, model_quality_evaluated=False)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
    render_html(results, output / 'index.html')
    print(json.dumps(dict(passed=results['passed'], checks=checks), indent=2))
    raise SystemExit(0 if results['passed'] else 1)


if __name__ == '__main__':
    main()
