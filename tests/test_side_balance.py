import tempfile
import unittest
from pathlib import Path

from card_condition.region_experiment import experiment, side_class_training_weights, training_class_ratios
from card_condition.regions import REGION_LABELS


def row(group, side, value, split='train'):
    return dict(group=group, side=side, split=split,
                labels={key: value if key == 'edge_defect' else None for key in REGION_LABELS})


class SideBalanceTests(unittest.TestCase):
    def setUp(self):
        self.rows = [row('a', 'front', 0) for _ in range(3)] + [row('b','front',0),
                     row('c','front',1), row('d','back',0), row('e','back',1), row('held-out','front',0,'val')]

    def test_four_cells_have_equal_mass_and_duplicate_patches_share_group_mass(self):
        weights = side_class_training_weights(self.rows, ['edge_defect'])
        for side in ('front','back'):
            for value in (0,1):
                mass = sum(w[1] for r,w in zip(self.rows,weights)
                           if r['split']=='train' and r['side']==side and r['labels']['edge_defect']==value)
                self.assertAlmostEqual(mass, .25)
        self.assertAlmostEqual(sum(w[1] for w in weights[:3]), weights[3][1])
        self.assertEqual(weights[-1], [0.,0.,0.])
        self.assertAlmostEqual(training_class_ratios(self.rows,weights,['edge_defect'])[1],1.)

    def test_validation_cannot_fill_a_missing_train_cell(self):
        rows = [r for r in self.rows if not (r['side']=='back' and r['labels']['edge_defect']==1)]
        rows.append(row('leak','back',1,'val'))
        with self.assertRaises(ValueError):
            side_class_training_weights(rows,['edge_defect'])

    def test_unknown_labels_do_not_receive_weight(self):
        rows = self.rows + [row('unknown','back',None)]
        self.assertEqual(side_class_training_weights(rows,['edge_defect'])[-1],[0.,0.,0.])

    def test_opt_in_requires_balanced_point_experiment(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,'Side balance requires'):
                experiment('unused.jsonl',Path(directory)/'out',point_grid=True,side_balance=True)


if __name__ == '__main__':
    unittest.main()
