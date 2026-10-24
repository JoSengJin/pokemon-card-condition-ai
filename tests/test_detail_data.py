import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from card_condition.ebay_dataset import decoded_hash
from card_condition.detail_data import confirmed_detail_rows

class ConfirmedDetailDataTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.anchor=self.root/'back.png';self.image=self.root/'detail.png'
        Image.new('RGB',(40,60),(10,20,30)).save(self.anchor);Image.new('RGB',(60,40),(20,30,40)).save(self.image)
        photos=[dict(path=str(p),sha256=decoded_hash(p.read_bytes())[0]) for p in (self.anchor,self.image)]
        self.catalog={'items':[{'id':'listing','photos':photos}]};self.auth={'allowed_confirmed_detail_training':True}
        self.evidence=dict(source='direct user reply',user_quote='corner damage',source_image=str(self.image),source_image_sha256=hashlib.sha256(self.image.read_bytes()).hexdigest(),corner_defect=1)
        self.eligibility=dict(image=str(self.anchor),image_sha256=hashlib.sha256(self.anchor.read_bytes()).hexdigest(),reviewed_by='Codex',single_card=True,logo_visible=True,all_edges_visible=True,corners_visible=True,unobstructed=True)
        self.proposal=dict(full_back_eligibility=self.eligibility,id='detail1',group='listing',split='train',image=str(self.image),full_back_anchor=str(self.anchor),box=[.1,.1,.9,.9],label='corner_defect',human_evidence=self.evidence)

    def test_confirmed_presence_never_becomes_point_or_other_kind(self):
        rows,r=confirmed_detail_rows(self.catalog,[self.proposal],self.auth)
        self.assertEqual(rows[0]['supervision'],'region_presence');self.assertIsNone(rows[0]['point'])
        self.assertEqual(rows[0]['target'],1);self.assertEqual(rows[0]['group'],'listing')
        self.assertEqual(r['counts']['edge_defect'],{'0':0,'1':0});self.assertFalse(r['ready_labels'])

    def test_unknown_human_truth_is_excluded(self):
        self.evidence['corner_defect']=None
        rows,r=confirmed_detail_rows(self.catalog,[self.proposal],self.auth)
        self.assertEqual(rows,[]);self.assertEqual(r['skipped'][0]['reason'],'human truth unknown')

    def test_permission_and_changed_evidence_rejected(self):
        with self.assertRaises(ValueError):confirmed_detail_rows(self.catalog,[self.proposal],{})
        self.evidence['source_image_sha256']='wrong'
        with self.assertRaises(ValueError):confirmed_detail_rows(self.catalog,[self.proposal],self.auth)

    def test_listing_and_anchor_cannot_cross_splits(self):
        for existing in [[dict(group='listing',split='test')],[dict(group='other',split='val',_image_hashes=[self.catalog['items'][0]['photos'][0]['sha256']])]]:
            with self.assertRaises(ValueError):confirmed_detail_rows(self.catalog,[self.proposal],self.auth,existing)
        other=copy.deepcopy(self.proposal);other.update(id='detail2',split='test')
        with self.assertRaises(ValueError):confirmed_detail_rows(self.catalog,[self.proposal,other],self.auth)

    def test_bad_scope_duplicate_id_and_boolean_target_rejected(self):
        with self.assertRaises(ValueError):confirmed_detail_rows(self.catalog,[self.proposal,self.proposal],self.auth)
        self.proposal['group']='another'
        with self.assertRaises(ValueError):confirmed_detail_rows(self.catalog,[self.proposal],self.auth)
        self.proposal['group']='listing';self.evidence['corner_defect']=True
        with self.assertRaises(ValueError):confirmed_detail_rows(self.catalog,[self.proposal],self.auth)

    def test_confirmed_normal_is_local_only(self):
        self.evidence['corner_defect']=0
        rows,r=confirmed_detail_rows(self.catalog,[self.proposal],self.auth)
        self.assertEqual(rows[0]['target'],0);self.assertEqual(rows[0]['box'],[.1,.1,.9,.9]);self.assertEqual(r['whole_card_labels_created'],0)

    def test_missing_or_obscured_complete_anchor_is_rejected(self):
        self.proposal.pop('full_back_eligibility')
        with self.assertRaises(ValueError):confirmed_detail_rows(self.catalog,[self.proposal],self.auth)
        self.proposal['full_back_eligibility']=self.eligibility;self.eligibility['unobstructed']=False
        with self.assertRaises(ValueError):confirmed_detail_rows(self.catalog,[self.proposal],self.auth)

    def test_validation_rows_cannot_fill_training_readiness(self):
        self.proposal['split']='val'
        rows,r=confirmed_detail_rows(self.catalog,[self.proposal],self.auth)
        self.assertEqual(len(rows),1);self.assertEqual(r['counts']['corner_defect'],{'0':0,'1':0})
