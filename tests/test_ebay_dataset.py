import io
import json
import sqlite3
import tempfile
import copy
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from pathlib import Path

from PIL import Image

from card_condition.ebay_dataset import collect, decoded_hash, export_selected, reserve_screen_call, select_photos, validate_selection, back_is_complete, human_back_checks


class EbayDatasetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        photos = []
        for index, color in enumerate(('red', 'blue', 'green')):
            stream = io.BytesIO()
            Image.new('RGB', (440, 600), color).save(stream, 'PNG')
            raw = stream.getvalue()
            path = self.root / f'{index}.png'
            path.write_bytes(raw)
            digest, size = decoded_hash(raw)
            photos.append(dict(path=str(path), url=f'https://i.ebayimg.com/{index}.png', sha256=digest, size=size))
        self.item = dict(id='ebay-pair-example', item_id='v1|123|0', title='card', listing_url='https://www.ebay.com/itm/123', query='vintage', photos=photos)
        self.result = dict(single_card_listing=True, photos=[
            dict(index=0, side='other', card_count=2, full_card=True, logo_visible=True, confidence=.99),
            dict(index=1, side='back', card_count=1, full_card=True, logo_visible=True, confidence=.98),
            dict(index=2, side='front', card_count=1, full_card=True, logo_visible=False, confidence=.98)])
        self.boundary = dict(id=self.item['id'], card_count=1, top_visible=True, bottom_visible=True,
                             left_visible=True, right_visible=True, corners_visible=True,
                             logo_visible=True, obstructed=False, confidence=.99)

    def test_selects_by_visual_side_not_photo_order(self):
        result = select_photos(self.item, self.result, 'test-vision')
        self.assertEqual((result['front'], result['back']), (2, 1))

    def test_collector_fetches_all_detail_images_and_preserves_originals(self):
        class Provider:
            marketplace = 'EBAY_US'
            def search(self, query, limit):
                return [{'ebay_item_id': 'v1|new|0', 'title': 'single card'}]
            def access_token(self):
                return 'test-token'
        def detail(url, headers):
            return dict(title='single card', image={'imageUrl': '0'},
                        additionalImages=[{'imageUrl': '1'}, {'imageUrl': '2'}, {'imageUrl': '0'}])
        with patch('card_condition.ebay_dataset.ebay_image', side_effect=lambda url: Path(self.item['photos'][int(url)]['path']).read_bytes()):
            path = collect(Provider(), detail, self.root/'run', self.root/'learn', ['query'], 1)
        catalog = json.loads(path.read_text())
        photos = catalog['items'][0]['photos']
        self.assertEqual(len(photos), 3)
        self.assertEqual(Path(photos[2]['path']).read_bytes(), Path(self.item['photos'][2]['path']).read_bytes())
        self.assertNotIn('front', catalog['items'][0])
        with patch.object(Provider, 'search', side_effect=AssertionError('Completed collection must not search again')):
            self.assertEqual(collect(Provider(), detail, self.root/'run', self.root/'learn', ['query'], 1), path)

    def test_reference_roots_block_old_item_and_relisted_pixels_without_writes(self):
        old=self.root/'old';old.mkdir();(old/'source.json').write_text(json.dumps({'item_id':'old-id'}))
        photo=old/'known.png';photo.write_bytes(Path(self.item['photos'][0]['path']).read_bytes())
        before={p.name:p.read_bytes() for p in old.iterdir()}
        provider=SimpleNamespace(search=lambda q,limit:[{'ebay_item_id':'old-id','title':'card'},{'ebay_item_id':'new-id','title':'card'}],access_token=lambda:'fixture',marketplace='EBAY_US')
        seen=[]
        def detail(url,headers):
            seen.append(url)
            return {'image':{'imageUrl':'0'},'additionalImages':[{'imageUrl':'1'}]}
        with patch('card_condition.ebay_dataset.ebay_image',side_effect=lambda url:Path(self.item['photos'][int(url)]['path']).read_bytes()):
            path=collect(provider,detail,self.root/'reference-run',self.root/'new-learn',['q'],1,reference_learn=[old])
        catalog=json.loads(path.read_text());self.assertEqual(catalog['items'],[])
        self.assertEqual(len(seen),1);self.assertIn('new-id',seen[0]);self.assertIn('previously provided image',catalog['failures'][0]['error'])
        self.assertEqual(before,{p.name:p.read_bytes() for p in old.iterdir()})

    def test_cropped_or_missing_logo_or_multiple_cards_never_export(self):
        for field, value in [('full_card', False), ('logo_visible', False), ('card_count', 2), ('confidence', .6)]:
            with self.subTest(field=field):
                answer = json.loads(json.dumps(self.result))
                answer['photos'][1][field] = value
                self.assertEqual(select_photos(self.item, answer, 'vision')['status'], 'needs_review')

    def test_duplicate_indices_and_nonfinite_confidence_rejected(self):
        for mutate in (lambda a: a['photos'][0].update(index=1),
                       lambda a: a['photos'][1].update(confidence=float('nan'))):
            answer = json.loads(json.dumps(self.result))
            mutate(answer)
            with self.assertRaises(ValueError):
                select_photos(self.item, answer, 'vision')

    def test_front_closeup_is_not_preferred_over_full_card(self):
        self.result['photos'][2]['full_card'] = False
        self.assertEqual(select_photos(self.item, self.result, 'vision')['status'], 'needs_review')

    def test_transparent_stand_or_one_hidden_edge_blocks_second_gate(self):
        row = dict(card_count=1, top_visible=True, bottom_visible=True, left_visible=True,
                   right_visible=True, corners_visible=True, logo_visible=True, obstructed=False, confidence=.99)
        self.assertTrue(back_is_complete(row))
        self.assertFalse(back_is_complete({**row, 'obstructed': True}))
        self.assertFalse(back_is_complete({**row, 'bottom_visible': False}))
        self.assertFalse(back_is_complete({**row, 'collage_or_inset': True}))
        self.assertFalse(back_is_complete({**row, 'collage_or_inset': 'false'}))
        self.assertTrue(back_is_complete({**row, 'collage_or_inset': False}))

    def test_seller_example_back_is_not_selected_over_actual_back(self):
        self.result['photos'][0].update(side='back',card_count=1,confidence=1.,reason='상태 설명 예시 사진')
        self.assertEqual(select_photos(self.item,self.result,'vision')['back'],1)
        self.result['photos'][0].update(reason='뒷면',stock_or_example=True)
        self.assertEqual(select_photos(self.item,self.result,'vision')['back'],1)
        self.result['photos'][0].update(stock_or_example=False,collage_or_inset=True)
        self.assertEqual(select_photos(self.item,self.result,'vision')['back'],1)

    def test_missing_wordmark_blocks_special_back_even_if_boolean_claims_logo(self):
        self.result['photos'][1]['logo_text']=''
        self.assertEqual(select_photos(self.item,self.result,'vision')['status'],'needs_review')
        self.result['photos'][1]['logo_text']='Pokémon™'
        self.assertEqual(select_photos(self.item,self.result,'vision')['status'],'accepted')

    def test_explicit_human_back_confirmation_does_not_invent_defect_or_pair_truth(self):
        screens={self.item['id']:dict(selection=select_photos(self.item,self.result,'vision'))}
        data=human_back_checks([self.item],screens,{},[self.item['id']],reviewer='Human reviewer')
        check=data['checks'][self.item['id']]
        self.assertTrue(back_is_complete(check))
        self.assertNotIn('confidence',check)
        choice={**screens[self.item['id']]['selection'], 'back_boundary_checks':check,
                'back_boundary_verified_by':'human: Human reviewer'}
        output=self.root/'human-export.jsonl'
        export_selected(dict(learn=str(self.root/'learn'),items=[self.item]),{self.item['id']:choice},output)
        row=json.loads(output.read_text())
        self.assertFalse(row['pair_verified'])
        self.assertTrue(all(v is None for v in row['labels'].values()))
        provenance=json.loads((Path(row['front']).parent/'source.json').read_text())
        self.assertEqual(provenance['photo_eligibility']['back_boundary_checks']['verification_method'],'human')

    def test_human_rejection_unknown_id_and_conflicting_decisions_fail_closed(self):
        screens={self.item['id']:dict(selection=select_photos(self.item,self.result,'vision'))}
        rejected=human_back_checks([self.item],screens,{},rejected=[self.item['id']],reviewer='Human')
        self.assertFalse(back_is_complete(rejected['checks'][self.item['id']]))
        for approved,rejected,reviewer in [(['unknown'],[],'Human'),([self.item['id']],[],''),
                                          ([self.item['id']],[self.item['id']],'Human')]:
            with self.assertRaises(ValueError):
                human_back_checks([self.item],screens,{},approved,rejected,reviewer)

    def test_human_confirmation_is_bound_to_selected_photo_hash(self):
        screens={self.item['id']:dict(selection=select_photos(self.item,self.result,'vision'))}
        data=human_back_checks([self.item],screens,{},[self.item['id']],reviewer='Human')
        self.item['photos'][1]['sha256']='changed'
        with self.assertRaises(ValueError):
            human_back_checks([self.item],screens,data)
        fresh=human_back_checks([self.item],screens,data,[self.item['id']],reviewer='Human reconfirmation')
        self.assertEqual(fresh['input_sha256'][self.item['id']],'changed')

    def test_export_has_no_invented_truth_and_preserves_two_original_files(self):
        choice = select_photos(self.item, self.result, 'vision')
        with self.assertRaises(ValueError):
            export_selected(dict(learn=str(self.root/'learn'), items=[self.item]), {self.item['id']: choice}, self.root/'unverified.jsonl')
        choice.update(back_boundary_checks=self.boundary, back_boundary_verified_by='vision')
        catalog = dict(learn=str(self.root/'learn'), items=[self.item])
        output = self.root/'selected.jsonl'
        self.assertEqual(export_selected(catalog, {self.item['id']: choice}, output), 1)
        row = json.loads(output.read_text())
        self.assertTrue(all(value is None for value in row['labels'].values()))
        self.assertFalse(row['pair_verified'])
        self.assertEqual(row['reviewed_by'], '')
        self.assertEqual(Path(row['back']).read_bytes(), Path(self.item['photos'][1]['path']).read_bytes())
        self.assertEqual(len(row['images']), 2)
        with self.assertRaises(FileExistsError):
            export_selected(catalog, {self.item['id']: choice}, output)

    def test_changed_image_and_missing_eligibility_rejected(self):
        choice = select_photos(self.item, self.result, 'vision')
        choice.update(back_boundary_checks=self.boundary, back_boundary_verified_by='vision')
        invalid = {**choice, 'back_full': False}
        with self.assertRaises(ValueError):
            validate_selection(invalid, self.item)
        Path(self.item['photos'][1]['path']).write_bytes(Path(self.item['photos'][0]['path']).read_bytes())
        with self.assertRaises(ValueError):
            export_selected(dict(learn=str(self.root/'learn'), items=[self.item]), {self.item['id']: choice}, self.root/'out.jsonl')

    def test_shared_quota_reservation_stops_at_existing_bucket_limit(self):
        path = self.root/'quota.sqlite3'
        with sqlite3.connect(path) as db:
            db.executescript('CREATE TABLE setting(key TEXT PRIMARY KEY,value TEXT);'
                             'CREATE TABLE ai_usage(day TEXT PRIMARY KEY,calls INTEGER);'
                             'CREATE TABLE ai_usage_bucket(day TEXT,bucket TEXT,calls INTEGER,PRIMARY KEY(day,bucket));')
            db.executemany('INSERT INTO setting VALUES(?,?)', [('gemini_daily_limit','5'),('gemini_identify_daily_limit','1')])
        self.assertTrue(reserve_screen_call(path))
        self.assertFalse(reserve_screen_call(path))
        with sqlite3.connect(path) as db:
            self.assertEqual(db.execute('SELECT SUM(calls) FROM ai_usage_bucket').fetchone()[0], 1)

    def test_cli_partial_confirmation_rejects_stale_contract_and_preserves_review(self):
        from tools.collect_ebay_dataset import main
        output = self.root/'run'
        (output/'screening').mkdir(parents=True)
        items = []
        for identity in ('first', 'second'):
            item = copy.deepcopy(self.item)
            item['id'] = identity
            items.append(item)
            screen = dict(model='fixture', evidence=self.result,
                          input_sha256=[p['sha256'] for p in item['photos']])
            (output/'screening'/f'{identity}.json').write_text(json.dumps(screen))
        (output/'catalog.json').write_text(json.dumps(dict(collection_complete=True,
             learn=str(self.root/'learn'), items=items)))
        (output/'verified-backs.json').write_text(json.dumps(dict(prompt_version='ebay-back-boundary-v2',
             input_sha256={i['id']:i['photos'][1]['sha256'] for i in items},
             evidence=[{**self.boundary,'id':i['id']} for i in items], model='stale')))
        (output/'last-error.json').write_text(json.dumps(dict(stage='back_verification',error='old quota failure')))
        (output/'labels-review.jsonl').write_text('human work must survive')
        provider = SimpleNamespace(EbayProvider=lambda:SimpleNamespace(configured=True),
                                   GeminiProvider=lambda:SimpleNamespace(configured=True), request_json=None)
        argv = ['collect', '--consumer-root', str(self.root), '--learn', str(self.root/'learn'),
                '--output', str(output), '--quota-db', str(self.root/'unused.sqlite3'), '--screen-limit', '0']
        for extra, accepted, pending in [(['--confirm-back','first','--confirmed-by','Human'],1,1),
                                         (['--reject-back','second','--confirmed-by','Human'],1,0),([],1,0)]:
            with patch.dict(sys.modules, {'pokecollector.providers':provider}), patch.object(sys,'argv',argv+extra), patch('builtins.print'):
                main()
            summary=json.loads((output/'summary.json').read_text())
            self.assertEqual((summary['accepted'],summary['awaiting_boundary_verification'],summary['gemini_attempts_this_run']), (accepted,pending,0))
        self.assertFalse((output/'last-error.json').exists())
        self.assertFalse((self.root/'unused.sqlite3').exists())
        self.assertEqual((output/'labels-review.jsonl').read_text(),'human work must survive')
        self.assertFalse((self.root/'learn'/'second').exists())


