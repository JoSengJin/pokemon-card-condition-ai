"""8단계 Gold 시험 공용 도구(시험 없음). 훅은 실제 하위 프로세스에 표준입력 JSON을 넣어 부른다(설치 없음, 모의 입력)."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile

from harness import gold_issue, gold_store

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRITERIA = hashlib.sha256(b"corner-criteria:test-1").hexdigest()  # 기준 문구의 SHA-256 자리

# 진입점을 __main__으로 실행하기 전에 argv[2]의 코드를 끼워 넣는 드라이버(kill -9 지점·경합 창 주입용).
# 이 드라이버가 저장에 성공한다는 것 자체가 훅 표식이 보안 경계가 아니라는 뜻이다(gold_store 한계 설명).
DRIVER = r'''
import os, runpy, signal, sys, time
sys.path.insert(0, sys.argv[1])
from harness import gold_store, ledger
exec(sys.argv[2])
sys.argv = [gold_store.ENTRY, sys.argv[3]]
runpy.run_path(gold_store.ENTRY, run_name="__main__")
'''


def zones(*names):
    """합성 구역(실제 사진 아님). 이름이 같으면 같은 이미지·구역이다."""
    return [{"image_sha256": hashlib.sha256(("image-" + n).encode()).hexdigest(), "region": "upper_left",
             "crop_sha256": hashlib.sha256(("crop-" + n).encode()).hexdigest()} for n in names]


def issue(root, *names, criteria=CRITERIA, judge="judy", **kw):
    return gold_issue.issue(root, zones(*(names or ("a", "b"))), criteria, judge, 100.0, **kw)


def paste(meta, values=None, **head):
    """화면이 만들 붙여넣기. head로 머리 줄 값을 바꾸고, None이면 그 줄을 뺀다."""
    lines = {"화면": meta["screen_id"], "nonce": meta["nonce"], "직접판정": "확인", "제출시각": "2026-12-01T10:00:00+09:00"}
    lines.update(head)
    values = values if values is not None else ["정상"] * len(meta["zones"])
    return "\n".join(["# %s=%s" % (k, v) for k, v in lines.items() if v is not None]
                     + ["z%d=%s" % (n, v) for n, v in enumerate(values, 1)])


def launch(root, prompt, patch=None, event="UserPromptSubmit", stdin=None):
    """훅 프로세스를 띄우고 stdin까지 넣은 Popen. patch가 있으면 드라이버를 거친다."""
    command = [sys.executable, "-I", "-B"]
    command += [gold_store.ENTRY, root] if patch is None else ["-c", DRIVER, REPO, patch, root]
    proc = subprocess.Popen(command, cwd=tempfile.gettempdir(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    if stdin is None:
        stdin = json.dumps({"hook_event_name": event, "prompt": prompt, "session_id": "session-test",
                            "transcript_path": "/tmp/transcript-test.jsonl"}).encode("utf-8")
    proc.stdin.write(stdin)
    proc.stdin.close()
    return proc


def hook(case, root, prompt, **kw):
    """훅을 끝까지 실행한다. 종료 코드 0과 빈 stderr를 확인하고 표준출력을 돌려준다."""
    proc = launch(root, prompt, **kw)
    out, err = proc.stdout.read().decode("utf-8"), proc.stderr.read().decode("utf-8")
    proc.stdout.close()
    proc.stderr.close()
    case.assertEqual((proc.wait(timeout=60), err), (0, ""), out)
    return out


def stored(root):
    return [r["data"] for r in gold_store.rows(root, gold_store.STORE)]
