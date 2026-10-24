import hashlib
import math
import os
import tempfile
import time
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

from .data import CardDataset, LABELS, image_tensor, load_manifest, training_readiness


class ConditionModel(nn.Module):
    def __init__(self, pretrained=False):
        super().__init__()
        weights = MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
        self.features = mobilenet_v3_small(weights=weights).features
        self.features.requires_grad_(False)
        self.head = nn.Linear(576 * 2 + 2, len(LABELS))

    def forward(self, images, present):
        self.features.eval()  # Frozen backbone includes frozen BatchNorm statistics.
        with torch.no_grad():
            features = self.features(images.flatten(0, 1)).mean((2, 3)).reshape(images.shape[0], -1)
        return self.head(torch.cat((features, present), dim=1))


def device_for(name="auto"):
    if name == "auto":
        name = "mps" if torch.backends.mps.is_available() else "cpu"
    if name not in ("cpu", "mps") or (name == "mps" and not torch.backends.mps.is_available()):
        raise ValueError("Requested device is unavailable; use cpu or auto")
    return torch.device(name)


def checked_sigmoid(logits):
    # sigmoid maps +/-inf to plausible 1/0; reject numerical failure before conversion.
    if not torch.isfinite(logits).all().item():
        raise ValueError('Non-finite model logits; use Gemini fallback')
    return logits.sigmoid()


def train(manifest, output, epochs=5, batch_size=4, device="auto", pretrained=True, image_size=224):
    if image_size not in (224, 448):
        raise ValueError("image_size must be 224 or 448")
    if epochs < 1 or batch_size < 1:
        raise ValueError("epochs and batch_size must be positive")
    output = Path(output)
    if output.exists():
        raise ValueError("Output exists: choose a new model path")
    rows = load_manifest(manifest, splits={"train", "val"})
    training = [r for r in rows if r["split"] == "train"]
    validation = [r for r in rows if r["split"] == "val"]
    plan = training_readiness(rows)
    if not plan["ready_for_training"]:
        raise ValueError("; ".join(plan["issues"]))
    supported = plan["supported"]
    torch.manual_seed(42)
    device = device_for(device)
    model = ConditionModel(pretrained=pretrained).to(device)
    optimizer = torch.optim.AdamW(model.head.parameters(), lr=1e-3)
    active = torch.tensor([k in supported for k in LABELS], device=device)
    best, best_state, history = float("inf"), None, []
    for epoch in range(epochs):
        losses = {}
        for phase, subset in (("train", training), ("val", validation)):
            total, count = 0.0, 0
            model.train(phase == "train")
            for images, present, labels in DataLoader(CardDataset(subset, image_size), batch_size=batch_size,
                                                       shuffle=phase == "train", num_workers=0):
                images, present, labels = images.to(device), present.to(device), labels.to(device)
                mask = (labels >= 0) & active
                with torch.set_grad_enabled(phase == "train"):
                    logits = model(images, present)
                    loss = nn.functional.binary_cross_entropy_with_logits(logits[mask], labels[mask])
                    if not torch.isfinite(loss):
                        raise ValueError("Non-finite loss; checkpoint not saved")
                    if phase == "train":
                        optimizer.zero_grad()
                        loss.backward()
                        optimizer.step()
                total += loss.item() * mask.sum().item()
                count += mask.sum().item()
            losses[phase] = total / count
        history.append({"epoch": epoch + 1, **losses})
        if losses["val"] < best:
            best = losses["val"]
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    checkpoint = {"format": 1, "architecture": "mobilenet_v3_small_pair", "labels": list(LABELS),
                  "image_size": image_size, "supported": supported, "pretrained": pretrained, "state_dict": best_state,
                  "history": history, "manifest_sha256": hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
                  "training_image_hashes": sorted({h for r in rows if r["split"] != "test" for h in r["_image_hashes"]}),
                  "training_groups": sorted({r["group"] for r in rows if r["split"] != "test"}),
                  "status": "experimental", "torch_version": str(torch.__version__)}
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=output.parent, suffix=".tmp")
    os.close(fd)
    try:
        torch.save(checkpoint, temp)
        os.replace(temp, output)
    finally:
        Path(temp).unlink(missing_ok=True)
    return {"checkpoint": str(output), "supported": supported, "history": history,
            "device": str(device), "status": "experimental"}


