"""Compare execpolicy verdicts for the task's fixed command matrix."""

import argparse
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile


ROWS = (
    ("필수", "git push"),
    ("필수", "git push origin main"),
    ("필수", "git push origin HEAD:main"),
    ("필수", "./develop -- git push"),
    ("필수", "./develop -- git push origin main"),
    ("보존", "git commit -m x"),
    ("보존", "git fetch origin main"),
    ("보존", "git status"),
    ("보존", "git diff --cached --name-only"),
    ("보존", "./develop -- git commit -m x"),
    ("보존", "./develop -- git status"),
    ("관찰", "git -C . push origin main"),
    ("관찰", "git -c push.default=current push"),
    ("관찰", "/usr/bin/git push origin main"),
    ("관찰", "env git push origin main"),
    ("관찰", '/bin/zsh -lc "git push origin main"'),
    ("관찰", "./develop -- /usr/bin/git push origin main"),
    ("관찰", "git send-pack origin main"),
)
RESTRICTIVE = {"prompt", "forbidden"}


def policy_decision(rule_files, tokens):
    args = ["codex", "execpolicy", "check"]
    for rules in rule_files:
        args.extend(("--rules", str(rules)))
    try:
        result = subprocess.run(
            [*args, "--", *tokens], capture_output=True, check=True, text=True,
        )
        payload = json.loads(result.stdout)
    except (OSError, subprocess.CalledProcessError, ValueError):
        return "오류"

    if isinstance(payload, dict):
        decision = payload.get("decision")
        matches = payload.get("matchedRules")
        if isinstance(matches, list):
            if matches and decision in ("allow", "prompt", "forbidden"):
                return decision
            if not matches and decision is None:
                return "미일치"
    return "오류"


def classify(category, current, proposed):
    if "오류" in (current, proposed):
        return "실패"
    if category == "관찰":
        return "일치" if proposed in RESTRICTIVE else "한계"
    if category == "필수":
        return "통과" if proposed in RESTRICTIVE else "실패"
    return "통과" if proposed == current and proposed not in RESTRICTIVE else "실패"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    args = parser.parse_args()
    if shutil.which("codex") is None:
        print("오류: PATH에서 codex를 찾을 수 없습니다.", file=sys.stderr)
        return 1

    failed = False
    with tempfile.TemporaryDirectory(prefix="codex-push-rule-") as directory:
        current_rules = Path(directory) / "current.rules"
        candidate_rules = Path(directory) / "candidate.rules"
        try:
            shutil.copyfile(args.rules, current_rules)
            shutil.copyfile(args.candidate, candidate_rules)
        except OSError:
            print("오류: 입력 규칙의 임시 사본을 만들 수 없습니다.", file=sys.stderr)
            return 1

        print("분류\t명령\t현재\t적용안\t결과")
        for category, command in ROWS:
            tokens = shlex.split(command)
            current = policy_decision((current_rules,), tokens)
            proposed = policy_decision((current_rules, candidate_rules), tokens)
            outcome = classify(category, current, proposed)
            print(category, command, current, proposed, outcome, sep="\t")
            failed |= outcome == "실패"
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
