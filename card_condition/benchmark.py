"""Local warm inference timing on validation sides, including image preprocessing."""
import json
import math
from pathlib import Path
import statistics
import time

from .side_experiment import side_rows
from .side_model import SideAnalyzer
from .point_probe import digest
from .evaluation_inputs import unchanged_inputs


def benchmark_validation(manifest, checkpoint, output, device='auto'):
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists: choose a new report path')
    before = {p: digest(p) for p in (manifest, checkpoint)}
    rows, _, _ = side_rows(manifest, splits={'val'})
    if not rows:
        raise ValueError('No annotated validation sides')
    for row in rows:
        path = str(Path(row['image']).resolve())
        if path not in before:
            before[path] = digest(path)
    started = time.perf_counter()
    analyzer = SideAnalyzer(checkpoint, device)
    load_seconds = time.perf_counter() - started
    analyzer.predict(rows[0]['image'], rows[0]['box'])
    durations = []
    for _ in range(3):
        for row in rows:
            started = time.perf_counter()
            analyzer.predict(row['image'], row['box'])
            durations.append(time.perf_counter() - started)
    unchanged_inputs(before)
    result = {'evaluation_kind': 'validation_benchmark', 'n_sides': len(rows), 'repeats': 3,
              'samples': len(durations), 'warmup_calls': 1, 'load_seconds': load_seconds,
              'median_seconds': statistics.median(durations),
              'p95_seconds': sorted(durations)[math.ceil(.95 * len(durations)) - 1],
              'min_seconds': min(durations), 'max_seconds': max(durations),
              'model_sha256': analyzer.model_sha256,
              'manifest_sha256': before[manifest],
              'device': str(analyzer.device),
              'backbone_name': analyzer.meta.get('backbone_name', 'mobilenet_v3_small'),
              'requires_gemini': True, 'production_ready': False, 'actual_calls_saved': 0,
              'limitations': ['Warm local timings include image read/preprocessing and model inference.',
                             'OS file cache, device load and thermal state can change timings; memory is not measured.']}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return result
