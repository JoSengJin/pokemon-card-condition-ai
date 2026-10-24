"""Validation-only warm patch timing; no accuracy or routing decisions."""
import json
import math
from pathlib import Path
import statistics
import time

import torch

from .edge_views import patch_features
from .model import checked_sigmoid, device_for
from .point_dataset import point_rows
from .point_probe import digest, load_probe_model
from .evaluation_inputs import unchanged_inputs


def benchmark_points(manifest, checkpoint, output, device='auto'):
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists: choose a new report path')
    before = {p: digest(p) for p in (manifest, checkpoint)}
    rows, _ = point_rows(manifest, grid=True)
    rows = [r for r in rows if r['split'] == 'val']
    if not rows:
        raise ValueError('No annotated validation patches')
    for row in rows:
        path = str(Path(row['image']).resolve())
        if path not in before:
            before[path] = digest(path)
    device = device_for(device)
    started = time.perf_counter()
    meta, backbone, head, views = load_probe_model(checkpoint, device)
    if device.type == 'mps':
        torch.mps.synchronize()
    load_seconds = time.perf_counter() - started
    durations = []
    with torch.inference_mode():
        for row in [rows[0], *rows, *rows, *rows]:
            started = time.perf_counter()
            # CPU copy synchronizes device completion, including the sigmoid/head.
            scores = checked_sigmoid(head(patch_features(backbone, row, device, views, meta.get('image_size', 224)))).cpu().tolist()
            elapsed = time.perf_counter() - started
            if not all(math.isfinite(v) for v in scores[0]):
                raise ValueError('Non-finite benchmark output')
            durations.append(elapsed)
    durations = durations[1:]
    unchanged_inputs(before)
    result = dict(evaluation_kind='validation_point_benchmark', architecture=meta['architecture'],
        device=str(device), image_size=meta.get('image_size', 224), n_patches=len(rows), groups=len({r['group'] for r in rows}),
        repeats=3, warmup_calls=1, samples=len(durations), load_seconds=load_seconds,
        median_seconds=statistics.median(durations),
        p95_seconds=sorted(durations)[math.ceil(.95*len(durations))-1],
        min_seconds=min(durations), max_seconds=max(durations),
        checkpoint_sha256=before[checkpoint], manifest_sha256=before[manifest],
        production_ready=False, requires_gemini=True, actual_calls_saved=0,
        limitations=['Per-patch timing includes image read, crop, preprocessing and synchronized inference.',
            'Not whole-listing latency; patches can share an image and benefit from OS file cache.',
            'Memory, concurrent load and production latency are not measured; no quality claim.'])
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return result
