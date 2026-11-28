import json
import unittest
from collections import Counter

from card_condition import experiment_record as recording
from card_condition import experiment_sidecars as sidecars
from test_experiment_sidecars import FACT, MEASURES, RUN, SidecarBase

class SidecarTestMore(SidecarBase):
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
