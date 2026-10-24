"""Opt-in local research review signal; never a production defect verdict."""
from pathlib import Path
import torch
from .edge_views import edge_view_boxes, patch_features
from .side_experiment import view_tensors
from .regions import region_box
from .observation_backbone import DINOV2_REVISION


def review_route(baseline, candidate):
    if not all(isinstance(v,(int,float)) and 0 <= v <= 1 for v in (baseline,candidate)):
        raise ValueError('Expected finite probability scores')
    return dict(baseline_score=baseline,candidate_score=candidate,
                additional_review=baseline < .5 <= candidate,
                flagged_for_review=max(baseline,candidate)>=.5,
                production_ready=False,human_review_required=True)


class HybridEdgeReview:
    def __init__(self, checkpoint, dino_repository, device='cpu'):
        self.device=device
        self.meta=torch.load(checkpoint,map_location='cpu',weights_only=True)
        if (self.meta.get('architecture')!='edge_hybrid_review_v1'
                or self.meta.get('dino_revision')!=DINOV2_REVISION
                or self.meta.get('training_side') not in ('front','back')
                or self.meta.get('policy')!='full_and_outer_mean__dino_patch_max'
                or self.meta['coef'].shape!=(1920,) or not torch.isfinite(self.meta['coef']).all()
                or self.meta['bias'].ndim!=0 or not torch.isfinite(self.meta['bias'])):
            raise ValueError('Unsupported hybrid review checkpoint')
        # Use the pinned, already downloaded local source; prediction never fetches code or weights.
        repo=Path(dino_repository)
        if repo.name!='facebookresearch_dinov2_'+DINOV2_REVISION or not (repo/'hubconf.py').is_file():
            raise ValueError('Pinned local DINOv2 source cache required')
        from .side_model import backbone_for
        self.mobile,_=backbone_for('mobilenet_v3_small');self.mobile.load_state_dict(self.meta['mobile']);self.mobile.to(device).eval()
        self.dino=torch.hub.load(str(repo),'dinov2_vits14',source='local',pretrained=False).requires_grad_(False).eval().to(device)
        self.dino.load_state_dict(self.meta['dino'])

    def analyze(self, image, card_box, area, side):
        if side!=self.meta['training_side']:
            raise ValueError('Choose the checkpoint matching the image side')
        if area=='center':raise ValueError('Center is not an edge region')
        row=dict(image=image,card_box=card_box,box=region_box(card_box,area),area=area)
        with torch.inference_mode():
            mobile=patch_features(self.mobile,row,self.device,True,224)[0].cpu()
            tensors=torch.stack(list(view_tensors(image,[row['box'],*edge_view_boxes(row)],224))).to(self.device)
            pooled=self.dino.forward_features(tensors)['x_norm_patchtokens'].amax(1)
            dino=torch.cat((pooled[0],pooled[1:].mean(0))).cpu()
            features=torch.cat((mobile,dino))
            baseline=float((mobile@self.meta['baseline_coef']+self.meta['baseline_bias']).sigmoid())
            candidate=float((features@self.meta['coef']+self.meta['bias']).sigmoid())
        return review_route(baseline,candidate)