class Analyzer:
    def __init__(self, checkpoint, device="auto"):
        self.device = device_for(device)
        self.meta = torch.load(checkpoint, map_location="cpu", weights_only=True)
        if (self.meta.get("format") != 1 or self.meta.get("labels") != list(LABELS)
                or self.meta.get("architecture") != "mobilenet_v3_small_pair"
                or not set(self.meta.get("supported", [])) <= set(LABELS)):
            raise ValueError("Unsupported checkpoint contract")
        self.image_size = self.meta.get("image_size", 224)
        if self.image_size not in (224, 448):
            raise ValueError("Unsupported image_size")
        self.model = ConditionModel().to(self.device)
        self.model.load_state_dict(self.meta["state_dict"], strict=True)
        self.model.eval()

    def analyze(self, front, back=None):
        started = time.perf_counter()
        if front is None and back is None:
            raise ValueError("At least one image is required")
        images = torch.stack([image_tensor(front, self.image_size), image_tensor(back, self.image_size)]).unsqueeze(0).to(self.device)
        present = torch.tensor([[front is not None, back is not None]], dtype=torch.float32, device=self.device)
        with torch.inference_mode():
            values = checked_sigmoid(self.model(images, present))[0].cpu().tolist()
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Invalid model output")
        probabilities = {k: v if k in self.meta["supported"] else None for k, v in zip(LABELS, values)}
        return {"schema_version": 1, "status": "experimental", "probabilities": probabilities,
                "requires_gemini": True, "reason": "model_not_validated_for_production",
                "elapsed_seconds": time.perf_counter() - started,
                "model_training_manifest": self.meta["manifest_sha256"]}


def evaluate(manifest, checkpoint, threshold=0.9, device="auto"):
    if not math.isfinite(threshold) or not 0.5 < threshold < 1:
        raise ValueError("Threshold must be between 0.5 and 1")
    rows = [r for r in load_manifest(manifest) if r["split"] == "test"]
    if not rows:
        raise ValueError("Held-out test data required")
    analyzer = Analyzer(checkpoint, device)
    if {r["group"] for r in rows} & set(analyzer.meta["training_groups"]):
        raise ValueError("Test group overlaps training/validation")
    if {h for r in rows for h in r["_image_hashes"]} & set(analyzer.meta["training_image_hashes"]):
        raise ValueError("Test images overlap training/validation")
    counts = {k: dict(tp=0, tn=0, fp=0, fn=0) for k in analyzer.meta["supported"]}
    candidates, misses, unlabelled_candidates, details = 0, 0, 0, []
    for row in rows:
        result = analyzer.analyze(row["front"], row["back"])
        p = result["probabilities"]
        for key, matrix in counts.items():
            truth = row["labels"][key]
            if truth is not None:
                prediction = int(p[key] >= 0.5)
                matrix[("t" if prediction == truth else "f") + ("p" if prediction else "n")] += 1
        # Hypothesis only: replace analysis for clear full pairs, never a production decision.
        candidate = (row["front"] is not None and row["back"] is not None
                     and all(v is not None for v in p.values()) and p["gradable"] >= threshold
                     and all(max(p[k], 1-p[k]) >= threshold for k in LABELS[1:]))
        candidates += int(candidate)
        if candidate:
            unlabelled_candidates += int(any(row["labels"][k] is None for k in LABELS))
            misses += int(row["labels"]["gradable"] == 0 or any(
                row["labels"][k] == 1 and p[k] < 0.5 for k in LABELS[1:]))
        details.append({"id": row["id"], "labels": row["labels"], **result, "hypothetical_local": bool(candidate)})
    for matrix in counts.values():
        positives, negatives = matrix["tp"] + matrix["fn"], matrix["tn"] + matrix["fp"]
        matrix["miss_rate"] = matrix["fn"] / positives if positives else None
        matrix["false_positive_rate"] = matrix["fp"] / negatives if negatives else None
    return {"evaluation_kind": "regression", "final_performance_claim": False, "n_test": len(rows), "metrics": counts, "threshold": threshold,
            "hypothetical_call_reduction": candidates / len(rows), "unsafe_candidates": misses,
            "candidates_with_unknown_labels": unlabelled_candidates,
            "actual_calls_saved": 0, "production_ready": False, "predictions": details}