if __name__ == '__main__':
    unittest.main()


class TitleGateTests(unittest.TestCase):
    def test_only_explicit_lots_and_variants_blocked(self):
        from card_condition.ebay_dataset import non_single_listing
        for title in ('Pokemon Holo Card Lot 3 Cards', '45 vintage Pokémon cards',
                      'Vintage cards Choose your Card', 'Pick Your Card Raichu'):
            self.assertTrue(non_single_listing(title), title)
        for title in ('Slugma 72/97 Common Dragon Pokemon', 'Card lots of scratches',
                      'Pokemon card PSA 10'):
            self.assertFalse(non_single_listing(title), title)

    def test_obvious_lot_never_downloads_or_consumes_collection_slot(self):
        with tempfile.TemporaryDirectory() as directory:
            provider=SimpleNamespace(search=lambda q,limit:[{'ebay_item_id':'lot','title':'Lot of 3 cards'}])
            def no_detail(*args,**kwargs):
                raise AssertionError('Lot must be excluded before API detail or image download')
            path=collect(provider,no_detail,Path(directory)/'out',Path(directory)/'learn',['q'],1)
            catalog=json.loads(path.read_text())
            self.assertEqual(catalog['items'],[])
            self.assertIn('Explicit multi-card',catalog['failures'][0]['error'])


