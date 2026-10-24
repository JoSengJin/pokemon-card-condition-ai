"""Per-evaluation provenance guards; no changes to human groups or truth."""
from pathlib import Path
from .point_probe import digest


def track_photos(records, hashes):
    for row in records:
        for side in ('front','back'):
            if row.get(side):
                path = str(Path(row[side]).resolve())
                if path not in hashes:
                    hashes[path] = digest(path)


def reject_copied_test_groups(records):
    owners = {}
    for row in records:
        for value in row['_image_hashes']:
            if owners.setdefault(value,row['group']) != row['group']:
                raise ValueError('Identical decoded image assigned to different physical groups in evaluation')


def unchanged_inputs(hashes):
    if any(digest(path) != value for path,value in hashes.items()):
        raise ValueError('Evaluation inputs changed; no report saved')


def development_sets(meta, group_key='development_groups'):
    keys = (group_key, 'development_ids', 'development_image_hashes')
    if not isinstance(meta, dict) or any(
            not isinstance(meta.get(key), list) or not meta[key]
            or any(type(value) is not str or not value.strip() for value in meta[key])
            for key in keys):
        raise ValueError('Missing or invalid checkpoint development provenance')
    if any(len(value) != 64 or any(c not in '0123456789abcdef' for c in value)
           for value in meta['development_image_hashes']):
        raise ValueError('Invalid checkpoint development provenance image hashes')
    return tuple(set(meta[key]) for key in keys)
