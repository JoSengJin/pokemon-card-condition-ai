"""Optional human annotations, tied to the selected source image."""
import copy
import math
from .data import LABELS

VISIBILITY_ISSUES = ("glare", "blur", "obstruction", "cropped", "low_resolution", "perspective", "shadow")
# shortcut: coarse 3x3 locations; use precise boxes only if these labels prove insufficient.
GLARE_AREAS = ("upper_left", "upper_center", "upper_right", "middle_left", "center",
               "middle_right", "lower_left", "lower_center", "lower_right")
REGION_LABELS = ("corner_defect", "edge_defect", "surface_defect")
REGION_TARGET_AREAS = {'corner_defect':('upper_left','upper_right','lower_left','lower_right'),
                       'edge_defect':tuple(area for area in GLARE_AREAS if area != 'center'),
                       'surface_defect':GLARE_AREAS}


def region_box(box, area):
    if (type(area) is not str or area not in GLARE_AREAS or not isinstance(box, (list, tuple))
            or len(box) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in box)
            or not (box[0] < box[2] and box[1] < box[3])):
        raise ValueError('Valid normalized card box and 3x3 area are required')
    left, top, right, bottom = box
    y, x = divmod(GLARE_AREAS.index(area), 3)
    width, height = (right-left)/3, (bottom-top)/3
    return [left+x*width, top+y*height, left+(x+1)*width, top+(y+1)*height]


def validate_annotations(value, row):
    if not isinstance(value, dict) or set(value) - {"front", "back"}:
        raise ValueError("면별 라벨 형식이 올바르지 않습니다.")
    for side, annotation in value.items():
        required = {"image", "box", "labels"}
        if (not isinstance(annotation, dict) or not required <= set(annotation)
                or set(annotation) - required - {"visibility_issues", "glare_areas", "region_labels", "region_reviews", "defect_points", "box_reviewed", "visibility_points"}):
            raise ValueError("면별 라벨에는 image, box, labels와 선택적 관찰 제한 정보만 허용됩니다.")
        if not row.get(side) or annotation["image"] != row[side]:
            raise ValueError("면별 라벨의 사진이 변경되었습니다. 다시 지정하세요.")
        labels = annotation["labels"]
        if not isinstance(labels, dict) or set(labels) != set(LABELS):
            raise ValueError("면별 라벨 항목이 올바르지 않습니다.")
        if any(v is not None and (type(v) is not int or v not in (0, 1)) for v in labels.values()):
            raise ValueError("면별 라벨은 0, 1, null만 허용됩니다.")
        issues = annotation.get("visibility_issues", [])
        if (not isinstance(issues, list)
                or any(type(issue) is not str or issue not in VISIBILITY_ISSUES for issue in issues)
                or len(issues) != len(set(issues))):
            raise ValueError("관찰 제한 사유가 올바르지 않습니다.")
        areas = annotation.get("glare_areas", [])
        if (not isinstance(areas, list)
                or any(type(area) is not str or area not in GLARE_AREAS for area in areas)
                or len(areas) != len(set(areas))
                or areas and ("glare" not in issues or annotation["box"] is None)):
            raise ValueError("빛 반사 위치는 카드 영역과 빛 반사 사유를 지정한 뒤 선택하세요.")
        box = annotation["box"]
        if box is not None:
            if (not isinstance(box, list) or len(box) != 4 or
                    any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in box) or
                    not (box[0] < box[2] and box[1] < box[3])):
                raise ValueError("카드 영역은 0~1 범위의 좌상단·우하단 좌표여야 합니다.")
        if (type(annotation.get('box_reviewed',False)) is not bool
                or annotation.get('box_reviewed',False) and box is None):
            raise ValueError('카드 영역 확인에는 유효한 영역과 확인 체크가 필요합니다.')
        validate_defect_points(annotation.get('defect_points', []), box)
        validate_visibility_points(annotation.get('visibility_points', []), box, issues)
        regions = annotation.get('region_labels', {})
        reviews = annotation.get('region_reviews', {})
        if (not isinstance(reviews, dict) or set(reviews) - set(GLARE_AREAS)
                or reviews and box is None):
            raise ValueError('구역 검토 완료 기록에는 카드 영역과 유효한 위치가 필요합니다.')
        for area, keys in reviews.items():
            if (not isinstance(keys, list) or not keys
                    or any(type(k) is not str or k not in REGION_LABELS or area not in REGION_TARGET_AREAS[k] for k in keys)
                    or len(keys) != len(set(keys))):
                raise ValueError('구역 검토 완료 항목이 올바르지 않습니다.')
        if (not isinstance(regions, dict) or set(regions) - set(GLARE_AREAS)
                or regions and box is None):
            raise ValueError('구역별 결함 라벨에는 카드 영역과 유효한 위치가 필요합니다.')
        for area, region_labels in regions.items():
            if (not isinstance(region_labels, dict) or set(region_labels) != set(REGION_LABELS)
                    or any(v is not None and (type(v) is not int or v not in (0, 1)) for v in region_labels.values())):
                raise ValueError('구역별 결함 라벨은 모서리·엣지·표면의 0, 1, null을 기록하세요.')
            if any(v is not None and area not in REGION_TARGET_AREAS[k] for k, v in region_labels.items()):
                raise ValueError('모서리는 네 귀퉁이, 엣지는 중앙을 제외한 구역에서만 평가하세요.')
            if any(v == 1 and labels[k] != 1 for k, v in region_labels.items()):
                raise ValueError('구역에서 결함을 관찰했다면 해당 면의 같은 결함도 관찰됨으로 확인하세요.')
    return copy.deepcopy(value)


