import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from freeze_dev_manifest import audit, combine


def face(points, **extra):
    return dict(box=[0, 0, 1, 1], labels=dict(corner_defect=1, edge_defect=None, surface_defect=0), defect_points=points,
                box_reviewed=True, **extra)


class FreezeDevManifestTest(unittest.TestCase):
    def write(self, root, name, rows):
        path = Path(root) / name
        path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
        return path, hashlib.sha256(path.read_bytes()).hexdigest()

    def test_combine_refuses_changed_base_train_batch_and_split_crossing(self):
        with tempfile.TemporaryDirectory() as root:
            base, sha = self.write(root, 'base.jsonl', [dict(id='a', group='g1', split='train')])
            ok, _ = self.write(root, 'ok.jsonl', [dict(id='b', group='g2', split='val')])
            rows, info = combine(base, sha, [ok])
            self.assertEqual([r['id'] for r in rows], ['a', 'b'])
            self.assertEqual(info['sources'][0]['rows'], 1)
            with self.assertRaises(ValueError):
                combine(base, '0' * 64, [ok])
            train, _ = self.write(root, 'train.jsonl', [dict(id='c', group='g3', split='train')])
            with self.assertRaises(ValueError):
                combine(base, sha, [train])
            cross, _ = self.write(root, 'cross.jsonl', [dict(id='d', group='g1', split='val')])
            with self.assertRaises(ValueError):
                combine(base, sha, [cross])

    def test_audit_flags_wrong_area_negative_face_and_normal_conflict_only(self):
        rows = [dict(id='x', split='val', side_annotations=dict(front=face(
            [dict(x=0.1, y=0.1, label='corner_defect'), dict(x=0.5, y=0.5, label='corner_defect'),
             dict(x=0.5, y=0.1, label='surface_defect'), dict(x=0.9, y=0.9, label='corner_defect')],
            region_labels=dict(lower_right=dict(corner_defect=0)))))]
        errors, warnings = audit(rows)
        self.assertEqual(sorted((e['point'], e['reason']) for e in errors),
                         [(2, 'kind_not_allowed_in_area'), (3, 'face_label_not_positive'),
                          (4, 'conflicts_same_kind_normal_region')])
        self.assertEqual(warnings, [])


if __name__ == '__main__':
    unittest.main()
