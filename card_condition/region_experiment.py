"""Offline 3x3 patch baseline; only explicit human labels train the head."""
import hashlib
import json
from pathlib import Path
import time

import torch
from torch import nn

from .model import device_for
from .region_dataset import region_rows
from .regions import REGION_LABELS
from .side_model import backbone_for
from .edge_views import patch_features, tile_prefix_maps, tile_tail_features
from .side_experiment import side_tensor
from .feature_scaling import fit_train_scaler, fold_scaler
from .region_head import region_head


def group_training_weights(rows, supported, split='train'):
    """Give each physical group equal total weight per known training target."""
    counts = {}
    for row in rows:
        if row['split'] == split:
            for key in supported:
                if row['labels'][key] is not None:
                    pair = (row['group'], key)
                    counts[pair] = counts.get(pair, 0) + 1
    return [[1 / counts[(row['group'], key)]
             if row['split'] == split and key in supported and row['labels'][key] is not None else 0.0
             for key in REGION_LABELS] for row in rows]


def training_class_ratios(rows, weights, supported):
    """Balance effective train class mass after physical-group weighting."""
    ratios = []
    for i, key in enumerate(REGION_LABELS):
        mass = [sum(weights[n][i] for n, row in enumerate(rows)
                    if row['split'] == 'train' and row['labels'][key] == value) for value in (0, 1)]
        if key in supported and not all(mass):
            raise ValueError('Training class balance requires both known classes')
        ratios.append(mass[0]/mass[1] if key in supported else 1.0)
    return ratios


def side_class_training_weights(rows, supported):
    """Equal train side/class mass, then equal physical groups inside each cell."""
    counts = {}
    for row in rows:
        if row['split'] != 'train':
            continue
        for key in supported:
            value = row['labels'][key]
            if value is not None:
                if row['side'] not in ('front', 'back') or type(value) is not int or value not in (0, 1):
                    raise ValueError('Side balance requires front/back and binary training labels')
                cell = (key, row['side'], value, row['group'])
                counts[cell] = counts.get(cell, 0) + 1
    groups = {(key, side, value): sum(k == key and s == side and v == value for k, s, v, _ in counts)
              for key in supported for side in ('front', 'back') for value in (0, 1)}
    if any(not count for count in groups.values()):
        raise ValueError('Side balance requires normal and defective train groups on both sides')
    return [[1 / (4 * groups[(key, row['side'], row['labels'][key])]
                  * counts[(key, row['side'], row['labels'][key], row['group'])])
             if row['split'] == 'train' and key in supported and row['labels'][key] is not None else 0.
             for key in REGION_LABELS] for row in rows]




def class_group_validation_weights(rows, supported):
    """Equal class mass, then equal physical groups within each validation class."""
    counts = {}
    for row in rows:
        if row['split'] == 'val':
            for key in supported:
                value = row['labels'][key]
                if value is not None:
                    pair = (key, value, row['group'])
                    counts[pair] = counts.get(pair, 0)+1
    groups = {(key,value): sum(k == key and v == value for k,v,_ in counts)
              for key in supported for value in (0,1)}
    if any(not n for n in groups.values()):
        raise ValueError('Balanced selection requires both validation classes')
    return [[1/(counts[(key,row['labels'][key],row['group'])]*groups[(key,row['labels'][key])])
        if row['split'] == 'val' and key in supported and row['labels'][key] is not None else 0.
        for key in REGION_LABELS] for row in rows]

def validation_diagnostics(logits, truth, weights, supported):
    """Trace the existing validation objective; never select or update a model here."""
    logits, truth, weights = logits.detach().cpu(), truth.detach().cpu(), weights.detach().cpu()
    result = {}
    for i, key in enumerate(REGION_LABELS):
        if key not in supported:
            continue
        known = truth[:, i] >= 0
        values, targets, mass = logits[known, i], truth[known, i], weights[known, i]
        losses = nn.functional.binary_cross_entropy_with_logits(values, targets, reduction='none')
        counts = {kind: int(((targets == t) & ((values >= 0) == p)).sum())
                  for kind, t, p in (('tp',1,True),('tn',0,False),('fp',0,True),('fn',1,False))}
        classes = {}
        for value, label in ((0,'normal'),(1,'defect')):
            selected = targets == value
            total = float(mass[selected].sum())
            classes[label] = dict(known=int(selected.sum()), effective_mass=total,
                weighted_bce=float((losses[selected]*mass[selected]).sum()/total) if total else None)
        result[key] = dict(metrics_at_05=counts, classes=classes)
    return result

