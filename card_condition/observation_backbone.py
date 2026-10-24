"""Optional pinned DINOv2 experiment; the default model remains unchanged."""
import torch
from torch import nn

DINOV2_REVISION = '7764ea0f912e53c92e82eb78a2a1631e92725fc8'
BACKBONES = ('mobilenet_v3_small', 'dinov2_vits14')


class DinoFeatures(nn.Module):
    def __init__(self, pretrained=False):
        super().__init__()
        self.model = torch.hub.load('facebookresearch/dinov2:'+DINOV2_REVISION,
            'dinov2_vits14', pretrained=pretrained, trust_repo=True, skip_validation=True)

    def forward(self, image):
        # Official CLS descriptor; singleton map reuses the existing global pooling path.
        return self.model(image).unsqueeze(-1).unsqueeze(-1)


def dino_backbone(pretrained=False):
    return DinoFeatures(pretrained).requires_grad_(False).eval(), 384
