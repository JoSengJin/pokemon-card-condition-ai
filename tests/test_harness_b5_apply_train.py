"""B5-7: 학습 적용기. VERIFIED 학습 작업 → 하네스가 계약 입력(SHA 확인한 사본)과 Silver 장부로 manifest v2를 만들어 registry에 등록(멱등).

executor가 out/에 쓴 manifest는 믿지 않는다. 부모는 계약 입력 경로 parents/<모델 ID>/... 하나로만 선언하고, 그 입력 SHA가 그 모델의 가중치
SHA와 같아야 한다. 등록 모델의 가중치와 같은 입력을 parents/ 밖에 두면 거절(선언하지 않은 부모). 승격은 하지 않는다.
합성 시험(작업 폴더를 직접 만든다)이며 실제 학습·모델 성능 근거가 아니다.
"""
import hashlib
import json
import os
import signal
import subprocess
import sys
import unittest

from harness import apply_train, cas, champion, contract as ct, eligibility, opstate, registry, silver_gate, withdrawal
from harness.jsonio import write_json
from tests.test_harness_champion_support import REPO, add_model, make_root
from tests.test_harness_withdrawal_support import make_batch

KILL = r'''
import os, signal, sys
from harness import apply_train, registry
real = registry.register
def register(*a, **k):  # 등록 줄을 쓴 직후·적용 기록 전에 실제 SIGKILL
    real(*a, **k)
    os.kill(os.getpid(), signal.SIGKILL)
registry.register = register
apply_train.apply(sys.argv[1], sys.argv[2], 9.0)
'''


