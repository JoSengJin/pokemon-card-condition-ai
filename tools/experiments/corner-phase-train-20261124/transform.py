"""Training-view expansion for the corner head: each zone is duplicated once per input view (pure, torch only).

Duplicating a zone with identical features leaves every term of the card-ranking objective unchanged:
guarded_masses divides by the per-group count, so the duplicates split their group's mass and the normalized
masses sum back to the original; photo_pairs keys by image, so a photo's pos x neg mean over duplicated
rows equals the original mean; card_scores subtracts log(count) from the logsumexp, so log 2 cancels.
No term is keyed by row id, so nothing else needs adjusting. Views of a zone differ only in features.
"""
import torch


def expand_rows(rows, views):
    """View-major copies of rows; id gets an '@dx,dy' suffix, every other field (target/group/image/...) is kept."""
    return [dict(r, id=f"{r['id']}@{dx},{dy}") for dx, dy in views for r in rows]


def stack_views(views, idx, dtype):
    """Rows idx of each per-view array stacked view-major (matches expand_rows); allocated once in dtype."""
    out = torch.empty((len(views)*len(idx),) + tuple(views[0].shape[1:]), dtype=dtype)
    for v, x in enumerate(views):
        out[v*len(idx):(v + 1)*len(idx)] = torch.as_tensor(x[idx])
    return out
