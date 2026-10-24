import json
from pathlib import Path
import tempfile
import unittest
from test_pipeline import fixture
from card_condition.label_audit import label_audit

class LabelAuditTest(unittest.TestCase):
    def test_read_only_visibility_and_split_audit(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();reference,rows=fixture(root)
            for r in rows:
                for side in ('front','back'):r[side]=str(root/r[side])
                r['images']=[{'path':r[s]} for s in ('front','back')]
                r['side_annotations']={s:{'image':r[s],'box':[0,0,1,1],'labels':dict(r['labels'])} for s in ('front','back')}
                if r['split']=='test':r['front']='missing';r['labels']={}
            reference.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            rows[0]['split']='val'
            a=rows[0]['side_annotations']['front']['labels']
            a.update(gradable=0,centering_defect=None,corner_defect=0,edge_defect=1,surface_defect=None)
            inventory=root/'inventory.jsonl';inventory.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            before=inventory.read_bytes();report=label_audit(inventory,reference,root/'audit.json')
            self.assertEqual(before,inventory.read_bytes())
            flags=[f for f in report['findings'] if f['id']=='0/front' and f['kind']=='ungradable_negative_review']
            self.assertEqual(['corner_defect'],flags[0]['labels'])
            self.assertTrue(any(f['kind']=='ungradable_reason_missing' for f in report['findings']))
            self.assertTrue(any(f['kind']=='split_changed' for f in report['findings']))
            self.assertFalse(report['labels_modified'])
            with self.assertRaisesRegex(ValueError,'exists'):label_audit(inventory,reference,root/'audit.json')
