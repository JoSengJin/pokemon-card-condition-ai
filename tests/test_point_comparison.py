import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from card_condition.comparison import compare_regions
from card_condition.point_dataset import point_rows
from card_condition.regions import REGION_LABELS
from test_pipeline import fixture


class PointComparisonTest(unittest.TestCase):
    def test_training_only_change_metrics_and_validation_identity_guards(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve(); manifest, rows=fixture(root)
            for i in range(4):
                rows[i]['labels']['gradable']=None
                a=dict(image=str(root/rows[i]['front']),box=[0,0,1,1],labels=dict(rows[i]['labels']))
                if i%2:
                    a['defect_points']=[dict(label='surface_defect',x=.5,y=.5)]
                else:
                    a['region_labels']={'center':dict(corner_defect=None,edge_defect=None,surface_defect=0)}
                rows[i]['side_annotations']={'front':a}
            for r in rows[4:]:r['front']='unread-test.png'
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            patches,_=point_rows(manifest,grid=True)
            predictions=[{**r,'probabilities':{k:.8 if k=='surface_defect' else None for k in REGION_LABELS}}
                         for r in patches if r['split']=='val']
            report=dict(evaluation_kind='point_validation',manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                        supported=['surface_defect'],predictions=predictions,
                        metrics={'surface_defect':dict(tp=1,tn=0,fp=1,fn=0)},architecture='mobilenet_v3_small_point_grid_v1',
                        epochs=20,selected_epoch=9,elapsed_seconds=1)
            one=root/'one.json';one.write_text(json.dumps(report))
            newer=root/'newer.jsonl';rows[0]['notes']='train-only change'
            newer.write_text('\n'.join(json.dumps(r) for r in rows))
            report['manifest_sha256']=hashlib.sha256(newer.read_bytes()).hexdigest()
            two=root/'two.json';two.write_text(json.dumps(report))
            result=compare_regions(newer,[one,two],root/'comparison.json',[manifest],point_grid=True)
            self.assertEqual('point_validation_comparison',result['evaluation_kind'])
            self.assertEqual((2,2),(result['regions'],result['groups']))
            self.assertEqual(1,result['models'][0]['metrics_at_05']['surface_defect']['fp'])
            self.assertEqual(1,len(result['models'][0]['errors']))
            rates=result['models'][1]['rate_change_from_reference_at_05']['surface_defect']
            self.assertEqual({'false_negative_rate':0.,'false_positive_rate':0.,'accuracy':0.},rates['change_percentage_points'])
            self.assertEqual((1,1),tuple(rates['candidate'][k] for k in ('positive','negative')))
            self.assertFalse(rates['errors_jointly_improved'])
            self.assertEqual(.5,result['models'][0]['score_diagnostics']['surface_defect']['auroc'])
            trial=result['models'][0]['score_diagnostics']['surface_defect']['abstention_trials'][2]
            self.assertEqual(2,len(trial['by_group']))
            self.assertEqual(1,sum(g['fp'] for g in trial['by_group'].values()))
            self.assertEqual(0,trial['zero_accepted_known_groups'])
            self.assertEqual(224,result['models'][0]['image_size'])
            listing = result['models'][0]['listing_readiness']
            self.assertEqual(2, listing['listings'])
            self.assertEqual(0, listing['local_complete_candidates'])
            self.assertTrue(all(r['whole_listing_blockers'] for r in listing['records']))
            with self.assertRaisesRegex(ValueError,'exists'):
                compare_regions(newer,[one,two],root/'comparison.json',[manifest],point_grid=True)
            report['metrics']['surface_defect']['fp']=0;two.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError,'metrics'):
                compare_regions(newer,[one,two],root/'wrong.json',[manifest],point_grid=True)
            self.assertFalse((root/'wrong.json').exists())
            rows[2]['side_annotations']['front']['box']=[.1,0,1,1]
            newer.write_text('\n'.join(json.dumps(r) for r in rows))
            with self.assertRaisesRegex(ValueError,'validation regions differ'):
                compare_regions(newer,[one,two],root/'leak.json',[manifest],point_grid=True)
            self.assertFalse((root/'leak.json').exists())