def validate_defect_points(points, box):
    """Optional human evidence in EXIF-oriented source-image coordinates; not training targets."""
    if not isinstance(points, list) or points and box is None:
        raise ValueError('결함 지점은 카드 영역을 지정한 뒤 기록하세요.')
    seen = set()
    for point in points:
        if (not isinstance(point, dict) or not {'label', 'x', 'y'} <= set(point) or bool(set(point) - {'label', 'x', 'y', 'types'})
                or type(point['label']) is not str or point['label'] not in REGION_LABELS
                or any(type(point[k]) not in (int, float) or not math.isfinite(point[k]) for k in ('x', 'y'))
                or not box[0] <= point['x'] <= box[2] or not box[1] <= point['y'] <= box[3]):
            raise ValueError('결함 지점은 모서리·엣지·표면 종류와 카드 영역 안의 0~1 좌표여야 합니다.')
        types = point.get('types')
        if 'types' in point and (point['label'] != 'surface_defect' or not isinstance(types, list) or not types
                or any(type(t) is not str or t not in ('scratch', 'crease', 'stain') for t in types)
                or len(types) != len(set(types))):
            raise ValueError('결함 지점의 표면 종류가 올바르지 않습니다.')
        identity = (point['label'], point['x'], point['y'])
        if identity in seen:
            raise ValueError('같은 종류의 결함 지점이 중복되었습니다.')
        seen.add(identity)


def validate_visibility_points(points, box, issues):
    if not isinstance(points, list) or points and box is None:
        raise ValueError('관찰 제한 지점에는 카드 영역이 필요합니다.')
    seen = set()
    for point in points:
        if (not isinstance(point, dict) or set(point) != {'issue', 'x', 'y'}
                or type(point['issue']) is not str or point['issue'] not in issues
                or any(type(point[k]) not in (int, float) or not math.isfinite(point[k]) for k in ('x', 'y'))
                or not box[0] <= point['x'] <= box[2] or not box[1] <= point['y'] <= box[3]):
            raise ValueError('관찰 제한 지점의 종류·좌표를 확인하세요.')
        identity = (point['issue'], point['x'], point['y'])
        if identity in seen:
            raise ValueError('관찰 제한 지점이 중복되었습니다.')
        seen.add(identity)
