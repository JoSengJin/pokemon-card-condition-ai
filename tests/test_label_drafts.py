import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from card_condition.review import ReviewStore
from card_condition.point_dataset import point_rows
from test_pipeline import fixture


class LabelDraftTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.path,rows=fixture(self.root)
        for row in rows:
            row['images']=[dict(path=str(self.root/row[s]),size=[90,130]) for s in ('front','back')]
            for side in ('front','back'):row[side]=str(self.root/row[side])
            row['reviewed_by']='original-human';row['pair_verified']=True
        row=rows[0]
        row['side_annotations']={'front':dict(image=row['front'],box=[0,0,1,1],box_reviewed=True,
            labels=dict(row['labels']),region_labels={},defect_points=[])}
        self.path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        self.draft=dict(id='normal-edge',card=row['id'],side='front',image_sha256=hashlib.sha256(Path(row['front']).read_bytes()).hexdigest(),box=[0,0,1,1],area='upper_center',label='edge_defect',value=0,reason='AI normal candidate',author='Codex')
        self.drafts=self.path.with_suffix('.drafts.json');self.drafts.write_text(json.dumps([self.draft]))
        self.store=ReviewStore(self.path)

    def payload(self,decision='approve'):
        return dict(revision=self.store.revision,ids=[self.draft['id']],decision=decision,reviewed_by='confirming-human')

    def test_unapproved_drafts_are_not_training_truth(self):
        raw=self.path.read_bytes();snapshot=self.store.snapshot()
        self.assertTrue(snapshot['drafts'][0]['available'])
        patches,_=point_rows(self.path,grid=True,splits={'train'})
        self.assertFalse(any(p['card_id']=='0' for p in patches))
        self.assertEqual(raw,self.path.read_bytes())

    def test_approval_persists_source_and_only_one_explicit_normal_region(self):
        saved=self.store.review_drafts(self.payload())
        row=saved['rows'][0];annotation=row['side_annotations']['front']
        self.assertEqual(annotation['region_labels'],{'upper_center':dict(corner_defect=None,edge_defect=0,surface_defect=None)})
        record=row['ai_draft_reviews'][0]
        self.assertEqual((record['author'],record['reviewed_by'],record['decision']),('Codex','confirming-human','approve'))
        self.assertFalse(saved['drafts'][0]['available'])
        reloaded=ReviewStore(self.path)
        self.assertEqual(record,reloaded.rows[0]['ai_draft_reviews'][0])
        payload=reloaded.snapshot();payload['rows'][0]['notes']='ordinary edit'
        payload['rows'][0]['ai_draft_reviews']=[]
        reloaded.save(payload)
        self.assertEqual(record,reloaded.rows[0]['ai_draft_reviews'][0])
        exported=reloaded.export(reloaded.revision)
        self.assertEqual(record,json.loads(Path(exported['output']).read_text().splitlines()[0])['ai_draft_reviews'][0])
        patches,_=point_rows(self.path,grid=True,splits={'train'})
        self.assertEqual(len([p for p in patches if p['card_id']=='0']),1)
        with self.assertRaises(ValueError):self.store.review_drafts(self.payload())

    def test_rejection_does_not_change_labels_or_points(self):
        original=copy.deepcopy(self.store.rows)
        result=self.store.review_drafts(self.payload('reject'))
        self.assertEqual(original[0]['labels'],result['rows'][0]['labels'])
        self.assertEqual(original[0]['side_annotations'],result['rows'][0]['side_annotations'])
        self.assertEqual(result['rows'][0]['ai_draft_reviews'][0]['decision'],'reject')

    def test_changed_image_box_and_test_split_block_approval(self):
        for change in ('image','box','test','unreviewed'):
            with self.subTest(change=change):
                rows=copy.deepcopy(self.store.rows)
                proposal=copy.deepcopy(self.draft)
                if change=='image':proposal['image_sha256']='0'*64
                if change=='box':proposal['box']=[.01,0,1,1]
                if change=='test':rows[0]['split']='test'
                if change=='unreviewed':rows[0]['side_annotations']['front']['box_reviewed']=False
                self.drafts.write_text(json.dumps([proposal]))
                from card_condition.label_drafts import review_drafts
                with self.assertRaises(ValueError):review_drafts(rows,self.drafts,['normal-edge'],'approve','Human')

    def test_known_labels_points_or_glare_block_normal(self):
        from card_condition.label_drafts import review_drafts
        for change in ('known','point','glare'):
            rows=copy.deepcopy(self.store.rows);annotation=rows[0]['side_annotations']['front']
            if change=='known':annotation['region_labels']={'upper_center':dict(corner_defect=None,edge_defect=1,surface_defect=None)}
            if change=='point':annotation['defect_points']=[dict(label='edge_defect',x=.5,y=.1)]
            if change=='glare':annotation.update(visibility_issues=['glare'],glare_areas=['upper_center'])
            with self.assertRaises(ValueError):review_drafts(rows,self.drafts,['normal-edge'],'approve','Human')

    def test_no_forged_ids_empty_reviewer_or_stale_revision(self):
        for changes in (dict(ids=['forged']),dict(reviewed_by=''),dict(ids=['normal-edge','normal-edge'])):
            with self.assertRaises(ValueError):self.store.review_drafts({**self.payload(),**changes})
        with self.assertRaises(FileExistsError):self.store.review_drafts({**self.payload(),'revision':'stale'})
        self.assertNotIn('ai_draft_reviews',self.store.rows[0])

    def test_duplicate_target_proposals_fail_closed(self):
        self.drafts.write_text(json.dumps([self.draft,{**self.draft,'id':'other','value':1}]))
        with self.assertRaises(ValueError):self.store.snapshot()

    def test_defect_approval_preserves_other_kinds_and_updates_face(self):
        proposal={**self.draft,'label':'surface_defect','area':'center','value':1}
        self.drafts.write_text(json.dumps([proposal]))
        payload=self.store.snapshot();payload['rows'][0]['side_annotations']['front']['labels']['surface_defect']=None
        payload['rows'][0]['labels']['surface_defect']=None
        self.store.save(payload)
        row=self.store.review_drafts(self.payload())['rows'][0]
        self.assertEqual(row['side_annotations']['front']['labels']['surface_defect'],1)
        self.assertEqual(row['labels']['surface_defect'],1)
        self.assertIsNone(row['side_annotations']['front']['region_labels']['center']['edge_defect'])

    def test_http_approval_requires_token_and_persists_human_truth(self):
        import threading
        from urllib.request import Request,urlopen
        from urllib.error import HTTPError
        from card_condition.review import ReviewServer
        with ReviewServer(self.path,0) as server:
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                payload=json.dumps(dict(revision=server.store.revision,ids=['normal-edge'],decision='approve',reviewed_by='HTTP Human')).encode()
                request=Request(server.origin+'/api/draft-review',data=payload,headers={'Content-Type':'application/json'})
                with self.assertRaises(HTTPError):urlopen(request)
                request.add_header('X-Review-Token',server.store.token)
                with urlopen(request) as response:result=json.load(response)
                self.assertEqual(result['rows'][0]['ai_draft_reviews'][0]['reviewed_by'],'HTTP Human')
                self.assertEqual(result['rows'][0]['side_annotations']['front']['region_labels']['upper_center']['edge_defect'],0)
            finally:
                server.shutdown();thread.join()
