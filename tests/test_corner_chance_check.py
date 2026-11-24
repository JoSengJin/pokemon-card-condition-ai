import ast
import contextlib
import importlib.util
import io
import json
import random
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('corner_chance_check', ROOT / 'tools/diagnostics/corner-chance-check-20261124/check.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)
ROWS = [dict(id=f'{g}/{z}', group=g, image='p' + g, target=t) for g, z, t in
        [('a', 1, 1), ('a', 2, 1), ('a', 3, 0), ('b', 1, 1), ('b', 2, 0), ('c', 1, 0), ('c', 2, 0), ('d', 1, 0)]]
OLD = [.10, .20, .99, .30, .05, .59, .10, .60]
NEW = [.10, .19, .99, .30, .95, .60, .10, .59]


def original(path, name):
    """The real definition from the tracked source, without importing its torch dependencies."""
    node = next(n for n in ast.parse((ROOT / path).read_text()).body if getattr(n, 'name', None) == name)
    scope = dict(defaultdict=defaultdict)
    exec(compile(ast.Module([node], []), path, 'exec'), scope)
    return scope[name]


class ChanceCheck(unittest.TestCase):
    def run_main(self, folder, rows=ROWS, new=NEW):
        """Synthetic control/candidate runs plus extra ledger records; returns exit code, stdout and stderr."""
        runs = [('2', 'ctl', 'completed', 'x'), ('3', 'cand', 'completed', 'x'), ('1', 'fail', 'failed', 'x'),
                ('4', 'stop', 'interrupted', 'x'), ('5', 'old', 'completed', 'other')]
        for start, name, status, cohort in runs:
            run = Path(folder, name)
            run.mkdir()
            (run / 'record.json').write_text(json.dumps(dict(started_at=start, status=status, hypothesis_id='h-' + name)))
            (run / 'reference.json').write_text(json.dumps(dict(cohort_sha256=cohort)))
        Path(folder, 'broken').mkdir()
        Path(folder, 'ctl', 'result.json').write_text(json.dumps(dict(rows=ROWS, scores=OLD)))
        Path(folder, 'cand', 'result.json').write_text(json.dumps(dict(rows=rows, scores=new)))
        before = {p: p.read_bytes() for p in Path(folder).rglob('*.json')}
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = check.main([f'{folder}/ctl/result.json', f'{folder}/cand/result.json', folder])
        self.assertEqual({p: p.read_bytes() for p in Path(folder).rglob('*') if p.is_file()}, before)  # read-only
        return code, out.getvalue(), err.getvalue()

    def test_card_rules(self):
        miss, alarm = check.card_flags(ROWS, OLD)
        self.assertEqual((miss, alarm), (dict(a=False, b=False), dict(c=False, d=True)))  # .20 is found, .60 alarms
        self.assertEqual(check.card_flags(ROWS, NEW), (dict(a=True, b=False), dict(c=True, d=False)))
        changed = [0. if r['group'] in 'ab' and not r['target'] else s for r, s in zip(ROWS, OLD)]
        self.assertEqual(check.card_flags(ROWS, changed), (miss, alarm))  # normal zones of defect cards never count
        card_miss, rng = original('tools/experiments/corner-mlp-head-20261121/worker.py', 'card_miss'), random.Random(1)
        for _ in range(200):
            scores = [rng.choice([0., .1, .2, .4, .6, 1.]) for _ in ROWS]
            miss, alarm = check.card_flags(ROWS, scores)
            low, high = card_miss(ROWS, scores, 0, fixed=check.LOW), card_miss(ROWS, scores, 0, fixed=check.HIGH)
            self.assertEqual((sum(miss.values()), len(miss), sum(alarm.values()), len(alarm)),
                             (low['miss'], low['positives'], high['false_alarm'], high['normals']))

    def test_statistics(self):
        for b, c, p in [(0, 0, 1.), (2, 0, .5), (0, 2, .5), (5, 1, .21875), (2, 2, 1.), (10, 2, 158 / 4096)]:
            before = {i: b <= i < b + c for i in range(b + c + 3)}
            after = {i: i < b for i in range(b + c + 3)}
            result = check.mcnemar(before, after)
            self.assertEqual((result['worse_b'], result['better_c']), (b, c))
            self.assertAlmostEqual(result['exact_two_sided_p'], p)
        for k, n, lo, hi in [(0, 10, 0., .2775), (10, 10, .7225, 1.), (5, 10, .2366, .7634), (1, 100, .0018, .0545)]:
            got = check.rate({i: i < k for i in range(n)})
            self.assertEqual((got['count'], got['cards']), (k, n))
            self.assertAlmostEqual(got['wilson95'][0], lo, places=4)
            self.assertAlmostEqual(got['wilson95'][1], hi, places=4)
        self.assertIsNone(check.rate({})['wilson95'])

    def test_report_same_results_and_ledger(self):
        with tempfile.TemporaryDirectory() as folder:
            code, out, _ = self.run_main(folder, new=OLD)
            report = json.loads(out)
            self.assertEqual(code, 0)
            for name in ('miss', 'false_alarm'):
                self.assertEqual(report[name]['paired'], dict(worse_b=0, better_c=0, exact_two_sided_p=1.))
                self.assertEqual(report[name]['control'], report[name]['candidate'])
            self.assertEqual(report['same_photo_auc']['bootstrap95'], [0., 0.])
            self.assertIn('기술 통계, 채택 기준 아님', out)
            self.assertIn('cohort_sha256이 다른 옛 실행(946구역 등)은 세지 않아 실제 시도 수의 하한', out)
        with tempfile.TemporaryDirectory() as folder:
            report = json.loads(self.run_main(folder)[1])
            self.assertEqual(report['miss']['paired'], dict(worse_b=1, better_c=0, exact_two_sided_p=1.))
            self.assertEqual(report['false_alarm']['paired'], dict(worse_b=1, better_c=1, exact_two_sided_p=1.))
        self.assertEqual(report['attempts'], dict(cohort_sha256='x', total=4, by_status=dict(completed=2, failed=1, interrupted=1),
                                   candidate_attempt_number=3, hypothesis_ids=['h-fail', 'h-ctl', 'h-cand', 'h-stop'], unreadable=['broken']))

    def test_bad_inputs_rejected(self):
        swapped, relabelled = [ROWS[1], ROWS[0]] + ROWS[2:], [dict(ROWS[0], target=0)] + ROWS[1:]
        unknown = [dict(ROWS[0], target=None)] + ROWS[1:]
        for rows, new in [(swapped, NEW), (relabelled, NEW), (ROWS[:-1], NEW[:-1]), (unknown, NEW), (ROWS, NEW[:-1]),
                          (ROWS, [1.5] + NEW[1:]), (ROWS, [float('nan')] + NEW[1:])]:
            with tempfile.TemporaryDirectory() as folder:
                code, out, err = self.run_main(folder, rows, new)
                self.assertEqual((code, out), (2, ''))
                self.assertIn('ValueError', err)
        with self.assertRaises(ValueError):
            check.same_photo([dict(r, image='shared') for r in ROWS], OLD, NEW)

    def test_bootstrap(self):
        rng = random.Random(7)
        rows = [dict(id=f'{g}/{z}', group=f'g{g}', image=f'p{g}', target=int(z < g % 3)) for g in range(12) for z in range(4)]
        old, new = [[rng.random() for _ in rows] for _ in range(2)]
        got = check.same_photo(rows, old, new)
        self.assertEqual(got, check.same_photo(rows, old, new))
        auc = original('tools/experiments/edge-back-bagging-20261031/worker.py', 'auc')
        self.assertAlmostEqual(got['control'], auc(rows, old, True))
        self.assertAlmostEqual(got['candidate'], auc(rows, new, True))
        # reference: resample whole groups with the same seed and score them with the original AUC definition
        keys, draw, diffs = sorted({r['group'] for r in rows}), random.Random(20261124), []
        for _ in range(2000):
            sub, a, b = [], [], []
            for n, g in enumerate([draw.choice(keys) for _ in keys]):
                for i, r in enumerate(rows):
                    if r['group'] == g:
                        sub.append(dict(r, image=f'{r["image"]}#{n}'))
                        a.append(old[i])
                        b.append(new[i])
            diffs.append(auc(sub, b, True) - auc(sub, a, True))
        diffs.sort()
        self.assertEqual((got['draws'], got['seed']), (2000, 20261124))
        for bound, q in zip(got['bootstrap95'], (.025, .975)):
            self.assertAlmostEqual(bound, diffs[int(q * 1999)])
        self.assertIsNone(check.same_photo([dict(r, target=0) for r in rows], old, new)['bootstrap95'])


if __name__ == '__main__':
    print('check.py:', check.__file__)
    unittest.main()
