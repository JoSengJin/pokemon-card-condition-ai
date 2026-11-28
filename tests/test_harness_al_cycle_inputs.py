"""D7 D조각: 능동 학습 후보 입력 계약(harness/al_cycle.load_inputs). 합성 후보만 쓰며 실제 선별·학습·모델 호출이 없다(구현 완료 단계 증거).

빈 보호 목록 틈: active_learning.protected_reason은 네 목록이 모두 [] 여도 통과시킨다(all()이 빈 목록에서 참). 기존 함수는 그대로 두고
load_inputs가 막는다. 이 시험이 그 틈과 막힘을 함께 고정한다.
"""
import hashlib
import json
import os
import tempfile
import unittest

from harness import active_learning, al_cycle, claude_perm
from tests.test_harness_silver_active_learning import CONFIG
from tests.test_harness_silver_support import al_pool

SEED = "ab" * 32
POOL = al_pool(30)
SEALED_GROUP = "gSEALED"
PROTECTED = {"sealed": {"image_shas": ["shaSEALED"], "group_ids": [SEALED_GROUP]},
             "calibration": {"image_shas": ["shaCAL"], "group_ids": ["gCAL"]}}
SETTINGS = {"budget": 6, "config": CONFIG}


def stage(files=None, overrides=None):
    """실제 stage_inputs로 만든 (작업 폴더, 계약). files {상대 경로: 바이트}는 기본 세 파일을 덮어쓴다(SHA는 덮어쓴 내용 기준)."""
    body = {al_cycle.CANDIDATES: json.dumps(POOL), al_cycle.PROTECTED: json.dumps(PROTECTED), al_cycle.SETTINGS: json.dumps(SETTINGS)}
    body.update(files or {})
    source, work = tempfile.mkdtemp(), tempfile.mkdtemp()
    inputs = {}
    for rel, text in body.items():
        data = text if isinstance(text, bytes) else text.encode("utf-8")
        path = os.path.join(source, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(data)
        inputs[rel] = hashlib.sha256(data).hexdigest()
    contract = dict({"task_type": al_cycle.TASK_TYPE, "inputs": inputs, "outputs": list(al_cycle.OUTPUTS), "depends_on": [SEED],
                     "needs_llm": False, "needs_vision": False, "risk": "low", "retry_policy": {}, "escalation_level": 0},
                    **(overrides or {}))
    task_dir = os.path.join(work, "task")
    claude_perm.stage_inputs(task_dir, contract, source, os.path.join(work, "root"))
    return task_dir, contract


class LoadInputsTest(unittest.TestCase):
    def test_reads_the_three_pinned_files_and_the_result_feeds_select(self):
        got = al_cycle.load_inputs(*stage())
        self.assertEqual((got["candidates"], got["protected"], got["budget"], got["seed"]), (POOL, PROTECTED, 6, SEED))
        res = active_learning.select(got["candidates"], got["protected"], got["config"], got["budget"], got["seed"], [])
        self.assertEqual(len(res["selected"]), 6)

    def test_empty_protected_lists_pass_the_old_function_but_load_inputs_refuses_them(self):
        empty = {"image_shas": [], "group_ids": []}
        every_empty = {"sealed": empty, "calibration": empty}
        # 기존 함수의 틈(동작은 바꾸지 않는다): 네 목록이 비어도 모든 후보가 통과한다
        self.assertIsNone(active_learning.protected_reason(dict(POOL[0], group_id=SEALED_GROUP), every_empty))
        self.assertEqual(active_learning.select(POOL, every_empty, CONFIG, 6, SEED, [])["excluded"], {"sealed": 0, "calibration": 0})
        cases = {"전부 빔": every_empty}
        for name in ("sealed", "calibration"):
            for field in ("image_shas", "group_ids"):
                cases["%s.%s만 빔" % (name, field)] = dict(PROTECTED, **{name: dict(PROTECTED[name], **{field: []})})
        for label, body in cases.items():
            with self.subTest(label), self.assertRaises(al_cycle.AlCycleError):
                al_cycle.load_inputs(*stage({al_cycle.PROTECTED: json.dumps(body)}))

    def test_protected_list_is_used_to_exclude_candidates(self):
        pool = [dict(POOL[0], region_id="rS", image_sha="shaSEALED"), dict(POOL[1], region_id="rG", group_id="gCAL")] + POOL[2:]
        got = al_cycle.load_inputs(*stage({al_cycle.CANDIDATES: json.dumps(pool)}))
        res = active_learning.select(got["candidates"], got["protected"], got["config"], 28, got["seed"], [])
        self.assertEqual(res["excluded"], {"sealed": 1, "calibration": 1})
        self.assertFalse({"rS", "rG"} & {s["region_id"] for s in res["selected"]})

    def test_changed_copy_missing_contract_entry_links_and_non_files_are_refused(self):
        task_dir, contract = stage()
        copy = os.path.join(task_dir, "in", *al_cycle.PROTECTED.split("/"))
        with open(copy, "w") as handle:  # 검증 뒤 사본이 바뀜(SHA 불일치)
            handle.write(json.dumps(dict(PROTECTED, sealed={"image_shas": ["x"], "group_ids": ["y"]})))
        with self.assertRaises(al_cycle.AlCycleError):
            al_cycle.load_inputs(task_dir, contract)
        for rel in (al_cycle.CANDIDATES, al_cycle.PROTECTED, al_cycle.SETTINGS):  # 계약 inputs에 없는 파일
            task_dir, contract = stage()
            contract["inputs"].pop(rel)
            with self.subTest("계약에 없음 " + rel), self.assertRaises(al_cycle.AlCycleError):
                al_cycle.load_inputs(task_dir, contract)
        task_dir, contract = stage()  # 파일 링크
        copy = os.path.join(task_dir, "in", *al_cycle.CANDIDATES.split("/"))
        other = os.path.join(task_dir, "other.json")
        os.rename(copy, other)
        os.symlink(other, copy)
        with self.assertRaises(al_cycle.AlCycleError):
            al_cycle.load_inputs(task_dir, contract)
        task_dir, contract = stage()  # 폴더 링크
        folder = os.path.join(task_dir, "in", "al")
        os.rename(folder, os.path.join(task_dir, "real_al"))
        os.symlink(os.path.join(task_dir, "real_al"), folder)
        with self.assertRaises(al_cycle.AlCycleError):
            al_cycle.load_inputs(task_dir, contract)
        task_dir, contract = stage()  # 일반 파일이 아님
        copy = os.path.join(task_dir, "in", *al_cycle.SETTINGS.split("/"))
        os.remove(copy)
        os.mkdir(copy)
        with self.assertRaises(al_cycle.AlCycleError):
            al_cycle.load_inputs(task_dir, contract)

    def test_duplicate_json_keys_and_bad_formats_are_refused(self):
        one = json.dumps(POOL[0])
        bad = {
            al_cycle.CANDIDATES: {"중복 키": "[" + one[:-1] + ', "zone": "x"}]', "목록 아님": json.dumps({"candidates": POOL}), "빈 목록": "[]",
                                  "region_id 중복": json.dumps([POOL[0], dict(POOL[0])]), "필수 필드 누락": json.dumps(
                                      [{k: v for k, v in POOL[0].items() if k != "expected_label"}]), "깨진 JSON": "[", "UTF-8 아님": b"\xff"},
            al_cycle.PROTECTED: {"중복 키": '{"sealed": {"image_shas": ["a"], "group_ids": ["b"]}, "sealed": {"image_shas": ["a"], '
                                           '"group_ids": ["b"]}, "calibration": {"image_shas": ["a"], "group_ids": ["b"]}}',
                                 "목록 아님": "[]", "calibration 없음": json.dumps({"sealed": PROTECTED["sealed"]}),
                                 "문자열이 아닌 값": json.dumps(dict(PROTECTED, sealed={"image_shas": [1], "group_ids": ["g"]})),
                                 "공백 문자열": json.dumps(dict(PROTECTED, sealed={"image_shas": [" "], "group_ids": ["g"]}))},
            al_cycle.SETTINGS: {"budget 없음": json.dumps({"config": CONFIG}), "config 없음": json.dumps({"budget": 3}),
                                "budget 음수": json.dumps(dict(SETTINGS, budget=-1)), "budget 불리언": json.dumps(dict(SETTINGS, budget=True)),
                                "모르는 키": json.dumps(dict(SETTINGS, extra=1)), "상한 없음": json.dumps(
                                    {"budget": 3, "config": {k: v for k, v in CONFIG.items() if k != "per_group_cap"}}),
                                "중복 키": '{"budget": 3, "budget": 4, "config": %s}' % json.dumps(CONFIG)}}
        for rel, cases in bad.items():
            for label, text in cases.items():
                with self.subTest(rel + " " + label), self.assertRaises(al_cycle.AlCycleError):
                    al_cycle.load_inputs(*stage({rel: text}))

    def test_seed_must_be_the_single_dependency(self):
        for depends in ([], [SEED, "cd" * 32]):
            with self.subTest(depends), self.assertRaises(al_cycle.AlCycleError):
                al_cycle.load_inputs(*stage(overrides={"depends_on": depends}))


if __name__ == "__main__":
    unittest.main()
