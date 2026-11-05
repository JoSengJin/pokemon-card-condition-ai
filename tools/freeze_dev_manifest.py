"""Adopt reviewed val batches into a new development manifest and freeze its A3 table. No inference or new truth."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from card_condition.data_coverage import coverage_report
from card_condition.regions import GLARE_AREAS, REGION_LABELS, REGION_TARGET_AREAS

KO = dict(centering_defect='센터링', corner_defect='모서리', edge_defect='엣지', surface_defect='표면', observation_limited='관찰제한')


def combine(base, base_sha, sources):
    """Base rows stay as adopted; source rows must be new val rows. A physical group may not span splits."""
    sha = hashlib.sha256(Path(base).read_bytes()).hexdigest()
    if sha != base_sha:
        raise ValueError(f'Base manifest changed: {sha}')
    rows, info, splits = [json.loads(l) for l in open(base, encoding='utf-8') if l.strip()], [], {}
    for source in sources:
        data = Path(source).read_bytes()
        new = [json.loads(l) for l in data.decode('utf-8').splitlines() if l.strip()]
        if any(r.get('split') != 'val' for r in new):
            raise ValueError(f'{source}: only val rows can be adopted from a review batch')
        info.append(dict(path=str(source), sha256=hashlib.sha256(data).hexdigest(), rows=len(new),
                         excluded=sum(bool(r.get('excluded')) for r in new)))
        rows += new
    ids = [r['id'] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate row id across base and batches')
    for r in rows:
        if splits.setdefault(r['group'], r.get('split')) != r.get('split'):
            raise ValueError(f"Physical group {r['group']} spans splits")
    return rows, dict(base=str(base), base_sha256=sha, sources=info)


def audit(rows):
    """Coordinate-source audit of typed points; errors would corrupt point evaluation, warnings are disclosed only."""
    errors, warnings = [], []
    for r in rows:
        if r.get('excluded') or not isinstance(r.get('side_annotations'), dict):
            continue
        for side, a in r['side_annotations'].items():
            if not a or not a.get('box'):
                continue
            l, t, rt, b = a['box']
            labels, regions, kinds = a.get('labels') or {}, a.get('region_labels') or {}, set()
            where = dict(id=r['id'], split=r.get('split'), side=side)
            for n, p in enumerate(a.get('defect_points', []), 1):
                kind, kinds = p['label'], kinds | {p['label']}
                if not (l <= p['x'] <= rt and t <= p['y'] <= b):
                    errors.append(dict(where, point=n, kind=kind, reason='point_outside_box'))
                    continue
                area = GLARE_AREAS[min(2, int(3*(p['y']-t)/(b-t)))*3 + min(2, int(3*(p['x']-l)/(rt-l)))]
                if area not in REGION_TARGET_AREAS[kind]:
                    errors.append(dict(where, point=n, kind=kind, area=area, reason='kind_not_allowed_in_area'))
                if labels.get(kind) != 1:
                    errors.append(dict(where, point=n, kind=kind, reason='face_label_not_positive'))
                if (regions.get(area) or {}).get(kind) == 0:
                    errors.append(dict(where, point=n, kind=kind, area=area, reason='conflicts_same_kind_normal_region'))
                if a.get('box_reviewed') is not True:
                    warnings.append(dict(where, point=n, kind=kind, reason='point_on_unreviewed_box'))
            for kind in REGION_LABELS:
                if labels.get(kind) == 1 and kind not in kinds:
                    warnings.append(dict(where, kind=kind, reason='positive_face_without_typed_point'))
    return errors, warnings


def table(report):
    lines = ['| 질문 | 면 | 양성 단위/실물 | 정상 단위/실물 | 미확인 | 충족 |', '|---|---|---:|---:|---:|---|']
    for c in report['cells']:
        if c['split'] == 'val':
            p, n = c['positive'], c['negative']
            lines.append(f"| {KO[c['label']]} | {'앞' if c['side'] == 'front' else '뒤'} | {p['units']}/{p['groups']} "
                         f"| {n['units']}/{n['groups']} | {c['unknown_units']} | {'예' if c['quantity_met'] else '아니오'} |")
    return '\n'.join(lines)


def freeze(base, base_sha, sources, output, decided_by):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    rows, provenance = combine(base, base_sha, sources)
    manifest = output / 'combined-reviewed.jsonl'
    with manifest.open('x', encoding='utf-8') as stream:
        stream.writelines(json.dumps(r, ensure_ascii=False) + '\n' for r in rows)
    report = coverage_report(manifest)
    errors, warnings = audit(rows)
    val = [c for c in report['cells'] if c['split'] == 'val']
    summary = dict(schema='development_manifest_adoption/v1', adopted_manifest=manifest.name,
                   adopted_sha256=report['manifest_sha256'], rows=len(rows), decided_by=decided_by, **provenance,
                   val_cells_met=sum(c['quantity_met'] for c in val), val_cells=len(val),
                   audit_errors=len(errors), audit_warnings=len(warnings), labels_modified=False,
                   training_calls=0, inference_calls=0, independent=False, d1_use=False,
                   # A3 is the val development table; train errors are disclosed but do not enter val denominators.
                   a3_frozen=not any(e['split'] == 'val' for e in errors) and all(c['quantity_met'] for c in val))
    for name, value in (('coverage.json', report), ('audit.json', dict(errors=errors, warnings=warnings)),
                        ('ADOPTION.json', summary)):
        with (output / name).open('x', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=1, allow_nan=False)
    with (output / 'FROZEN_TABLE.md').open('x', encoding='utf-8') as stream:
        stream.write(f"# 개발 평가(val) A3 충족표 — 동결\n\nmanifest SHA `{report['manifest_sha256']}`, 행 {len(rows)}, "
                     f"감사 오류 {len(errors)}·경고 {len(warnings)}. 기준: 양성·정상 각 20단위·5실물. "
                     "개발 평가용이며 독립 시험(D1)이 아니다.\n\n" + table(report) + '\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    parser.add_argument('--base-sha256', required=True)
    parser.add_argument('--source', action='append', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--decided-by', required=True)
    args = parser.parse_args()
    print(json.dumps(freeze(args.base, args.base_sha256, args.source, args.output, args.decided_by), ensure_ascii=False, indent=1))