def binary_training_loss(logits, truth, focal=False):
    loss = nn.functional.binary_cross_entropy_with_logits(logits,truth,reduction='none')
    return loss*(1-torch.exp(-loss)).square() if focal else loss

def experiment(manifest, output, epochs=5, device='auto', pretrained=True, group_balance=False,
               backbone_name='mobilenet_v3_small', point_grid=False, balance=False, edge_input=None, image_size=224,
               fine_tune_spatial=False, balanced_selection=False, side_balance=False, standardize_features=False,
               nonlinear_head=False, focal_loss=False, surface_input=None, seed=42, zero_init_head=False):
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError('seed must be an integer in [0, 2**32)')
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists; choose a new directory')
    if type(epochs) is not int or epochs < 1:
        raise ValueError('epochs must be positive')
    if balanced_selection and not point_grid:
        raise ValueError('Balanced selection requires point-grid validation')
    if balance and not point_grid:
        raise ValueError('Class balance is an opt-in point-grid experiment only')
    if side_balance and not (point_grid and balance):
        raise ValueError('Side balance requires an opt-in balanced point-grid experiment')
    if standardize_features and (not point_grid or not edge_input or fine_tune_spatial or side_balance):
        raise ValueError('Feature scaling requires frozen point-grid edge features without side balance')
    if nonlinear_head and (not point_grid or not edge_input or fine_tune_spatial or side_balance or standardize_features):
        raise ValueError('Nonlinear head requires frozen unscaled point-grid edge features without side balance')
    if focal_loss and (not point_grid or not edge_input or fine_tune_spatial or side_balance or standardize_features):
        raise ValueError('Focal loss requires frozen unscaled point-grid edge features without side balance')
    if edge_input not in (None, 'context', 'views', 'tiles', 'tiles-max') or edge_input and not point_grid:
        raise ValueError('Edge input requires a point-grid context/views/tiles experiment')
    if image_size not in (224, 448) or image_size != 224 and not point_grid:
        raise ValueError('448 image_size is supported only by point-grid experiments')
    if fine_tune_spatial and (not point_grid or (edge_input or surface_input) not in ('context', 'tiles') or backbone_name != 'mobilenet_v3_small'):
        raise ValueError('Spatial fine-tuning requires MobileNet point-grid edge context or tiles')
    if surface_input is not None:
        if (surface_input not in ('context', 'tiles') or not point_grid or edge_input is not None
                or side_balance or standardize_features or nonlinear_head or focal_loss):
            raise ValueError('Surface input requires a separate point-grid context/tiles experiment')
        edge_input = surface_input
    if type(zero_init_head) is not bool or zero_init_head and (not surface_input or fine_tune_spatial):
        raise ValueError('Zero head initialization requires a frozen surface-only linear experiment')
    source_hash = hashlib.sha256(Path(manifest).read_bytes()).hexdigest()
    point_report = None
    if point_grid:
        from .point_dataset import point_rows
        rows, point_report = point_rows(manifest, grid=True)
        if not point_report['ready_for_experiment']:
            raise ValueError('Explicit train/val point classes are insufficient')
        missing, group_balance = [], True
    else:
        rows, missing = region_rows(manifest)
    counts = {s: {k: {str(v): sum(r['labels'][k] == v for r in rows if r['split'] == s)
                       for v in (0, 1, None)} for k in REGION_LABELS} for s in ('train', 'val')}
    supported = [k for k in REGION_LABELS if counts['train'][k]['0'] and counts['train'][k]['1']]
    if edge_input:
        supported = [k for k in supported if k == ('surface_defect' if surface_input else 'edge_defect')]
    if not supported or any(not counts['val'][k]['0'] or not counts['val'][k]['1'] for k in supported):
        raise ValueError('Explicit train/val region classes are insufficient')
    device = device_for(device)
    torch.manual_seed(seed)
    backbone, dimension = backbone_for(backbone_name, pretrained)
    if edge_input in ('views', 'tiles', 'tiles-max'):
        dimension *= 2
    backbone = backbone.to(device)
    started = time.perf_counter()
    if fine_tune_spatial:
        # Last inverted residual contains a spatial convolution; keep BatchNorm in eval mode.
        backbone[-2].requires_grad_(True)
        tail = backbone[-2:]
        with torch.no_grad():
            features = torch.cat([tile_prefix_maps(backbone[:-2], r, device, image_size).cpu()
                if edge_input == 'tiles' else backbone[:-2](side_tensor(r['image'], r['box'], True, image_size)
                    .unsqueeze(0).to(device)).cpu() for r in rows])
    else:
        with torch.inference_mode():
            features = torch.cat([patch_features(backbone, r, device, edge_input if edge_input in ('tiles', 'tiles-max') else edge_input == 'views', image_size).cpu() for r in rows])
    features = features.clone().to(device)
    labels = torch.tensor([[r['labels'][k] if r['labels'][k] is not None else -1 for k in REGION_LABELS]
                           for r in rows], dtype=torch.float32, device=device)
    indices = {s: torch.tensor([i for i, r in enumerate(rows) if r['split'] == s], device=device)
               for s in ('train', 'val')}
    active = torch.tensor([k in supported for k in REGION_LABELS], device=device)
    train_weights = (side_class_training_weights(rows, supported) if side_balance
                     else group_training_weights(rows, supported))
    scaler = None
    if standardize_features:
        scaler = fit_train_scaler(features, [sum(w) for w in train_weights])
        features = (features-scaler[0])/scaler[1]
    ratios = training_class_ratios(rows, train_weights, supported) if balance else [1.0]*len(REGION_LABELS)
    positive_weights = torch.tensor(ratios, dtype=torch.float32, device=device)
    weights = torch.tensor(train_weights, dtype=torch.float32, device=device)
    if point_grid:
        weights += torch.tensor(class_group_validation_weights(rows, supported) if balanced_selection else
            group_training_weights(rows, supported, 'val'), dtype=torch.float32, device=device)
    torch.manual_seed(seed)
    head = region_head(dimension,8 if nonlinear_head else 0).to(device)
    if zero_init_head:
        for parameter in head.parameters():
            nn.init.zeros_(parameter)
    optimizer = torch.optim.AdamW([{'params': head.parameters(), 'lr': .001},
        {'params': backbone[-2].parameters(), 'lr': .0001}] if fine_tune_spatial else head.parameters(), lr=.001)
    def selected_features(ix):
        if fine_tune_spatial and edge_input == 'tiles':
            return tile_tail_features(tail, features[ix])
        return tail(features[ix]).mean((2, 3)) if fine_tune_spatial else features[ix]
    best, history, selected_epoch = float('inf'), [], None
    for epoch in range(epochs):
        stats = {}
        for phase in ('train', 'val'):
            ix = indices[phase]
            with torch.set_grad_enabled(phase == 'train'):
                logits = head(selected_features(ix))
                mask = (labels[ix] >= 0) & active.unsqueeze(0)
                losses = binary_training_loss(logits[mask],labels[ix][mask],focal=focal_loss and phase=='train')
                effective = weights[ix]
                if phase == 'train' and balance:
                    effective = effective * torch.where(labels[ix] == 1, positive_weights.unsqueeze(0), 1.0)
                loss = ((losses * effective[mask]).sum() / effective[mask].sum()
                        if (phase == 'train' and group_balance) or point_grid else losses.mean())
                if not torch.isfinite(loss):
                    raise ValueError('Non-finite loss')
                if phase == 'train':
                    optimizer.zero_grad(); loss.backward(); optimizer.step()
            stats[phase] = loss.item()
            if point_grid and phase == 'val':
                stats['val_diagnostics'] = validation_diagnostics(logits, labels[ix], effective, supported)
        history.append(stats)
        if stats['val'] < best:
            best, selected_epoch = stats['val'], epoch + 1
            best_state = {k: v.detach().cpu().clone() for k, v in head.state_dict().items()}
            if fine_tune_spatial:
                best_tail = {k: v.detach().cpu().clone() for k, v in tail.state_dict().items()}
    head.load_state_dict(best_state)
    if fine_tune_spatial:
        tail.load_state_dict(best_tail)
    with torch.inference_mode():
        probabilities = head(selected_features(indices['val'])).sigmoid().cpu().tolist()
    metrics = {k: dict(tp=0, tn=0, fp=0, fn=0) for k in supported}
    predictions = []
    for row, probs in zip([r for r in rows if r['split'] == 'val'], probabilities):
        for k in supported:
            truth = row['labels'][k]
            if truth is not None:
                pred = int(probs[REGION_LABELS.index(k)] >= .5)
                metrics[k][('t' if truth == pred else 'f') + ('p' if pred else 'n')] += 1
        predictions.append({**row, 'probabilities': {k: probs[i] if k in supported else None
                                                   for i, k in enumerate(REGION_LABELS)}})
    manifest_hash = hashlib.sha256(Path(manifest).read_bytes()).hexdigest()
    if manifest_hash != source_hash:
        raise ValueError('Manifest changed during experiment')
    report = {'evaluation_kind': 'region_validation', 'final_performance_claim': False,
              'architecture': backbone_name + '_region_v1', 'backbone_name': backbone_name,
              'seed': 42, 'epochs': epochs,
              'fine_tune_spatial': fine_tune_spatial, 'balanced_selection': balanced_selection,
              'pretrained': pretrained, 'image_size': image_size, 'counts': counts, 'supported': supported,
              'selected_epoch': selected_epoch, 'best_validation_loss': best,
              'selection_metric': 'unweighted validation BCE', 'history': history,
              'group_balance': group_balance,
              'balance': balance, 'positive_weights': dict(zip(REGION_LABELS, ratios)),
              'training_weighting': 'equal group total per target' if group_balance else 'equal known patch labels',
              'group_class_counts': {s: {k: {str(v): len({r['group'] for r in rows
                  if r['split'] == s and r['labels'][k] == v}) for v in (0, 1)}
                  for k in supported} for s in ('train', 'val')},
              'metrics': metrics, 'predictions': predictions,
              'positive_faces_without_region_labels': missing, 'manifest_sha256': manifest_hash,
              'elapsed_seconds': time.perf_counter() - started, 'device': str(device),
              'requires_gemini': True, 'production_ready': False, 'actual_calls_saved': 0,
              'limitations': ['Explicit patches only; this is not a whole-card quality score.',
                             '3x3 boxes have no perspective correction.',
                             'Repeated patches of one card are not independent samples; test is not read.']}
    report['seed'] = seed
    report['head_initialization'] = 'zero' if zero_init_head else 'default'
    if point_grid:
        report.update(evaluation_kind='point_validation', architecture=backbone_name+'_point_grid_v1',
                      crop_policy='fixed_3x3', point_dataset=point_report,
                      selection_metric='equal group total per target validation BCE')
        if balanced_selection:
            report['selection_metric'] = 'equal class then physical-group validation BCE'
        if balance:
            report['training_weighting'] = 'physical-group base weights, then equal train class mass per target'
        if side_balance:
            report['side_balance'] = True
            report['training_weighting'] = 'equal train side-class mass, then equal physical groups within each cell'
        if edge_input and not surface_input:
            report['edge_input'] = edge_input
        if edge_input == 'views':
            report['architecture'] = backbone_name+'_point_edge_views_v1'
            report['crop_policy'] = 'full_3x3_plus_outer_quarter_cell_v1'
    if edge_input in ('tiles', 'tiles-max'):
        report['architecture'] = backbone_name+('_point_edge_tiles_max_v1' if edge_input == 'tiles-max' else '_point_edge_tiles_v1')
        report['crop_policy'] = ('full_3x3_plus_fixed_2x2_spatial_max_features_v1' if edge_input == 'tiles-max'
                                 else 'full_3x3_plus_fixed_2x2_max_features_v1')
    if surface_input:
        report['surface_input'] = surface_input
        if surface_input == 'tiles':
            report['architecture'] = backbone_name+'_point_surface_tiles_v1'
    if scaler is not None:
        report['feature_scaling'] = dict(fit='train_only_physical_group_weights',std_floor=.001,
            dimensions=dimension,training_rows=sum(sum(w)>0 for w in train_weights),
            folded_into_head=True,validation_used_for_scaler=False)
        best_state = fold_scaler(best_state,scaler[0].cpu(),scaler[1].cpu())
    if nonlinear_head:
        report['head_hidden'] = 8
    if focal_loss:
        report['training_objective'] = 'focal_gamma2_existing_class_group_weights'
    output.mkdir(parents=True, exist_ok=False)
    if point_grid:
        (output/'inputs.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    torch.save({'architecture': report['architecture'], 'backbone_name': backbone_name, 'labels': list(REGION_LABELS),
                'image_size': image_size, 'seed': seed,
                'fine_tune_spatial': fine_tune_spatial, 'balanced_selection': balanced_selection,
                'supported': supported, 'backbone': {k: v.cpu() for k, v in backbone.state_dict().items()},
                'head': best_state, 'manifest_sha256': manifest_hash,
                'development_groups': sorted({r['group'] for r in rows}),
                'development_images': sorted({r['image'] for r in rows}),
                'development_ids': sorted({r['card_id'] for r in rows}),
                'development_image_hashes': sorted({r['image_sha256'] for r in rows}),
                'group_balance': group_balance, 'balance': balance, 'positive_weights': report['positive_weights'],
                'edge_input': None if surface_input else edge_input, 'surface_input': surface_input, 'side_balance': side_balance,
                'feature_scaling': report.get('feature_scaling'),
                'head_hidden': 8 if nonlinear_head else 0,
                'focal_loss': focal_loss, 'head_initialization': report['head_initialization'],
                'status': 'experimental'}, output / 'model.pt')
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return report