class CollectionOnlyCliTests(unittest.TestCase):
    def test_default_cli_cannot_initialize_gemini_or_reserve_quota(self):
        import importlib.util
        import contextlib
        from types import ModuleType
        tool=Path(__file__).resolve().parents[1]/'tools/collect_ebay_dataset.py'
        spec=importlib.util.spec_from_file_location('intake_cli_test',tool)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);run=root/'run';run.mkdir()
            (run/'catalog.json').write_text(json.dumps(dict(collection_complete=True,learn=str(root/'learn'),items=[])))
            providers=ModuleType('pokecollector.providers')
            providers.EbayProvider=lambda:SimpleNamespace(configured=True)
            def forbidden(*args,**kwargs):
                raise AssertionError('Default collection must not initialize Gemini or reserve quota')
            providers.GeminiProvider=forbidden;providers.request_json=forbidden
            package=ModuleType('pokecollector');package.__path__=[]
            with patch.dict(sys.modules,{'pokecollector':package,'pokecollector.providers':providers}), \
                 patch.object(sys,'argv',['collect','--consumer-root',str(root),'--learn',str(root/'learn'),'--output',str(run)]), \
                 patch.object(module,'reserve_screen_call',side_effect=forbidden), \
                 contextlib.redirect_stdout(io.StringIO()):
                module.main()
            summary=json.loads((run/'collection-summary.json').read_text())
            self.assertEqual(summary['gemini_attempts_this_run'],0)
            self.assertEqual(summary['mode'],'collection_only')
            self.assertEqual(summary['condition_labels_created'],0)
