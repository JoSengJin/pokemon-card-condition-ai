"""반복 claim→해제 경합: 작업권 파일이 지워졌다 다시 만들어지는 사이의 이중 소유를 O_EXCL 표식으로 감지한다."""
import os
import tempfile
import unittest

from harness import ledger
from tests.test_harness_support import CHURN, start_workers


class ClaimChurnTest(unittest.TestCase):
    def test_repeated_claim_and_release_never_overlaps_across_processes(self):
        with tempfile.TemporaryDirectory() as root:
            key, gate, procs = start_workers(self, root, 12, worker=CHURN, rounds=150)
            open(gate, "w").close()
            counts = [[int(n) for n in proc.stdout.readline().split()] for proc in procs]
            wins, overlaps = sum(c[0] for c in counts), sum(c[1] for c in counts)
            self.assertGreater(wins, 12)  # 프로세스마다 여러 번 이겼다(실제로 경합했다)
            self.assertEqual(overlaps, 0)  # 두 프로세스가 동시에 작업권을 쥔 적이 없다
            self.assertEqual(ledger.verify(os.path.join(root, "ledger.jsonl")), [])
            self.assertFalse(os.path.exists(os.path.join(root, "SENTINEL")))
