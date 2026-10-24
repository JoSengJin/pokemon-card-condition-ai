import hashlib
import json
from pathlib import Path

from PIL import Image, ImageOps
import torch
from torch.utils.data import Dataset
from torchvision.transforms.functional import normalize, to_tensor

LABELS = ("gradable", "centering_defect", "corner_defect", "edge_defect", "surface_defect")


def image_tensor(path, image_size=224):
    if image_size not in (224, 448):
        raise ValueError("image_size must be 224 or 448")
    if path is None:
        return torch.zeros(3, image_size, image_size)
    with Image.open(path) as image:
        # Keep every edge; ImageNet's default center crop can remove card defects.
        image = ImageOps.pad(ImageOps.exif_transpose(image).convert("RGB"), (image_size, image_size),
                             method=Image.Resampling.BILINEAR, color=(128, 128, 128))
        return normalize(to_tensor(image), [0.485, 0.456, 0.406], [0.229, 0.224, 0.225])


def load_manifest(path, splits=None, require_gradable=True):
    path = Path(path).resolve()
    records, ids, groups, hashes = [], set(), {}, {}
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"Line {line_number}: expected object")
        # Excluded splits are never opened, decoded, or used for label checks.
        if splits is not None and row.get("split") not in splits:
            continue
        for field in ("id", "group", "split"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"Line {line_number}: missing {field}")
        split = row["split"]
        if split not in ("train", "val", "test") or row["id"] in ids:
            raise ValueError("Invalid split or duplicate id")
        ids.add(row["id"])
        if groups.setdefault(row["group"], split) != split:
            raise ValueError("Same physical-card group appears across splits")
        labels = row.get("labels")
        if not isinstance(labels, dict) or set(labels) != set(LABELS):
            raise ValueError(f"labels must contain exactly {LABELS}")
        if any(v is not None and (type(v) is not int or v not in (0, 1)) for v in labels.values()):
            raise ValueError("Labels must be 0, 1 or null")
        if require_gradable and labels["gradable"] is None:
            raise ValueError("Human gradable label is required")
        side_hashes = []
        for side in ("front", "back"):
            value = row.get(side)
            if value is None:
                row[side] = None
                continue
            if not isinstance(value, str) or not value:
                raise ValueError(f"Invalid {side} path")
            image_path = (path.parent / value).resolve()
            with Image.open(image_path) as image:
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.load()
                digest = hashlib.sha256(str(image.size).encode() + image.tobytes()).hexdigest()
            if hashes.setdefault(digest, split) != split:
                raise ValueError("Identical decoded image appears across splits")
            row[side] = str(image_path)
            side_hashes.append(digest)
        if not side_hashes:
            raise ValueError("At least one image is required")
        if labels["gradable"] == 1 and (len(side_hashes) != 2 or len(set(side_hashes)) != 2):
            raise ValueError("Gradable requires two distinct front/back images")
        row["_image_hashes"] = side_hashes
        records.append(row)
    if not records:
        raise ValueError("Manifest is empty")
    return records


class CardDataset(Dataset):
    def __init__(self, records, image_size=224):
        self.records = records
        self.image_size = image_size

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        row = self.records[index]
        images = torch.stack([image_tensor(row[side], self.image_size) for side in ("front", "back")])
        present = torch.tensor([row[side] is not None for side in ("front", "back")], dtype=torch.float32)
        labels = torch.tensor([row["labels"][k] if row["labels"][k] is not None else -1
                               for k in LABELS], dtype=torch.float32)
        return images, present, labels


def prepare(folder, output):
    """Create an unlabelled inventory; filenames never establish sides or truth."""
    folder, output = Path(folder).resolve(), Path(output)
    if not folder.is_dir():
        raise ValueError("Image directory does not exist")
    groups = {}
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            with Image.open(path) as image:
                image.load()
                size = list(image.size)
            group = str(path.parent.relative_to(folder))
            groups.setdefault(group, []).append({"path": str(path), "size": size})
    if not groups:
        raise ValueError("No supported images found")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        for group, images in groups.items():
            stream.write(json.dumps({"id": group, "group": group, "split": None,
                                     "front": None, "back": None, "images": images,
                                     "labels": {k: None for k in LABELS}}, ensure_ascii=False) + "\n")
    return {"groups": len(groups), "images": sum(map(len, groups.values())),
            "output": str(output), "ready_for_training": False}


def training_readiness(rows):
    """Same class-balance gate used by the reviewer and training entry point."""
    counts = {split: {key: {str(value): sum(r["labels"][key] == value for r in rows
                                         if r["split"] == split) for value in (0, 1, None)}
                      for key in LABELS} for split in ("train", "val", "test")}
    supported = [k for k in LABELS if counts["train"][k]["0"] and counts["train"][k]["1"]]
    issues = []
    if "gradable" not in supported:
        issues.append("train에는 평가 가능/불가 정답이 모두 필요합니다.")
    for key in supported:
        if not counts["val"][key]["0"] or not counts["val"][key]["1"]:
            issues.append(f"val의 {key}: 0과 1 정답이 모두 필요합니다.")
    if not any(r["split"] == "val" for r in rows):
        issues.append("독립 val 데이터가 필요합니다.")
    return {"ready_for_training": not issues, "issues": issues, "supported": supported,
            "counts": counts, "has_test": any(r["split"] == "test" for r in rows),
            "note": "클래스 존재 확인은 최소 실행 조건이며 데이터 충분성/성능 보장이 아닙니다."}
