"""Per-evaluation provenance guards; no changes to human groups or truth."""
import hashlib
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from .point_probe import digest


def track_photos(records, hashes):
    """Record byte SHAs from the same bytes that must still decode to the loader's pixel identity."""
    for row in records:
        sides = [side for side in ('front','back') if row.get(side)]
        for side, expected in zip(sides, row['_image_hashes']):
            path = str(Path(row[side]).resolve())
            data = Path(path).read_bytes()
            with Image.open(BytesIO(data)) as image:
                image = ImageOps.exif_transpose(image).convert('RGB')
                pixels = hashlib.sha256(str(image.size).encode() + image.tobytes()).hexdigest()
            recorded = hashlib.sha256(data).hexdigest()
            if pixels != expected or hashes.setdefault(path, recorded) != recorded:
                raise ValueError('Evaluation photo changed while loading; no report saved')


def matched_model(analyzer, hashes, checkpoint):
    """The analyzer must have read the very checkpoint whose SHA the report will record."""
    if analyzer.model_sha256 != hashes[str(Path(checkpoint).resolve())]:
        raise ValueError('Analyzer loaded a different checkpoint than the recorded one; no report saved')


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
