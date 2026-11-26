"""산출물 경로 안전: 심볼릭 링크로 root 밖을 읽거나 쓰지 못한다(링크 폴더·링크 파일·out 자체)."""
import os
import pathlib
import tempfile
import unittest

from harness import lease, manifest, queue, states
from tests.test_harness_support import BOOT, alive_with, finish, make_contract

T0 = 1_000_000.0


class PathSafetyTest(unittest.TestCase):
    def test_safe_path_rejects_traversal_links_and_non_strings(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, outside = os.path.join(tmp, "out"), os.path.join(tmp, "outside")
            os.makedirs(os.path.join(out, "real"))
            os.makedirs(outside)
            os.symlink(outside, os.path.join(out, "linked"))
            self.assertEqual(manifest.safe_path(out, "real/a.txt"), os.path.join(out, "real", "a.txt"))
            self.assertIsNotNone(manifest.safe_path(out, "not-yet/created.txt"))  # 없는 파일도 복구 대상 경로는 허용
            for rel in ("linked/a.txt", "../x", "a/../../x", "/etc/passwd", "", None, 7):
                self.assertIsNone(manifest.safe_path(out, rel), rel)

    def test_complete_refuses_outputs_behind_a_linked_folder_or_linked_out(self):
        for outputs, link_at in ((("sub/r.txt",), "sub"), (("result.txt",), "")):
            with self.subTest(link_at=link_at), tempfile.TemporaryDirectory() as root, \
                    tempfile.TemporaryDirectory() as outside:
                task = make_contract(outputs=outputs)
                key = queue.enqueue(root, task, T0)
                res = queue.claim(root, key, os.getpid(), BOOT, T0)
                out = os.path.join(root, "tasks", key, "out")
                if link_at:
                    os.makedirs(out)
                os.symlink(outside, os.path.join(out, link_at) if link_at else out)
                pathlib.Path(outside, os.path.basename(outputs[0])).write_bytes(b"good")
                with self.assertRaises(ValueError):
                    queue.complete(root, key, res["run_id"], res["lease"], T0 + 1)
                self.assertFalse(os.path.exists(os.path.join(root, "tasks", key, "done.json")))
                self.assertFalse(os.path.exists(os.path.join(root, "cas")))  # 밖의 파일을 CAS로 읽어 들이지 않았다
                lease.release(res["lease"])

    def test_swapping_a_folder_or_out_for_a_link_after_completion_is_corrupt_and_never_restored_outside(self):
        for link_out in (False, True):
            with self.subTest(link_out=link_out), tempfile.TemporaryDirectory() as root, \
                    tempfile.TemporaryDirectory() as outside:
                key, _ = finish(root, make_contract(outputs=("sub/r.txt",)), T0, payload=b"data")
                tdir = os.path.join(root, "tasks", key)
                out = os.path.join(tdir, "out")
                if link_out:  # out 전체를 링크로 바꾼다(밖에는 같은 내용의 sub/r.txt)
                    os.rename(out, out + ".real")
                    os.makedirs(os.path.join(outside, "sub"))
                    pathlib.Path(outside, "sub", "r.txt").write_bytes(b"data")  # 내용이 같아도 링크를 거치면 안 된다
                    os.symlink(outside, out)
                else:  # out/sub 폴더만 링크로 바꾼다
                    os.rename(os.path.join(out, "sub"), os.path.join(tdir, "sub.real"))
                    pathlib.Path(outside, "r.txt").write_bytes(b"data")
                    os.symlink(outside, os.path.join(out, "sub"))
                self.assertEqual(states.classify(tdir, T0, alive_with()), states.CORRUPT)
                for leftover in pathlib.Path(outside).rglob("r.txt"):
                    leftover.unlink()  # 밖의 파일이 사라진 상황에서 CAS 복구가 밖에 다시 쓰면 안 된다
                plan = queue.recover(root, key, T0 + 5, is_alive=alive_with())
                self.assertEqual(plan["action"], "rerun")
                self.assertEqual([p for p in pathlib.Path(outside).rglob("*") if p.is_file()], [])

    def test_file_symlink_to_same_content_is_corrupt_and_not_restored_through_the_link(self):
        with tempfile.TemporaryDirectory() as root:
            key, _ = finish(root, make_contract(), T0, payload=b"data")
            tdir, out = os.path.join(root, "tasks", key), os.path.join(root, "tasks", key, "out")
            pathlib.Path(out, "copy.txt").write_bytes(b"data")  # 같은 내용의 다른 파일
            os.unlink(os.path.join(out, "result.txt"))
            os.symlink(os.path.join(out, "copy.txt"), os.path.join(out, "result.txt"))
            self.assertEqual(states.classify(tdir, T0, alive_with()), states.CORRUPT)
            plan = queue.recover(root, key, T0 + 5, is_alive=alive_with())
            self.assertEqual(plan["action"], "rerun")  # 링크를 거쳐 복구하지 않고 새로 실행하게 한다
            self.assertTrue(os.path.islink(os.path.join(out, "result.txt")))