class ApplyTrainTest(unittest.TestCase):
    def setUp(self):
        self.root = make_root(self)
        self.policy = make_batch(self.root, "b1")
        self.base = add_model(self.root, "base", batches=["b1"])
        self.models = registry.load(self.root)["models"]
        self.labels = json.dumps(silver_gate.trainable_labels(self.root), sort_keys=True).encode()  # 능동 학습·Silver 조회 출력 형식

    def make_task(self, files=None, parent="base", task_type="training", done=True):
        """작업 폴더(contract.json·in/ 사본·out/·done.json)를 직접 만든다. files: {입력 경로: 바이트}. task_key를 돌려준다."""
        weights = b"weights-base" if parent == "base" else None
        files = dict({"silver/labels.json": self.labels, "data/train.jsonl": b"rows"},
                     **({"parents/%s/weights.bin" % self.base: weights} if weights else {}), **(files or {}))
        inputs = {rel: hashlib.sha256(data).hexdigest() for rel, data in files.items()}
        task = {"task_type": task_type, "inputs": inputs, "outputs": ["weights.bin", "eval.json", "manifest.json"],
                "depends_on": [], "needs_llm": False, "needs_vision": False, "risk": "high", "retry_policy": {}, "escalation_level": 0,
                "run_conditions": {"command": ["python", "train.py"] + ["{input:%s}" % rel for rel in sorted(files)],
                                   "code_sha": "A" * 40, "config": {"lr": 0.01}, "seed": 3}}
        key = ct.task_key(task)
        tdir = os.path.join(self.root, "tasks", key)
        write_json(os.path.join(tdir, "contract.json"), task)
        outs = {"weights.bin": b"trained-" + key.encode(), "manifest.json": json.dumps({"silver_label_ids": []}).encode(),
                "eval.json": json.dumps({"layer": "dev", "denominator": "zones:n=10", "seal_version": "none", "metrics": {"miss": 0.3}}).encode()}
        for rel, data in list(files.items()) + [("../out/" + r, d) for r, d in outs.items()]:
            path = os.path.normpath(os.path.join(tdir, "in", rel))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as handle:
                handle.write(data)
        if done:
            write_json(os.path.join(tdir, "done.json"), {"task_key": key, "manifest": {r: hashlib.sha256(d).hexdigest() for r, d in outs.items()}})
        return key

    def test_registers_with_harness_built_manifest_once(self):
        key = self.make_task()
        first, again = apply_train.apply(self.root, key, 5.0), apply_train.apply(self.root, key, 6.0)
        self.assertEqual((first["ok"], again["ok"], again.get("already"), again["model_id"]), (True, True, True, first["model_id"]))
        models = registry.load(self.root)["models"]
        rec = models[first["model_id"]]
        self.assertEqual((len(models), rec["parent"], rec["silver_batches"], rec["code_sha"]), (2, self.base, ["b1"], "a" * 40))
        with open(cas.blob_path(os.path.join(self.root, "cas"), rec["data_manifest_sha"]), encoding="utf-8") as handle:
            made = json.load(handle)
        self.assertEqual(made, {"format": eligibility.MANIFEST_FORMAT, "silver_batches": ["b1"], "start_weights_sha": self.models[self.base]["weights_sha"],
                                "silver_label_ids": sorted(r["label_id"] for r in json.loads(self.labels))})  # out/manifest.json은 무시
        self.assertTrue(eligibility.parent_check(self.root, first["model_id"])["ok"])  # 하네스 manifest는 적격성 대조(manifest v2)를 통과한다
        forged = json.dumps([dict(r, batch_id="other", grade="Gold") for r in json.loads(self.labels)]).encode()  # 파일의 묶음·등급은 믿지 않는다
        claimed = apply_train.apply(self.root, self.make_task({"silver/labels.json": forged, "data/x": b"f"}), 7.5)
        self.assertEqual(registry.load(self.root)["models"][claimed["model_id"]]["silver_batches"], ["b1"])
        scratch = apply_train.apply(self.root, self.make_task(parent=None), 8.0)  # 부모 입력 없음 = 처음부터 학습
        self.assertEqual(registry.load(self.root)["models"][scratch["model_id"]]["parent"], None)

    def test_inputs_and_parent_declaration_are_checked_fail_closed(self):
        held = add_model(self.root, "held", batches=["b1"])
        cases = {"undeclared_parent_weights": self.make_task({"init/w.bin": b"weights-held"}, parent=None),  # 보류 될 모델 가중치를 부모 생략으로
                 "unknown_parent": self.make_task({"parents/%s/w.bin" % ("e" * 64): b"weights-base"}, parent=None),
                 "parent_weights_mismatch": self.make_task({"parents/%s/w.bin" % held: b"weights-base"}, parent=None),
                 "parent_ambiguous": self.make_task({"parents/%s/w.bin" % held: b"weights-held"}),
                 "parent_path": self.make_task({"parents/%s" % held: b"weights-held"}, parent=None),
                 "silver_unknown_label": self.make_task({"silver/labels.json": b'[{"label_id": "%s"}]' % (b"f" * 32)}),
                 "silver_duplicate_label": self.make_task({"silver/labels.json": self.labels[:-1] + b"," + self.labels[1:]}),
                 "silver_format": self.make_task({"silver/labels.json": b'{"label_id": "x"}'}),
                 "silver_ambiguous": self.make_task({"silver/more.json": b"[]"}),
                 "not_verified": self.make_task({"data/x": b"1"}, done=False),
                 "not_training": self.make_task({"data/x": b"2"}, task_type="experiment")}
        tampered = self.make_task({"data/x": b"3"})
        with open(os.path.join(self.root, "tasks", tampered, "in", "silver", "labels.json"), "ab") as handle:
            handle.write(b" ")  # 사본이 계약 SHA와 다르다
        cases["input_copy_mismatch"] = tampered
        gone = self.make_task({"data/x": b"4"})
        os.unlink(os.path.join(self.root, "tasks", gone, "in", "parents", self.base, "weights.bin"))
        cases["input_copy_mismatch:missing"] = gone
        before = len(registry.load(self.root)["models"])
        for reason, key in cases.items():
            got = apply_train.apply(self.root, key, 5.0)
            self.assertEqual((got["ok"], got["reason"]), (False, reason.split(":")[0]), reason)
        self.assertEqual(before, len(registry.load(self.root)["models"]))
        withdrawal.withdraw(self.root, 6.0, self.policy, "criteria_change")  # 보류 계보 부모를 정직하게 선언하면 등록은 되지만 승격은 보류
        honest = apply_train.apply(self.root, self.make_task({"data/x": b"5"}), 7.0)
        self.assertEqual("policy_withdrawn_hold", champion.promote(self.root, 8.0, honest["model_id"])["reason"])
        self.assertEqual("policy_withdrawn_hold", eligibility.parent_check(self.root, honest["model_id"])["reason"])

    def test_halted_state_and_kill_between_register_and_record(self):
        key = self.make_task()
        opstate.set_condition(self.root, opstate.USER_STOPPED, 4.0, "user", "중단")
        self.assertEqual(apply_train.apply(self.root, key, 5.0)["reason"], "halted:USER_STOPPED")
        opstate.clear_by_user(self.root, opstate.USER_STOPPED, 5.0, "재개")
        env = dict(os.environ, PYTHONPATH=REPO, PYTHONDONTWRITEBYTECODE="1")
        child = subprocess.run([sys.executable, "-c", KILL, self.root, key], cwd=REPO, env=env, timeout=60)
        self.assertEqual(child.returncode, -signal.SIGKILL)
        self.assertFalse(os.path.exists(os.path.join(self.root, apply_train.APPLIED, key + ".json")))  # 적용 기록 전에 죽었다
        again = apply_train.apply(self.root, key, 6.0)
        self.assertEqual((again["ok"], len(registry.load(self.root)["models"])), (True, 2))  # 재시작 뒤에도 모델 하나
        self.assertTrue(apply_train.apply(self.root, key, 7.0)["already"])
        with open(os.path.join(self.root, apply_train.APPLIED, key + ".json"), "w", encoding="utf-8") as handle:
            json.dump({"task_key": key, "model_id": "0" * 64}, handle)  # 레지스트리에 없는 모델을 가리키는 적용 기록
        self.assertEqual(apply_train.apply(self.root, key, 8.0)["reason"], "applied_record_mismatch")


if __name__ == "__main__":
    unittest.main()
