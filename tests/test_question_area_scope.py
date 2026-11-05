from pathlib import Path
import tempfile
import unittest
from card_condition.physical_uncertainty import physical_uncertainty
from card_condition.evaluation_suite_metrics import question_cells

# Same fixed canonical scope as regions.REGION_TARGET_AREAS; checked against source in integration.
AREAS = dict(corner_defect=('upper_left','upper_right','lower_left','lower_right'),
             edge_defect=('upper_left','upper_center','upper_right','middle_left','middle_right','lower_left','lower_center','lower_right'),
             surface_defect=('upper_left','upper_center','upper_right','middle_left','center','middle_right','lower_left','lower_center','lower_right'))
Q = 'corner_defect'


def uncertainty_cell(rows, *, scoped=True):
    return next(c for c in physical_uncertainty(rows, [Q], question_areas=AREAS if scoped else None)['cells']
                if c['question'] == Q and c['side'] == 'front')


class QuestionAreaScopeTest(unittest.TestCase):
    def test_nonapplicable_unknown_is_disclosed_without_losing_normal_cards(self):
        rows = [dict(group=f'{truth}-{i}', side='front', area=area, labels={Q: truth if area=='upper_left' else None},
                     probabilities={Q: (.9 if truth else .1) if area=='upper_left' else None})
                for truth in (0,1) for i in range(30) for area in ('upper_left','center')]
        cell = uncertainty_cell(rows)
        self.assertEqual(30, cell['false_alarm']['physical_cards'])
        self.assertEqual(60, cell['out_of_scope_unknown_units'])
        self.assertEqual(0, cell['unknown_truth_units'])
        self.assertTrue(cell['numeric_conditions_met'])
        self.assertEqual(0, uncertainty_cell(rows, scoped=False)['false_alarm']['physical_cards'])

    def test_applicable_unknown_still_prevents_normal_card_inference(self):
        rows = [dict(group='one', side='front', area=area, labels={Q: truth}, probabilities={Q: score})
                for area, truth, score in [('upper_left',0,.1),('upper_right',None,None)]]
        cell = uncertainty_cell(rows)
        self.assertEqual(0, cell['false_alarm']['physical_cards'])
        self.assertEqual(1, cell['unknown_truth_units'])
        self.assertEqual(0, cell['out_of_scope_unknown_units'])

    def test_known_truth_outside_scope_is_never_silently_discarded(self):
        cell = uncertainty_cell([dict(group='one',side='front',area='center',labels={Q:1},probabilities={Q:None})])
        self.assertEqual(1,cell['miss']['physical_cards'])
        self.assertEqual(1,cell['miss']['unavailable_cards'])
        self.assertIsNone(cell['miss']['upper_95'])
        self.assertEqual(0,cell['out_of_scope_unknown_units'])

    def test_missing_or_noncanonical_area_keeps_unknown(self):
        for area in (None,'mystery'):
            with self.subTest(area=area):
                rows=[dict(group='one',side='front',area='upper_left',labels={Q:0},probabilities={Q:.1}),
                      dict(group='one',side='front',area=area,labels={Q:None},probabilities={Q:None})]
                self.assertEqual(1,uncertainty_cell(rows)['unknown_truth_units'])
                self.assertEqual(0,uncertainty_cell(rows)['false_alarm']['physical_cards'])

    def test_unsupported_model_keeps_source_quantity_and_blocks_score_gates(self):
        rows=[dict(card_id=f'{truth}-{i}',group=f'{truth}-{i}',side='front',area='upper_left',
                   labels={Q:truth},probabilities={Q:.9 if truth else .1}) for truth in (0,1) for i in range(30)]
        metadata={r['card_id']:{} for r in rows}
        cell=question_cells(rows,[],[Q],metadata,question_areas=AREAS)[0]
        self.assertEqual((30,30),(cell['positive_units'],cell['negative_units']))
        self.assertEqual((30,30),(cell['unavailable_positive_scores'],cell['unavailable_negative_scores']))
        self.assertTrue(cell['d1_class_quantity_met'])
        self.assertFalse(cell['c_numeric_condition_met'])
        self.assertIsNone(cell['false_negative_rate'])
        self.assertEqual(60,cell['subgroups'][0]['physical_cards'])

    def test_saved_suite_preserves_scope_and_partial_model_source_denominators(self):
        from card_condition.regions import REGION_TARGET_AREAS
        from card_condition.evaluation_suite import assess_suite
        from test_evaluation_suite import saved_suite
        self.assertEqual(REGION_TARGET_AREAS,AREAS)
        for supported in (None,[Q]):
            with self.subTest(supported=supported), tempfile.TemporaryDirectory() as directory:
                root=Path(directory).resolve()
                args,reports=saved_suite(root,surface_center=True,region_supported=supported)
                result=assess_suite(*args,reports,root/'assessment.json')
                self.assertTrue(result['numeric_gates']['d1_class_quantity'])
                self.assertEqual(supported is None,result['numeric_gates']['c_raw_all_questions'])
                self.assertEqual(supported is None,result['numeric_gates']['d3_card_event_bounds'])
                for cell in result['cells']:
                    if cell['question']==Q:
                        self.assertEqual(60,cell['out_of_scope_unknown_units'])
                        self.assertEqual(0,cell['unknown_truth_units'])
                        self.assertEqual(30,cell['physical_uncertainty']['false_alarm']['physical_cards'])
                    if supported and cell['question']=='edge_defect':
                        self.assertEqual(30,cell['positive_units'])
                        self.assertEqual(30,cell['unavailable_positive_scores'])
                        self.assertIsNone(cell['false_negative_rate'])
                self.assertFalse(result['production_ready'])
                self.assertFalse(result['d3_verified'])
