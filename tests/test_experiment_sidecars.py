import json
import os
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import test_experiment_record as fixture
from card_condition import experiment_record as recording
from card_condition import experiment_sidecars as sidecars

DATA = Path(os.environ.get('CARD_CONDITION_DATA_ROOT', Path(__file__).resolve().parents[1]))
RUN = DATA / 'artifacts/experiments/20261121T050740-8588eeb0/observations.json'
MEASURES = DATA / 'artifacts/corner-size-threshold-20261123/measures.json'
FACT = dict(background='unmeasured', px_per_mm_layer='unmeasured', rater_kind='unknown', criteria_sha256='버전 미상', input_hold=False)


def zone(**counts):
    base = {k: 0 for k in (*sidecars.STATES, *sidecars.MARKS)}
    return {**base, sidecars.BOX: {k: 0 for k in sidecars.STATES}, **counts}


class SidecarTest(unittest.TestCase):
    def setUp(self):
        self.case = fixture.ExperimentRecordTest('test_all_required_and_primary_pass')
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        # The shared fixture ids have no cell segment; give the frozen reference cell/zone ids.
        self.path = self.case.old / 'result.json'
        result = recording.read(self.path)
        result['rows'] = [dict(r, id=f"card{r['id']}/back/corner/upper_left", area='upper_left') for r in result['rows']]
        recording.save(self.path, result)
        self.ids = [r['id'] for r in result['rows']]
        self.exclusions = {'corner': {'upper_left': zone(**{'정상': 2, '결함': 1, '미확인': 4})}, 'kept_rule': sidecars.BOX_OUT}
        self.facts = dict({i: dict(FACT) for i in self.ids}, _measure_sha256='x')

    def declare(self, **extra):
        block = dict(extra)
        for name, body in (('exclusions', self.exclusions), ('row_facts', self.facts)):
            path = self.case.old / f'{name}.json'
            recording.save(path, body)
            block[name] = dict(path=str(path.relative_to(self.case.root)), sha256=recording.sha(path))
        self.case.plan['sidecars'] = block

    def rejected(self):
        with patch('subprocess.Popen') as child, self.assertRaises(ValueError):
            self.case.run_case()
        child.assert_not_called()
        self.assertFalse((self.case.root / 'artifacts/experiments').exists())

    def test_without_sidecars_no_new_keys(self):
        code, folder, _ = self.case.run_case()
        self.assertEqual(code, 0)
        self.assertEqual(set(recording.read(folder / 'reference.json')),
                         {'rows', 'before_scores', 'cohort_sha256', 'point_ids', 'point_scores', 'required_cohorts', 'source', 'source_sha256'})
        self.assertEqual(set(recording.read(folder / 'result.json')),
                         {'rows', 'before_scores', 'scores', 'comparison', 'independent', 'production_adopted', 'point_ids',
                          'point_scores', 'point_comparison', 'acceptance_caps', 'acceptance_passed', 'hypothesis_id'})

    def test_strata_table_recorded_and_verdict_unchanged(self):
        _, folder, _ = self.case.run_case()
        plain = recording.read(folder / 'result.json')
        self.declare()
        code, folder, record = self.case.run_case()
        self.assertEqual((code, record['status']), (0, 'completed'))
        result = recording.read(folder / 'result.json')
        table = result.pop('strata_table')
        self.assertEqual(result, plain)
        self.assertEqual(sum(r['n'] for r in table['after']), 3)
        self.assertEqual({r['band'] for r in table['before']}, {'>=0.6'})

    def test_missing_or_extra_row_fact_rejected_before_child(self):
        for change in (lambda: self.facts.pop(self.ids[0]), lambda: self.facts.update({'other': dict(FACT)})):
            with self.subTest():
                saved = dict(self.facts)
                change(); self.declare(); self.rejected()
                self.facts = saved

    def test_wrong_sha_rejected(self):
        self.declare()
        sha = self.case.plan['sidecars']['row_facts']['sha256']
        self.case.plan['sidecars']['row_facts']['sha256'] = ('0' if sha[0] != '0' else '1') + sha[1:]
        self.rejected()

    def test_kept_counts_must_match_rows(self):
        self.exclusions['corner']['upper_left']['정상'] = 3
        self.declare(); self.rejected()

    def test_box_in_rule_adds_unconfirmed_box_counts(self):
        z = self.exclusions['corner']['upper_left']
        z['정상'], z[sidecars.BOX]['정상'] = 1, 1
        self.declare(); self.rejected()
        self.exclusions['kept_rule'] = sidecars.BOX_IN
        self.declare()
        self.assertEqual(self.case.run_case()[0], 0)

    def test_branch_dependent_needs_observed_branch(self):
        evidence = self.case.old / 'branch.md'
        evidence.write_text('A')
        block = dict(rules_sha256='0' * 64, branch_dependent=True,
                     branch_evidence=dict(path=str(evidence.relative_to(self.case.root)), sha256=recording.sha(evidence)))
        self.declare(preregistration=block); self.rejected()
        self.declare(preregistration=dict(block, branch_observed='A'))
        self.assertEqual(self.case.run_case()[0], 0)

    @unittest.skipUnless(RUN.is_file() and MEASURES.is_file(), '미검증: 실자료 없음')
    def test_real_scores_reproduce_published_strata(self):
        run, measures = json.loads(RUN.read_text()), json.loads(MEASURES.read_text())
        facts = {}
        for r in run['rows']:
            m = measures[f"{r['id']}|{r['image_sha256']}|{','.join(f'{v:.6f}' for v in r['box'])}"]
            facts[r['id']] = dict(FACT, background=m['status'])
        table = sidecars.tally(dict(run, before_scores=run['scores']), dict(bands=sidecars.BANDS, row_facts=facts))['strata_table']['after']
        n = Counter()
        for row in table:
            n[row['background'], row['band'], row['target']] += row['n']
        def total(bands, target, background=None):
            return sum(v for (g, b, t), v in n.items() if b in bands and t == target and background in (None, g))
        low, high, every = ('<0.2', '0.2-0.4', '0.4-0.5'), ('0.5-0.6', '>=0.6'), ('<0.2', '0.2-0.4', '0.4-0.5', '0.5-0.6', '>=0.6')
        for background, miss, alarm in (('bg_bright', (52, 185), (39, 336)), ('ok', (28, 187), (40, 164))):
            self.assertEqual((total(low, 1, background), total(every, 1, background)), miss)
            self.assertEqual((total(high, 0, background), total(every, 0, background)), alarm)
        self.assertEqual((total(('<0.2', '0.2-0.4'), 1), total(('0.4-0.5',), 1)), (63, 26))
        self.assertEqual((total(('0.5-0.6',), 0), total(('>=0.6',), 0)), (35, 54))
        for target, expected in ((0, [249, 238, 54]), (1, [15, 103, 283])):
            self.assertEqual([total(('<0.2',), target), total(('0.2-0.4', '0.4-0.5', '0.5-0.6'), target), total(('>=0.6',), target)], expected)


if __name__ == '__main__':
    unittest.main()
