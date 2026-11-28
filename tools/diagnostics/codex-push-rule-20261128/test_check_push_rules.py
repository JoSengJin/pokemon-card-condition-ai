"""Exercise the installed CLI with synthetic rules and cover failure handling."""

from hashlib import sha256
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True

from check_push_rules import main, policy_decision


DIRECTORY = Path(__file__).resolve().parent
SYNTHETIC_RULES = (
    'prefix_rule(pattern=["git", "push", "origin", "main"], decision="allow")\n'
    'prefix_rule(pattern=["./develop", "--", "git"], decision="allow")\n'
)


class PushRuleTests(unittest.TestCase):
    def run_check(self, candidate_text, current_text=SYNTHETIC_RULES):
        with tempfile.TemporaryDirectory() as directory:
            rules = Path(directory) / "original.rules"
            candidate = Path(directory) / "proposal.rules"
            rules.write_text(current_text, encoding="utf-8")
            candidate.write_text(candidate_text, encoding="utf-8")
            inputs = (rules, candidate)
            before = [sha256(path.read_bytes()).hexdigest() for path in inputs]
            result = subprocess.run(
                [sys.executable, str(DIRECTORY / "check_push_rules.py"),
                 "--rules", str(rules), "--candidate", str(candidate)],
                capture_output=True, text=True,
            )
            self.assertEqual(before, [sha256(path.read_bytes()).hexdigest() for path in inputs])
        return result

    def test_proposed_rules(self):
        result = self.run_check((DIRECTORY / "proposed.rules").read_text(encoding="utf-8"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rows = [line.split("\t") for line in result.stdout.splitlines()[1:]]
        self.assertEqual(sum(row[0] == "필수" and row[-1] == "통과" for row in rows), 5)
        self.assertEqual(sum(row[0] == "보존" and row[-1] == "통과" for row in rows), 6)
        self.assertEqual(sum(row[0] == "관찰" and row[-1] == "한계" for row in rows), 7)
        self.assertIn(["필수", "git push origin main", "allow", "prompt", "통과"], rows)
        self.assertIn(["보존", "git status", "미일치", "미일치", "통과"], rows)

    def test_missing_push_rules_fail(self):
        result = self.run_check("# no additional rules\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("필수\tgit push origin main\tallow\tallow\t실패", result.stdout)

    def test_changed_preserved_rule_fails(self):
        proposal = (DIRECTORY / "proposed.rules").read_text(encoding="utf-8")
        proposal += 'prefix_rule(pattern=["git", "status"], decision="prompt")\n'
        result = self.run_check(proposal)
        self.assertEqual(result.returncode, 1)
        self.assertIn("보존\tgit status\t미일치\tprompt\t실패", result.stdout)

    def test_invalid_cli_output_fails(self):
        for output in ("invalid json", "{}", '{"matchedRules": [], "decision": "unknown"}'):
            with self.subTest(output=output), patch("check_push_rules.subprocess.run") as run:
                run.return_value.stdout = output
                self.assertEqual(policy_decision((), ("git", "status")), "오류")

    def test_cli_failure_is_not_a_decision(self):
        with patch("check_push_rules.subprocess.run") as run:
            run.side_effect = subprocess.CalledProcessError(2, "codex")
            self.assertEqual(policy_decision((), ("git", "status")), "오류")

    def test_missing_cli_fails(self):
        with (
            patch("check_push_rules.shutil.which", return_value=None),
            patch.object(sys, "argv", ["checker", "--rules", "x", "--candidate", "y"]),
            patch("sys.stderr"),
        ):
            self.assertEqual(main(), 1)


if __name__ == "__main__":
    unittest.main()
