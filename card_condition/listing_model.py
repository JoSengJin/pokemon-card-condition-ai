"""Standalone photo-bundle inference; no dataset, truth labels or training."""
import copy
import hashlib
from pathlib import Path

from .data import LABELS
from .recall_review import review_labels
from .listing_readiness import listing_readiness
from .listing_observation import observation_evidence
from .release import check_loaded, read_release
from .visibility_model import VisibilityAnalyzer
from .region_model import RegionAnalyzer
from .regions import GLARE_AREAS, REGION_TARGET_AREAS, validate_annotations


def photo_request(request):
    if (not isinstance(request, dict) or set(request) - {'id', 'front', 'back'}
            or type(request.get('id')) is not str or not request['id'].strip()):
        raise ValueError('Request requires a nonempty id and optional front/back inputs only')
    request = copy.deepcopy(request)
    row = dict(id=request['id'], group=request['id'], front=None, back=None, side_annotations={})
    unreviewed = []
    for side in ('front', 'back'):
        face = request.get(side)
        if face is None:
            continue
        if (not isinstance(face, dict) or 'image' not in face
                or set(face) - {'image', 'box', 'visibility_issues', 'glare_areas'}
                or type(face['image']) is not str or not Path(face['image']).is_absolute()):
            raise ValueError('Each face requires an absolute image path and optional box/observation limits')
        row[side] = face['image']
        annotation = dict(image=face['image'], box=face.get('box'),
                          labels={key: None for key in LABELS},
                          visibility_issues=face.get('visibility_issues', []),
                          glare_areas=face.get('glare_areas', []))
        row['side_annotations'][side] = annotation
        if 'visibility_issues' not in face:
            unreviewed.append(side)
    validate_annotations(row['side_annotations'], row)
    return row, unreviewed


class ListingAnalyzer:
    def __init__(self, checkpoint=None, device='auto', *, observation_checkpoint=None, recall_checkpoint=None,
                 release=None):
        self.release = None
        if release is not None:
            if (checkpoint, observation_checkpoint, recall_checkpoint) != (None, None, None):
                raise ValueError('Use either a release manifest or direct checkpoints, not both')
            self.release, files = read_release(release)
            checkpoint = files['region']
            observation_checkpoint, recall_checkpoint = files.get('observation'), files.get('recall')
        self.region = RegionAnalyzer(checkpoint, device)
        self.recall = RegionAnalyzer(recall_checkpoint, device) if recall_checkpoint is not None else None
        if self.recall is not None and set(self.recall.meta["supported"]) != set(self.region.meta["supported"]):
            raise ValueError("Recall checkpoint must support the same defect labels")
        self.observation = (VisibilityAnalyzer(observation_checkpoint, device)
                            if observation_checkpoint is not None else None)
        if self.release is not None:
            check_loaded(self.release, dict(region=self.region.model_sha256,
                observation=getattr(self.observation, 'model_sha256', None),
                recall=getattr(self.recall, 'model_sha256', None)))

    def analyze(self, request, *, batch_views=False):
        if type(batch_views) is not bool:
            raise ValueError('batch_views must be boolean')
        row, unreviewed = photo_request(request)
        images = {row[side] for side in ('front', 'back') if row[side]}
        before = {image: hashlib.sha256(Path(image).read_bytes()).hexdigest() for image in images}
        predictions, review_candidates = [], []
        supported = self.region.meta['supported']
        for side, annotation in row['side_annotations'].items():
            if annotation['box'] is None or side in unreviewed:
                continue
            issues, glare = annotation['visibility_issues'], annotation['glare_areas']
            areas=[area for area in GLARE_AREAS
                if any(area in REGION_TARGET_AREAS[key] for key in supported)
                and not (set(issues)-{'glare'} or 'glare' in issues and (not glare or area in glare))]
            results=self.region.analyze_regions(row[side],annotation['box'],areas,batch_views=batch_views)
            extras=(self.recall.analyze_regions(row[side],annotation['box'],areas,batch_views=batch_views)
                    if self.recall is not None else [None]*len(areas))
            for area,result,extra in zip(areas,results,extras,strict=True):
                if extra is not None:
                    review_candidates.extend(dict(side=side, area=area, box=result['box'], **item)
                        for item in review_labels(result['probabilities'], extra['probabilities']))
                predictions.append(dict(card_id=row['id'], group=row['group'], side=side,
                    image=row[side], card_box=annotation['box'], area=area,
                    box=result['box'], probabilities=result['probabilities']))
        observation = None
        if self.observation is not None:
            evidence_row = copy.deepcopy(row)
            for side in unreviewed:
                evidence_row['side_annotations'][side].pop('visibility_issues', None)
                evidence_row['side_annotations'][side].pop('glare_areas', None)
            observation = observation_evidence([evidence_row], None, str(self.region.device),
                                               analyzer=self.observation)
        if any(hashlib.sha256(Path(image).read_bytes()).hexdigest() != value
               for image, value in before.items()):
            raise ValueError('Photo inputs changed during inference; discard result')
        readiness = listing_readiness([row], predictions, supported, unreviewed_sides=unreviewed)
        report = dict(id=row['id'], model_sha256=self.region.model_sha256,
            architecture=self.region.meta['architecture'], image_size=self.region.image_size,
            device=str(self.region.device), batched_views=batch_views,
            input_photo_sha256=before, observation_unreviewed_sides=unreviewed,
            inferred_regions=len(predictions), predictions=predictions,
            listing_readiness=readiness, training_performed=False,
            ground_truth_used_for_region_selection=False, same_object_verified=False,
            requires_gemini=True, production_ready=False, actual_calls_saved=0,
            limitations=['Human card boxes and observation limits are required; no automatic glare detection.',
                'Omitted observation review is unknown; an explicit empty list is a caller assertion, not model clearance.',
                'Fixed exploratory thresholds are uncalibrated; no overall grade, authenticity or purchase decision.',
                'No independent accuracy or production Gemini bypass is established.'])
        if self.recall is not None:
            report['recall_review'] = dict(model_sha256=self.recall.model_sha256, threshold=.5,
                candidates=review_candidates, policy='either_model_suspicious',
                verdict='review_only', automatic_rejection=False)
        if observation is not None:
            report['observation_evidence'] = observation
        if self.release is not None:
            report['release'] = copy.deepcopy(self.release)
        return report
