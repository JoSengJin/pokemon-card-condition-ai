"""B5-5: 논리 구역 수 세기(harness/logical_zones.py). 합성 후보만 쓴다. 이 수는 실제 AI 사용량이 아니며 모델 성능 근거가 아니다."""
import copy
import hashlib
import json
import os
import tempfile
import unittest

from harness import active_learning, claude_perm, logical_zones
from tests import harness_depth_kit as kit
from tests.test_harness_silver_active_learning import CONFIG, OPEN
from tests.test_harness_silver_support import al_pool

ITEM = {"region_id": "r1", "image_sha": "aa", "zone": "corner_tl", "group_id": "g1", "defect_type": "corner", "stratum": "back",
        "part": "ranked", "random_part": False}


def staged(text):
    """실제 stage_inputs로 만든 (작업 폴더, 계약). text는 후보 목록 파일 내용(str 또는 bytes)."""
    source, work = tempfile.mkdtemp(), tempfile.mkdtemp()
    data = text if isinstance(text, bytes) else text.encode("utf-8")
    path = os.path.join(source, logical_zones.INPUT)
    os.makedirs(os.path.dirname(path))
    with open(path, "wb") as handle:
        handle.write(data)
    contract = {"inputs": {logical_zones.INPUT: hashlib.sha256(data).hexdigest()}}
    claude_perm.stage_inputs(os.path.join(work, "task"), contract, source, os.path.join(work, "root"))
    return os.path.join(work, "task"), contract


class LogicalZonesTest(unittest.TestCase):
    def test_counts_selected_items_of_real_select_output_and_refuses_the_whole_output(self):
        out = active_learning.select(al_pool(60), OPEN, CONFIG, 10, 11, [])
        self.assertEqual(logical_zones.count_logical_zones(*staged(json.dumps({"selected": out["selected"]}))),
                         len(out["selected"]))
        two = [ITEM, dict(ITEM, region_id="r2", zone="corner_tr"), dict(ITEM, region_id="r3", image_sha="bb", part="random",
                                                                           random_part=True)]
        self.assertEqual(logical_zones.count_logical_zones(*staged(json.dumps({"selected": two}))), 3)  # 같은 구역 이름·다른 사진은 별개
        # 전체 반환에는 선별 점수(trace)와 기대 라벨이 드러나는 큐 소속이 있고, 세지 않는 목록에 구역을 숨길 수 있다
        for body in (out, {"selected": [ITEM], "silver_queue": two}):
            with self.assertRaises(logical_zones.LogicalZoneError):
                logical_zones.count_logical_zones(*staged(json.dumps(body)))

    def test_bad_format_duplicate_zones_and_empty_list_are_refused(self):
        one = json.dumps(ITEM)
        bad = {"깨진 JSON": "{", "UTF-8 아님": b"\xff\xfe", "빈 파일": "", "깊은 중첩": "[" * 100000, "목록": json.dumps([ITEM]),
               "빈 목록": '{"selected": []}', "selected 없음": "{}", "목록 아님": '{"selected": %s}' % one, "null": "null",
               "중복 JSON 키(앞 목록은 안 세어짐)": '{"selected": [%s, %s], "selected": [%s]}' % (one, one, one),
               "항목 안 중복 키": '{"selected": [{"zone": "x", %s]}' % one[1:]}
        items = {"항목이 문자열": ["r1"], "점수 추가": [dict(ITEM, score=0.5)], "키 누락": [{k: v for k, v in ITEM.items() if k != "zone"}],
                 "빈 문자열": [dict(ITEM, zone="  ")], "숫자 값": [dict(ITEM, image_sha=7)], "중첩 목록": [dict(ITEM, zone=["a", "b"])],
                 "part 모름": [dict(ITEM, part="x")], "random_part 불일치": [dict(ITEM, random_part=True)],
                 "random_part 정수": [dict(ITEM, random_part=0)], "같은 항목 두 번": [ITEM, copy.deepcopy(ITEM)],
                 "region_id 중복(철자만 다름)": [ITEM, dict(ITEM, region_id=" R1 ", zone="corner_tr")],
                 "같은 사진·구역(id·결함 유형·철자만 다름)": [ITEM, dict(ITEM, region_id="r2", image_sha=" AA ", zone="Corner_TL",
                                                                    defect_type="surface")]}
        bad.update({name: json.dumps({"selected": value}) for name, value in items.items()})
        for name, text in bad.items():
            with self.subTest(name), self.assertRaises(logical_zones.LogicalZoneError):
                logical_zones.count_logical_zones(*staged(text))

    def test_only_the_sha_checked_regular_copy_is_counted(self):
        text = json.dumps({"selected": [ITEM]})
        task_dir, contract = staged(text)
        path = os.path.join(task_dir, "in", logical_zones.INPUT)
        more = json.dumps({"selected": [ITEM, dict(ITEM, region_id="r2", zone="corner_tr")]})
        with open(path, "w", encoding="utf-8") as handle:  # 같은 task_key(같은 계약)에 목록만 바꿔 끼우기
            handle.write(more)
        with self.assertRaisesRegex(logical_zones.LogicalZoneError, "SHA"):
            logical_zones.count_logical_zones(task_dir, contract)
        elsewhere = os.path.join(tempfile.mkdtemp(), "list.json")
        with open(elsewhere, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.remove(path)
        for kind in ("없음", "링크", "FIFO", "폴더"):
            with self.subTest(kind):
                if kind == "링크":
                    os.symlink(elsewhere, path)  # 내용(SHA)이 같아도 링크는 읽지 않는다
                elif kind == "FIFO":
                    os.mkfifo(path)
                elif kind == "폴더":
                    os.mkdir(path)
                with self.assertRaises(logical_zones.LogicalZoneError):
                    logical_zones.count_logical_zones(task_dir, contract)
                if kind == "폴더":
                    os.rmdir(path)
                elif kind != "없음":
                    os.remove(path)
        os.rmdir(os.path.dirname(path))
        os.symlink(os.path.dirname(elsewhere), os.path.dirname(path))  # 중간 폴더 링크
        os.rename(elsewhere, os.path.join(os.path.dirname(elsewhere), os.path.basename(path)))
        with self.assertRaisesRegex(logical_zones.LogicalZoneError, "링크"):
            logical_zones.count_logical_zones(task_dir, contract)
        for inputs in ({}, {"candidates/other.json": "0" * 64}, {logical_zones.INPUT: None}):
            with self.assertRaises(logical_zones.LogicalZoneError):
                logical_zones.count_logical_zones(task_dir, {"inputs": inputs})

    def test_call_depth_fits_the_claude_job_call_site(self):
        depth, path = kit.longest("logical_zones.count_logical_zones")
        self.assertLessEqual(depth + 2, 4, path)  # supervisor.run -> claude_job.execute -> count_logical_zones


if __name__ == "__main__":
    unittest.main()
