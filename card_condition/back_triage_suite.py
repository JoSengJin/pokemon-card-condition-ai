"""One call for the supported back-face suggestions (edge, corner, surface, observation limit). Front photos and centering are reported as unsupported, never as normal."""
from .back_edge_triage import BackEdgeTriage
from .back_obs_limit import BackObservationLimit
from .back_zone_triage import BackZoneTriage

UNSUPPORTED = dict(centering='unsupported_human_review', front_face='unsupported_human_review')


class BackTriageSuite:
    def __init__(self, heads, body, device='cpu'):
        """heads: dict(edge, corner, surface, observation_limit) -> head file path."""
        self.parts = dict(edge=BackEdgeTriage(heads['edge'], body, device), corner=BackZoneTriage('corner', heads['corner'], body, device),
                          surface=BackZoneTriage('surface', heads['surface'], body, device), observation_limit=BackObservationLimit(heads['observation_limit'], body, device))

    def analyze(self, request):
        """Front or unconfirmed-box requests are held per part; supported parts never return a defect/normal verdict."""
        results = {name: part.analyze(request) for name, part in self.parts.items()}
        return dict(id=request.get('id'), results=results, unsupported=dict(UNSUPPORTED), complete=False,
                    model_sha256={name: r['model_sha256'] for name, r in results.items()})
