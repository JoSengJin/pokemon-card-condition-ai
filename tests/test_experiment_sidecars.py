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


class SidecarBase(unittest.TestCase):
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


class SidecarTest(SidecarBase):
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
        for missing, extra in (([self.ids[0]], []), ([], ['other'])):
            with self.subTest(missing=missing, extra=extra):
                saved = dict(self.facts)
                for ident in missing:
                    del self.facts[ident]
                self.facts.update({ident: dict(FACT) for ident in extra})
                self.declare()
                self.rejected()
                self.facts = saved


if __name__ == '__main__':
    unittest.main()
