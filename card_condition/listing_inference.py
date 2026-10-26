"""Validation-only whole supported-region inference, without ground-truth selection."""
from contextlib import nullcontext
import json
import hashlib
import io
import math
from pathlib import Path
import time

import torch

from .data import load_manifest
from .edge_views import patch_features, batched_patch_features
from .listing_readiness import listing_readiness
from .model import checked_sigmoid, device_for
from .point_probe import digest, load_probe_model
from .regions import GLARE_AREAS, REGION_LABELS, REGION_TARGET_AREAS, region_box, validate_annotations


def infer_listings(manifest, checkpoint, output, device='auto', observation_checkpoint=None, batch_views=False, profile_memory=False):
    if type(profile_memory) is not bool:
        raise ValueError('profile_memory must be boolean')
    if type(batch_views) is not bool:
        raise ValueError('batch_views must be boolean')
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists: choose a new report path')
    before = {str(Path(p).resolve()): digest(p) for p in (manifest, checkpoint)}
    observation_sha256 = None
    if observation_checkpoint is not None:
        observation_sha256 = digest(observation_checkpoint)
        before[str(Path(observation_checkpoint).resolve())] = observation_sha256
    records = load_manifest(manifest, splits={'val'}, require_gradable=False)
    records = [r for r in records if not r.get('excluded')]
    if not records:
        raise ValueError('No non-excluded validation listings')
    for row in records:
        validate_annotations(row.get('side_annotations', {}), row)
        for side in ('front', 'back'):
            if row.get(side):
                before[row[side]] = digest(row[side])
    device = device_for(device)
    checkpoint_bytes = Path(checkpoint).read_bytes()
    if hashlib.sha256(checkpoint_bytes).hexdigest() != before.get(str(Path(checkpoint).resolve())):
        raise ValueError('Listing checkpoint changed before loading; no report saved')
    meta, backbone, head, policy = load_probe_model(io.BytesIO(checkpoint_bytes), device)
    del checkpoint_bytes
    supported = meta['supported']
    predictions = []
    features_for = batched_patch_features if batch_views else patch_features
    if device.type == 'mps':
        torch.mps.synchronize()
    started = time.perf_counter()
    from .inference_memory import profile_mps_memory
    memory_context = profile_mps_memory(backbone, device) if profile_memory else nullcontext(None)
    with torch.inference_mode(), memory_context as memory:
        for row in records:
            for side in ('front', 'back'):
                annotation = row.get('side_annotations', {}).get(side)
                if (not row.get(side) or not annotation or annotation['box'] is None
                        or 'visibility_issues' not in annotation):
                    continue
                issues, glare = annotation.get('visibility_issues', []), annotation.get('glare_areas', [])
                for area in GLARE_AREAS:
                    if (not any(area in REGION_TARGET_AREAS[k] for k in supported)
                            or set(issues)-{'glare'} or 'glare' in issues and (not glare or area in glare)):
                        continue
                    patch = dict(card_id=row['id'], group=row['group'], side=side, area=area,
                        image=row[side], card_box=annotation['box'], box=region_box(annotation['box'], area))
                    values = checked_sigmoid(head(features_for(backbone, patch, device, policy,
                        meta.get('image_size', 224))))[0].cpu().tolist()
                    if not all(math.isfinite(v) for v in values):
                        raise ValueError('Non-finite listing output; no report saved')
                    patch['probabilities'] = {k: values[i] if k in supported and area in REGION_TARGET_AREAS[k]
                        else None for i, k in enumerate(REGION_LABELS)}
                    predictions.append(patch)
    observation = None
    if observation_checkpoint is not None:
        from .listing_observation import observation_evidence
        observation = observation_evidence(records, observation_checkpoint, str(device),
            expected_model_sha256=observation_sha256)
    if device.type == 'mps':
        torch.mps.synchronize()
    if any(digest(path) != sha for path, sha in before.items()):
        raise ValueError('Listing inputs changed during inference; no report saved')
    readiness = listing_readiness(records, predictions, supported)
    readiness['limitations'][0] = 'All supported observable validation regions inferred; this is not an accuracy evaluation.'
    result = dict(evaluation_kind='validation_listing_inference',
        manifest_sha256=before[str(Path(manifest).resolve())], checkpoint_sha256=before[str(Path(checkpoint).resolve())],
        architecture=meta['architecture'], image_size=meta.get('image_size', 224), supported=supported,
        device=str(device), elapsed_seconds=time.perf_counter()-started, inferred_regions=len(predictions),
        predictions=predictions, listing_readiness=readiness, training_performed=False,
        ground_truth_used_for_region_selection=False, final_performance_claim=False,
        production_ready=False, requires_gemini=True, actual_calls_saved=0,
        limitations=['Val only; train/test photographs are not opened by this command.',
            'Card boxes and observation limits are human supplied; no automatic glare or card detection.',
            'Unknown truth remains unknown; model scores are not new labels or condition grades.',
            'Repeated validation and exploratory thresholds do not authorize Gemini bypass.'])
    if memory is not None:
        result['memory_profile'] = memory
    if batch_views:
        result['batched_views'] = True
    if observation is not None:
        result['observation_evidence'] = observation
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return result
