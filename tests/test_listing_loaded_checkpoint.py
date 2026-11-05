import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
import torch
from card_condition import listing_inference,listing_observation,point_probe
from card_condition.regions import REGION_LABELS
from test_checkpoint_loaded_bytes import checkpoint_fixture,components


def source(root):
    checkpoint,raw,meta=checkpoint_fixture(root,'mobilenet_v3_small_point_grid_v1',REGION_LABELS)
    manifest=root/'val.jsonl';manifest.write_text('synthetic manifest mocked without opening photos')
    records=[dict(id='one',group='one',split='val',front=None,back=None,labels={},side_annotations={})]
    return checkpoint,raw,meta,manifest,records


class ListingLoadedCheckpointTest(unittest.TestCase):
    def test_actual_parser_receives_the_pinned_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);checkpoint,raw,meta,manifest,records=source(root)
            backbone,head=components()
            with patch.object(listing_inference,'load_manifest',return_value=records),patch.object(point_probe,'backbone_for',return_value=(backbone,1)),patch('card_condition.region_head.region_head',return_value=head),patch.object(listing_inference,'load_probe_model',wraps=point_probe.load_probe_model) as load:
                result=listing_inference.infer_listings(manifest,checkpoint,root/'report.json','cpu')
            self.assertEqual(raw,load.call_args.args[0].getvalue())
            self.assertEqual(hashlib.sha256(raw).hexdigest(),result['checkpoint_sha256'])
            self.assertEqual(0,result['inferred_regions'])
            self.assertFalse(result['production_ready'])
            head.assert_not_called()

    def test_swap_before_snapshot_is_rejected_before_loading(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);checkpoint,raw,meta,manifest,records=source(root)
            def swap(*args,**kwargs):
                checkpoint.write_bytes(b'different checkpoint bytes')
                return records
            with patch.object(listing_inference,'load_manifest',side_effect=swap),patch.object(listing_inference,'load_probe_model') as load:
                with self.assertRaisesRegex(ValueError,'changed before loading'):
                    listing_inference.infer_listings(manifest,checkpoint,root/'report.json','cpu')
            load.assert_not_called()
            self.assertFalse((root/'report.json').exists())

    def test_transient_path_swap_cannot_replace_loaded_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);checkpoint,raw,meta,manifest,records=source(root)
            alternate=root/'alternate.pt';torch.save(dict(meta,image_size=448),alternate)
            backbone,head=components()
            def reopen_then_restore(argument,device):
                checkpoint.write_bytes(alternate.read_bytes())
                try:
                    return point_probe.load_probe_model(argument,device)
                finally:
                    checkpoint.write_bytes(raw)
            with patch.object(listing_inference,'load_manifest',return_value=records),patch.object(point_probe,'backbone_for',return_value=(backbone,1)),patch('card_condition.region_head.region_head',return_value=head),patch.object(listing_inference,'load_probe_model',side_effect=reopen_then_restore):
                result=listing_inference.infer_listings(manifest,checkpoint,root/'report.json','cpu')
            self.assertEqual(224,result['image_size'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(),result['checkpoint_sha256'])
            self.assertEqual(raw,checkpoint.read_bytes())

    def test_observation_expected_sha_checks_injected_and_self_loaded_analyzers(self):
        row=dict(id='one',group='one',front='unused.png',back=None,
                 side_annotations={'front':dict(box=[0,0,1,1],visibility_issues=[])})
        for injected in (False,True):
            for correct in (False,True):
                with self.subTest(injected=injected,correct=correct):
                    analyzer=Mock(model_sha256='a'*64 if correct else 'b'*64)
                    analyzer.analyze.return_value=dict(observation_limit_score=.3)
                    with patch.object(listing_observation,'VisibilityAnalyzer',return_value=analyzer):
                        if correct:
                            result=listing_observation.observation_evidence([row],'synthetic.pt','cpu',analyzer=analyzer if injected else None,expected_model_sha256='a'*64)
                            self.assertEqual('a'*64,result['model_sha256'])
                            self.assertEqual(1,analyzer.analyze.call_count)
                        else:
                            with self.assertRaisesRegex(ValueError,'different checkpoint'):
                                listing_observation.observation_evidence([row],'synthetic.pt','cpu',analyzer=analyzer if injected else None,expected_model_sha256='a'*64)
                            analyzer.analyze.assert_not_called()
