import copy
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest

import torch
from torch import nn

from card_condition.listing_model import ListingAnalyzer
from card_condition.listing_review import review_page, review_record
from card_condition.regions import REGION_LABELS
from card_condition.side_model import backbone_for
from test_release import fixture_release

CELL = ('front', 'center', 'surface_defect')


def build(root):
    """Random-init release with region, recall and observation checkpoints; the report is a real run."""
    manifest, _ = fixture_release(root)
    data, files = json.loads(manifest.read_text()), {}
    for seed, role in ((1, 'recall'), (2, 'observation')):
        torch.manual_seed(seed)
        backbone, dimension = backbone_for('mobilenet_v3_small')
        meta = (dict(architecture='mobilenet_v3_small_region_v1', labels=list(REGION_LABELS), supported=['surface_defect'],
                     image_size=224, head=nn.Linear(dimension, len(REGION_LABELS)).state_dict()) if role == 'recall' else
                dict(architecture='mobilenet_v3_small_visibility_v1', target='observation_limited', image_size=224,
                     head=nn.Linear(dimension, 1).state_dict()))
        files[role] = root/f'{role}.pt'
        torch.save(dict(meta, backbone=backbone.state_dict()), files[role])
        data['checkpoints'][role] = dict(file=files[role].name, sha256=hashlib.sha256(files[role].read_bytes()).hexdigest())
    manifest.write_text(json.dumps(data))
    request = json.loads((root/'request.json').read_text())
    report = ListingAnalyzer(release=manifest, device='cpu').analyze(request)
    (root/'report.json').write_text(json.dumps(report))
    return report


def page_for(root, report, name='page.html'):
    path = root/'variant.json'
    path.write_text(json.dumps(report))
    review_page(path, root/'request.json', root/name)
    return (root/name).read_text()


class ListingReviewEvidenceTest(unittest.TestCase):
    def test_real_three_checkpoint_release_shows_evidence_and_binds_the_record(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = build(root)
            self.assertEqual({'region', 'observation', 'recall'}, set(report['release']['checkpoint_sha256']))
            summary = review_page(root/'report.json', root/'request.json', root/'page.html')
            page, candidates = (root/'page.html').read_text(), report['recall_review']['candidates']
            self.assertEqual((len(candidates), len(report['observation_evidence']['records'])),
                             (summary['recall_candidates'], summary['observation_faces']))
            self.assertEqual(2 * len(candidates), page.count('recall 후보 · primary'))
            self.assertIn(report['observation_evidence']['model_sha256'], page)
            self.assertIn(report['recall_review']['model_sha256'], page)
            self.assertIn('observation, recall, region', page)
            decisions = json.loads(re.search(r'id="data">(.*?)</script>', page).group(1))
            (root/'done.json').write_text(json.dumps(dict(report_sha256=decisions['report_sha256'], id=decisions['id'], decisions=[
                dict(side=s, area=a, label=l, decision='confirmed') for s, a, l in decisions['cells']])))
            review_record(root/'report.json', root/'done.json', root/'record.json')
            record = json.loads((root/'record.json').read_text())
            self.assertEqual(report['observation_evidence']['model_sha256'], record['observation_model_sha256'])
            self.assertEqual(report['recall_review']['model_sha256'], record['recall_model_sha256'])
            self.assertEqual([[c['side'], c['area'], c['label']] for c in report['listing_readiness']['records'][0]['cells']
                              if (c['side'], c['area'], c['label']) in {(x['side'], x['area'], x['label']) for x in candidates}],
                             record['recall_candidate_cells'])

    def test_one_constructed_candidate_marks_only_its_cell_and_shows_its_scores(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = build(root)
            report['recall_review']['candidates'] = [dict(side='front', area='center', label='surface_defect', primary_score=.61,
                                                          secondary_score=None, reason='model_suspicion', action='review_required')]
            report['observation_evidence']['records'][0]['observation_limit_score'] = .42
            page = page_for(root, report)
            self.assertEqual(1, page.count(' recall"'))
            row = re.search(r"<tr data-key='front\|center\|surface_defect'>(.*?)</tr>", page, re.S).group(1)
            self.assertIn('recall 후보 · primary 0.610 / secondary -', row)
            other = re.search(r"<tr data-key='front\|upper_left\|edge_defect'>(.*?)</tr>", page, re.S).group(1)
            self.assertNotIn('recall 후보', other)
            self.assertIn('0.420', page)

    def test_inconsistent_evidence_is_rejected_before_any_page_or_record(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = build(root)
            good = dict(side='front', area='center', label='surface_defect', primary_score=.6, secondary_score=.2, reason='r', action='a')
            broken = copy.deepcopy(report)
            broken['recall_review']['candidates'] = [good]
            self.assertIn('recall 후보', page_for(root, broken, 'control.html'))
            for name, candidates in (('unknown area', [dict(good, area='nowhere')]), ('list side', [dict(good, side=['front'])]),
                                     ('not an object', ['text']), ('duplicate', [good, dict(good)]),
                                     ('nan primary', [dict(good, primary_score=float('nan'))]),
                                     ('string secondary', [dict(good, secondary_score='high')]),
                                     ('missing primary', [dict(good, primary_score=None)])):
                broken = copy.deepcopy(report)
                broken['recall_review']['candidates'] = candidates
                with self.subTest(name), self.assertRaises(ValueError):
                    page_for(root, broken, 'bad.html')
            for mutate in (lambda r: r['recall_review'].update(candidates='x'),
                           lambda r: r['observation_evidence']['records'][0].update(observation_limit_score=1.5),
                           lambda r: r['observation_evidence']['records'][0].update(side='left'),
                           lambda r: r['observation_evidence'].update(records='x'),
                           lambda r: r['observation_evidence']['records'][0].update(human_visibility_issues='glare')):
                broken = copy.deepcopy(report)
                mutate(broken)
                with self.assertRaises(ValueError):
                    page_for(root, broken, 'bad.html')
            self.assertFalse((root/'bad.html').exists())
            report['recall_review']['candidates'] = [dict(good, area='nowhere')]
            (root/'bad-report.json').write_text(json.dumps(report))
            (root/'d.json').write_text(json.dumps(dict(report_sha256=hashlib.sha256((root/'bad-report.json').read_bytes()).hexdigest(),
                                                      id='one', decisions=[dict(side=c['side'], area=c['area'], label=c['label'], decision='confirmed')
                                                                            for c in report['listing_readiness']['records'][0]['cells']])))
            with self.assertRaises(ValueError):
                review_record(root/'bad-report.json', root/'d.json', root/'bad-record.json')
            self.assertFalse((root/'bad-record.json').exists())

    def test_report_text_is_escaped_in_the_page(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = build(root)
            report['listing_readiness']['records'][0]['cells'][0]['reason'] = '<script>alert(1)</script>'
            report['observation_evidence']['records'][0]['reason'] = '<img src=x onerror=alert(2)>'
            report['observation_evidence']['limitations'] = ['<b>x</b>']
            report['recall_review']['policy'] = '<u>p</u>'
            page = page_for(root, report)
            for raw in ('<script>alert(1)</script>', '<img src=x', '<b>x</b>', '<u>p</u>'):
                self.assertNotIn(raw, page)
            self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', page)
            self.assertIn('&lt;img src=x onerror=alert(2)&gt;', page)


if __name__ == '__main__':
    unittest.main()
