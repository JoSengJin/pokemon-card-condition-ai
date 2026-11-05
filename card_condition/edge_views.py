"""Experimental full patch plus outer-edge views; no labels are changed."""
from itertools import islice

import torch

from .side_experiment import view_tensors


def edge_view_boxes(row):
    left, top, right, bottom = row['box']
    card = row['card_box']
    # Fixed before validation: a quarter of a 3x3 cell per outer boundary.
    width, height = (card[2]-card[0])/12, (card[3]-card[1])/12
    area, boxes = row['area'], []
    if area.startswith('upper_'):
        boxes.append([left, top, right, min(bottom, top+height)])
    if area.startswith('lower_'):
        boxes.append([left, max(top, bottom-height), right, bottom])
    if area.endswith('_left'):
        boxes.append([left, top, min(right, left+width), bottom])
    if area.endswith('_right'):
        boxes.append([max(left, right-width), top, right, bottom])
    return boxes


def fixed_tile_boxes(row):
    left, top, right, bottom = row['box']
    mid_x, mid_y = (left+right)/2, (top+bottom)/2
    return [[left, top, mid_x, mid_y], [mid_x, top, right, mid_y],
            [left, mid_y, mid_x, bottom], [mid_x, mid_y, right, bottom]]


def patch_features(backbone, row, device, edge_views=False, image_size=224, *, prepared_views=None):
    boxes = (fixed_tile_boxes(row) if edge_views in ('tiles', 'tiles-max')
             else edge_view_boxes(row) if edge_views else [])
    tensors = (view_tensors(row['image'], [row['box'], *boxes], image_size)
               if prepared_views is None else iter(prepared_views))
    full = backbone(next(tensors).unsqueeze(0).to(device)).mean((2, 3))
    if not edge_views:
        return full
    # Center rows have no edge labels but retain prediction/input identity.
    maps = [backbone(tensor.unsqueeze(0).to(device)) for tensor in tensors]
    outer = torch.cat([m.amax((2, 3)) if edge_views == 'tiles-max' else m.mean((2, 3))
                       for m in maps]) if maps else full
    # One bag-level target; no tile is given the parent defect label.
    outer = outer.amax(0, keepdim=True) if edge_views in ('tiles', 'tiles-max') else outer.mean(0, keepdim=True)
    return torch.cat((full, outer), dim=1)


def tile_prefix_maps(prefix, row, device, image_size=224):
    """Cache identical fixed views before the trainable spatial block."""
    boxes = [row['box']] + fixed_tile_boxes(row)
    return torch.stack([prefix(tensor.unsqueeze(0).to(device))[0]
        for tensor in view_tensors(row['image'], boxes, image_size)]).unsqueeze(0)


def tile_tail_features(tail, maps):
    """One bag target: full view plus channelwise max of four tile features."""
    batch, views = maps.shape[:2]
    pooled = tail(maps.flatten(0, 1)).mean((2, 3)).reshape(batch, views, -1)
    return torch.cat((pooled[:, 0], pooled[:, 1:].amax(1)), dim=1)


def batched_patch_features(backbone, row, device, edge_views=False, image_size=224, *, prepared_views=None):
    """Same fixed views/pooling as patch_features; opt-in inference-only batching."""
    if not torch.is_inference_mode_enabled() or any(module.training for module in backbone.modules()):
        raise ValueError('Batched views require inference mode and an eval backbone')
    boxes = (fixed_tile_boxes(row) if edge_views in ('tiles', 'tiles-max')
             else edge_view_boxes(row) if edge_views else [])
    views = (view_tensors(row['image'], [row['box'], *boxes], image_size)
             if prepared_views is None else prepared_views)
    tensors = torch.stack(list(views)).to(device)
    maps = backbone(tensors)
    full = maps[:1].mean((2, 3))
    if not edge_views:
        return full
    outer = (maps[1:].amax((2, 3)) if edge_views == 'tiles-max' else maps[1:].mean((2, 3))) if boxes else full
    outer = outer.amax(0, keepdim=True) if edge_views in ('tiles', 'tiles-max') else outer.mean(0, keepdim=True)
    return torch.cat((full, outer), dim=1)


def region_features(backbone, rows, device, edge_views=False, image_size=224, batch_views=False):
    """Share context decoding; other policies retain their original per-region input path."""
    if not rows:
        return
    if not torch.is_inference_mode_enabled() or any(module.training for module in backbone.modules()):
        raise ValueError('Shared photo views require inference mode and an eval backbone')
    if len({(r['image'],tuple(r['card_box'])) for r in rows})!=1:
        raise ValueError('Shared photo views require one image and card box')
    # Tile/view timing did not meet the frozen gate; retain its original decode path.
    if edge_views:
        features_for=batched_patch_features if batch_views else patch_features
        for row in rows:
            yield features_for(backbone,row,device,edge_views,image_size)
        return
    boxes=[[r['box'], *(fixed_tile_boxes(r) if edge_views in ('tiles','tiles-max')
             else edge_view_boxes(r) if edge_views else [])] for r in rows]
    stream=view_tensors(rows[0]['image'],[box for group in boxes for box in group],image_size)
    features_for=batched_patch_features if batch_views else patch_features
    for row,group in zip(rows,boxes):
        # Finish preprocessing here, before the feature call, and retain no views between regions.
        views=list(islice(stream,len(group)))
        features=features_for(backbone,row,device,edge_views,image_size,prepared_views=views)
        del views
        yield features
