"""Explicit regression/final evaluation of a frozen single-side checkpoint."""
from pathlib import Path

import torch

from .evaluation_inputs import track_photos, reject_copied_test_groups, unchanged_inputs, development_sets, matched_model
from .evaluation_output import write_new_report
from .point_probe import digest
from .quality_rates import error_rates
from .data import LABELS, load_manifest
from .side_model import SideAnalyzer
from .side_experiment import side_rows, score


def evaluate_sides(manifest, checkpoint, output, kind, history=(), device='auto'):
    if kind not in ('regression', 'final'):
        raise ValueError('Choose regression or final')
    if kind == 'final' and not history:
        raise ValueError('최종평가에는 모든 이전 개발 manifest를 --history로 제공해야 합니다.')
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists: choose a new report path')
    input_hashes = {str(Path(path).resolve()):digest(path) for path in (manifest,checkpoint,*history)}
    records = load_manifest(manifest)
    if any(r['split'] != 'test' for r in records) and kind == 'final':
        raise ValueError('최종평가는 test 자료만 있는 별도 manifest를 사용하세요.')
    candidates = [r for r in records if r['split'] == 'test']
    reject_copied_test_groups(candidates)
    track_photos(candidates,input_hashes)
    rows, skipped, _ = side_rows(manifest, splits={'test'})
    if not rows:
        raise ValueError('No annotated test sides')
    meta = torch.load(checkpoint, map_location='cpu', weights_only=True)
    if (not isinstance(meta, dict) or meta.get('architecture') not in ('mobilenet_v3_small_single_side_v1', 'resnet18_single_side_v1') or meta.get('labels') != list(LABELS)
            or not set(meta.get('supported', [])) <= set(LABELS)):
        raise ValueError('Unsupported single-side checkpoint')
    groups, ids, hashes = development_sets(meta, 'training_groups')
    history_receipts = []
    for path in history:
        previous = load_manifest(path)
        track_photos(previous,input_hashes)
        groups.update(r['group'] for r in previous)
        ids.update(r['id'] for r in previous)
        hashes.update(h for r in previous for h in r['_image_hashes'])
        history_receipts.append({'path':str(Path(path).resolve()),'sha256':input_hashes[str(Path(path).resolve())]})
    conflicts = [r['id'] for r in candidates if r['id'] in ids or r['group'] in groups or set(r['_image_hashes']) & hashes]
    if conflicts:
        raise ValueError('개발에 사용된 카드/이미지가 평가 자료에 포함됨: '+', '.join(conflicts))
    analyzer = SideAnalyzer(checkpoint, device)
    matched_model(analyzer, input_hashes, checkpoint)
    probabilities = [list(analyzer.predict(r['image'], r['box']).values()) for r in rows]
    metrics,predictions=score(rows,probabilities,meta['supported'])
    if not any(sum(counts.values()) for counts in metrics.values()):
        raise ValueError('No scored supported test labels')
    unchanged_inputs(input_hashes)
    report = {'evaluation_kind':kind,'n_cards':len({r['group'] for r in rows}),'n_sides':len(rows),
              'metrics':metrics,'rates_at_05':{k:error_rates(v) for k,v in metrics.items()},
              'input_hashes':input_hashes,'predictions':predictions,'skipped':skipped,'threshold':.5,
              'history':history_receipts,'model_sha256':input_hashes[str(Path(checkpoint).resolve())],
              'manifest_sha256':input_hashes[str(Path(manifest).resolve())],
              'preprocessing':'human box + four overlapping tiles' if meta.get('tiles',False) else ('human box crop' if meta['crop'] else 'full photo'),
              'requires_gemini':True,'production_ready':False,'actual_calls_saved':0,
              'limitations':['Checks exact pixels/ids/groups in supplied history only; other photos of the same card require human grouping.',
                              'Final results must not be reused to tune the model; crop mode assumes human boxes.']}
    write_new_report(output, report)
    return report
