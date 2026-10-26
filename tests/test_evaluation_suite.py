from contextlib import redirect_stdout
import io
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image
import torch
from card_condition.data import LABELS, load_manifest
from card_condition import frozen_test, frozen_candidate, region_evaluation, side_evaluation, observation_heldout
from card_condition.evaluation_suite import assess_suite
from card_condition.evaluation_suite_cli import main
from card_condition.release import file_sha256


def saved_suite(root, n=30, *, alias=False):
    history, manifest = root / 'history.jsonl', root / 'test.jsonl'
    image = root / 'development.png'
    Image.new('RGB', (40, 60), (255, 0, 255)).save(image)
    history.write_text(json.dumps(dict(id='development', group='development', split='train', front=str(image),
                                      back=None, labels={q: 0 for q in LABELS})))
    records = []
    for truth in (0, 1):
        for i in range(n):
            ident = f'test-{truth}-{i}'
            record = dict(id=ident, group=ident, split='test', labels={q: 1 if q == 'gradable' else truth for q in LABELS},
                          side_annotations={}, language='en' if i % 2 == 0 else None, edition='base')
            for side in ('front', 'back'):
                image = root / (ident + '-' + side + '.png')
                Image.new('RGB', (40, 60), (1 + truth * n + i, 30 if side == 'front' else 90, 80)).save(image)
                record[side] = str(image)
                record['side_annotations'][side] = dict(image=str(image), box=[0, 0, 1, 1], labels=dict(record['labels']),
                    region_labels={'upper_left': {q: truth for q in ('corner_defect', 'edge_defect', 'surface_defect')}},
                    visibility_issues=['glare'] if truth else [], glare_areas=[])
            records.append(record)
    if alias:
        copied = copy.deepcopy(records[0])
        copied['id'] = 'alias-' + copied['id']
        records.append(copied)
    manifest.write_text('\n'.join(json.dumps(r) for r in records))
    used = load_manifest(history, require_gradable=False)[0]
    base = dict(development_ids=['development'], development_groups=['development'], training_groups=['development'],
                development_image_hashes=used['_image_hashes'])
    models = {op: root / (op + '.pt') for op in ('region_final', 'side_final', 'observation_final')}
    torch.save(dict(base, architecture='mobilenet_v3_small_region_v1',
                    supported=['corner_defect', 'edge_defect', 'surface_defect']), models['region_final'])
    torch.save(dict(base, architecture='mobilenet_v3_small_single_side_v1', supported=list(LABELS), labels=list(LABELS), crop=True), models['side_final'])
    torch.save(dict(base, architecture='mobilenet_v3_small_visibility_v1', target='observation_limited'), models['observation_final'])
    seal, candidate = root / 'seal.json', root / 'candidate.json'
    frozen_test.seal_test(manifest, [history], seal)
    frozen_candidate.pin_candidate(seal, file_sha256(seal), manifest, models, candidate, 'cpu')
    options = dict(test_seal=seal, test_seal_sha256=file_sha256(seal), test_candidate=candidate,
                   test_candidate_sha256=file_sha256(candidate))
    def region_scores(image, *args, **kwargs):
        truth = int(Path(image).name.split('-')[1])
        return dict(probabilities={q: .9 if truth else .1 for q in ('corner_defect', 'edge_defect', 'surface_defect')}, null_reasons={})
    def side_scores(image, *args, **kwargs):
        truth = int(Path(image).name.split('-')[1])
        return {q: .9 if q == 'gradable' or truth else .1 for q in LABELS}
    def observation_scores(image, *args, **kwargs):
        return dict(observation_limit_score=.9 if int(Path(image).name.split('-')[1]) else .1)
    region = Mock(model_sha256=file_sha256(models['region_final']))
    region.analyze.side_effect = region_scores
    side = Mock(model_sha256=file_sha256(models['side_final']))
    side.predict.side_effect = side_scores
    observation = Mock(model_sha256=file_sha256(models['observation_final']))
    observation.analyze.side_effect = observation_scores
    paths = dict(region_final=root/'region.json', side_final=root/'side.json', observation_final=root/'observation/report.json')
    with patch.object(frozen_test, 'LEDGER', root/'ledger'), \
         patch.object(region_evaluation, 'RegionAnalyzer', return_value=region), \
         patch.object(side_evaluation, 'SideAnalyzer', return_value=side), \
         patch.object(observation_heldout, 'VisibilityAnalyzer', return_value=observation):
        region_evaluation.evaluate_regions(manifest, models['region_final'], paths['region_final'], [history], 'cpu', **options)
        side_evaluation.evaluate_sides(manifest, models['side_final'], paths['side_final'], 'final', [history], 'cpu', **options)
        observation_heldout.evaluate_heldout(models['observation_final'], manifest, paths['observation_final'].parent,
                                           file_sha256(models['observation_final']), 'cpu', **options)
    reports = {op: dict(path=str(path), sha256=file_sha256(path)) for op, path in paths.items()}
    return (manifest, seal, file_sha256(seal), candidate, file_sha256(candidate)), reports


class EvaluationSuiteTest(unittest.TestCase):
    def test_all_numeric_gates_do_not_certify_independence_or_actual_points(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            args, reports = saved_suite(root)
            result = assess_suite(*args, reports, root/'assessment.json')
            self.assertTrue(all(result['numeric_gates'].values()))
            self.assertEqual(10, len(result['cells']))
            self.assertEqual([], result['missing_roles'])
            for flag in ('d1_verified', 'd2_verified', 'd3_verified', 'production_ready'):
                self.assertFalse(result[flag])
            for cell in result['cells']:
                self.assertEqual(30, cell['positive_units'])
                self.assertEqual(30, cell['negative_units'])
                self.assertEqual(0., cell['false_negative_rate'])
                if cell['typed_point_response']:
                    self.assertEqual('unmeasured', cell['typed_point_response']['status'])
            unknown = [g for g in result['cells'][0]['subgroups'] if g['dimension'] == 'language' and g['value'] == 'unknown'][0]
            self.assertEqual(30, unknown['physical_cards'])
            self.assertEqual(result, json.loads((root/'assessment.json').read_text()))

    def test_partial_roles_and_small_denominators_stay_pending_and_keep_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            args, reports = saved_suite(root, 2)
            only = {'region_final': reports['region_final']}
            output = root/'assessment.json'
            result = assess_suite(*args, only, output)
            self.assertEqual(['observation_final', 'side_final'], result['missing_roles'])
            self.assertFalse(any(result['numeric_gates'].values()))
            self.assertEqual(4, len([c for c in result['cells'] if not c['supported']]))
            before = output.read_bytes()
            with self.assertRaisesRegex(ValueError, 'Output exists'):
                assess_suite(*args, reports, output)
            self.assertEqual(before, output.read_bytes())

    def test_standalone_cli_uses_original_report_pins(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            args, reports = saved_suite(root, 2)
            manifest, seal, seal_sha, candidate, candidate_sha = args
            argv = [str(manifest), str(seal), str(candidate), str(root/'assessment.json'),
                    '--seal-sha256', seal_sha, '--candidate-sha256', candidate_sha]
            for op, entry in reports.items():
                role = op.removesuffix('_final')
                argv += ['--'+role, entry['path'], '--'+role+'-sha256', entry['sha256']]
            with redirect_stdout(io.StringIO()) as output:
                status = main(argv)
            self.assertEqual(0, status)
            self.assertFalse(json.loads(output.getvalue())['d2_verified'])
