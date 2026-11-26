"""작업권(flock + pid·부팅 식별자) 시험. 부팅 식별자·pid 생존은 주입해 합성 상황을 만든다."""
import os
import sys
import tempfile
import unittest

from harness import lease


class LeaseTest(unittest.TestCase):
    def test_boot_id_parses_sysctl_text_and_fails_explicitly(self):
        sample = "{ sec = 1794224399, usec = 802475 } Mon Nov  9 20:39:59 2026"
        self.assertEqual(lease.boot_id(sample), "1794224399")
        with self.assertRaises(lease.LeaseError):
            lease.boot_id("garbage")

    @unittest.skipUnless(sys.platform == "darwin", "kern.boottime은 macOS 전용")
    def test_real_boot_id_is_stable_digits(self):
        self.assertRegex(lease.boot_id(), r"^\d+$")
        self.assertEqual(lease.boot_id(), lease.boot_id())

    def test_is_alive_requires_same_boot_and_live_pid(self):
        rec = {"pid": 4242, "boot_id": "b1", "ts": 0}
        same_boot = lambda: "b1"
        self.assertTrue(lease.is_alive(rec, same_boot, lambda pid: True))
        self.assertFalse(lease.is_alive(rec, same_boot, lambda pid: False))
        self.assertFalse(lease.is_alive(rec, lambda: "b2", lambda pid: True))
        for broken in (None, {}, {"pid": "7", "boot_id": "b1"}, {"pid": True, "boot_id": "b1"}):
            self.assertFalse(lease.is_alive(broken, same_boot, lambda pid: True))
        self.assertTrue(lease.is_alive({"pid": os.getpid(), "boot_id": "b1"}, same_boot))

    def test_lock_is_exclusive_and_release_cleans_unstamped_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "lease.json")
            first = lease.lock(path)
            self.assertIsNone(lease.lock(path))
            lease.release(first)
            self.assertFalse(os.path.exists(path))
            second = lease.lock(path)
            lease.stamp(second, 7, "b1", 12.5, {"run_id": "r"})
            lease.release(second)
            self.assertTrue(os.path.exists(path))
            self.assertEqual(lease.read(path), {"pid": 7, "boot_id": "b1", "ts": 12.5, "run_id": "r"})
            self.assertEqual(lease.lock(path).previous["run_id"], "r")

    def test_read_distinguishes_absent_empty_and_garbled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "lease.json")
            self.assertIsNone(lease.read(path))
            for text, want in (("", None), ("  \n", None), ("{broken", {}), ("[1]", {})):
                with open(path, "w") as handle:
                    handle.write(text)
                self.assertEqual(lease.read(path), want, text)
