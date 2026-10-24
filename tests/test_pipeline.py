import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image
import torch

from card_condition.data import LABELS, image_tensor, load_manifest, prepare
from card_condition.model import Analyzer, ConditionModel, evaluate, train


def fixture(root):
    rows = []
    for i, split in enumerate(("train", "train", "val", "val", "test", "test")):
        for side, color in (("front", (40+i*20, 30, 60)), ("back", (40+i*20, 90, 80))):
            Image.new("RGB", (90, 130), color).save(root / f"{i}-{side}.png")
        rows.append({"id": str(i), "group": str(i), "split": split,
                     "front": f"{i}-front.png", "back": f"{i}-back.png",
                     "labels": {k: i % 2 for k in LABELS}})
    manifest = root / "manifest.jsonl"
    manifest.write_text("\n".join(json.dumps(r) for r in rows))
    return manifest, rows


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manifest, self.rows = fixture(self.root)
        torch.set_num_threads(1)

    def tearDown(self):
        self.temp.cleanup()

    def write(self):
        self.manifest.write_text("\n".join(json.dumps(r) for r in self.rows))

    def test_leakage_and_invalid_label(self):
        self.rows[2]["group"] = "0"
        self.write()
        with self.assertRaisesRegex(ValueError, "group"):
            load_manifest(self.manifest)
        self.rows[2]["group"] = "2"
        self.rows[2]["front"] = "0-front.png"
        self.write()
        with self.assertRaisesRegex(ValueError, "across splits"):
            load_manifest(self.manifest)
        self.rows[2]["front"] = "2-front.png"
        self.rows[2]["labels"]["gradable"] = "yes"
        self.write()
        with self.assertRaisesRegex(ValueError, "Labels"):
            load_manifest(self.manifest)

    def test_missing_and_duplicate_sides(self):
        self.rows[1]["back"] = None
        self.write()
        with self.assertRaisesRegex(ValueError, "two distinct"):
            load_manifest(self.manifest)
        self.rows[1]["labels"]["gradable"] = 0
        self.write()
        self.assertEqual(6, len(load_manifest(self.manifest)))
        self.assertEqual((3, 224, 224), tuple(image_tensor(None).shape))
        self.rows[1]["labels"]["gradable"] = 1
        self.rows[1]["back"] = self.rows[1]["front"]
        self.write()
        with self.assertRaisesRegex(ValueError, "two distinct"):
            load_manifest(self.manifest)

    def test_train_evaluate_predict_and_no_overwrite(self):
        output = self.root / "model.pt"
        report = train(self.manifest, output, epochs=1, device="cpu", pretrained=False)
        self.assertEqual(list(LABELS), report["supported"])
        prediction = Analyzer(output, "cpu").analyze(self.root / "4-front.png", self.root / "4-back.png")
        self.assertTrue(prediction["requires_gemini"])
        self.assertTrue(all(0 <= p <= 1 for p in prediction["probabilities"].values()))
        result = evaluate(self.manifest, output, device="cpu")
        self.assertEqual(2, result["n_test"])
        self.assertEqual(0, result["actual_calls_saved"])
        self.assertFalse(result["production_ready"])
        for matrix in result["metrics"].values():
            self.assertEqual(2, sum(matrix[k] for k in ("tp", "tn", "fp", "fn")))
        checkpoint = torch.load(output, weights_only=True)
        checkpoint["state_dict"]["head.weight"].zero_()
        checkpoint["state_dict"]["head.bias"] = torch.tensor([5., -5., -5., -5., -5.])
        torch.save(checkpoint, output)
        unsafe = evaluate(self.manifest, output, device="cpu")
        self.assertEqual(1, unsafe["hypothetical_call_reduction"])
        self.assertEqual(2, unsafe["unsafe_candidates"])
        self.assertEqual(1, unsafe["metrics"]["edge_defect"]["fn"])
        self.assertTrue(all(p["requires_gemini"] for p in unsafe["predictions"]))
        with self.assertRaisesRegex(ValueError, "exists"):
            train(self.manifest, output, pretrained=False)
        # A different manifest must not bypass pixel leakage protection.
        self.rows = [dict(self.rows[0], id="external", group="external", split="test")]
        self.write()
        with self.assertRaisesRegex(ValueError, "images overlap"):
            evaluate(self.manifest, output, device="cpu")

    def test_unknown_heads_never_report_as_trained(self):
        for row in self.rows:
            for key in LABELS[1:]:
                row["labels"][key] = None
        self.write()
        output = self.root / "quality.pt"
        train(self.manifest, output, epochs=1, device="cpu", pretrained=False)
        result = Analyzer(output, "cpu").analyze(self.root / "4-front.png")
        self.assertTrue(all(result["probabilities"][k] is None for k in LABELS[1:]))
        self.assertEqual(0, evaluate(self.manifest, output, device="cpu")["hypothetical_call_reduction"])

    def test_prepare_never_invents_labels(self):
        output = self.root / "review.jsonl"
        result = prepare(self.root, output)
        self.assertEqual(12, result["images"])
        self.assertFalse(result["ready_for_training"])
        row = json.loads(output.read_text())
        self.assertIsNone(row["front"])
        self.assertTrue(all(v is None for v in row["labels"].values()))
        with self.assertRaises(FileExistsError):
            prepare(self.root, output)

    def test_backbone_frozen(self):
        model = ConditionModel()
        model.train()
        before = {k: v.clone() for k, v in model.features.state_dict().items()}
        output = model(torch.zeros(1, 2, 3, 224, 224), torch.ones(1, 2))
        output.sum().backward()
        self.assertTrue(all(torch.equal(v, before[k]) for k, v in model.features.state_dict().items()))
        self.assertIsNotNone(model.head.weight.grad)
        self.assertTrue(all(p.grad is None for p in model.features.parameters()))


if __name__ == "__main__":
    unittest.main()
