"""3단계 Supervisor 시험 공용 도구(시험 없음). 가짜 claude 실행 파일(실제 하위 프로세스)과 상태 읽기 도우미.

가짜 claude는 실제 `claude`를 부르지 않고 모델을 호출하지 않는다. FAKE_CLAUDE_SCENARIO(JSON 목록)의 n번째 항목대로
stream-json 줄을 내고 끝나며, 실행마다 FAKE_CLAUDE_LOG에 argv·시각·세션 인자를 한 줄씩 남긴다(`--help`는 kind=help).
항목 do: limit(rate_limit_event 후 종료 코드 1) | success(계약 outputs를 산출물 폴더에 쓰고 성공 결과) |
no_session(--resume 대상 없음, 종료 코드 1) | fail. reset: sec|ms|iso|garbage|none|past, after(초), field, type, status, delay,
session(init 이벤트가 알려줄 세션 ID를 요청값과 다르게).
"""
import json
import os
import stat
import subprocess
import sys
import tempfile

from harness import queue
from tests.test_harness_support import REPO, make_contract

FAKE = r'''#!%(python)s
import datetime, json, os, re, sys, time, uuid
argv, log = sys.argv[1:], os.environ["FAKE_CLAUDE_LOG"]
def note(kind, **kw):
    with open(log, "a") as h:
        h.write(json.dumps(dict(kw, kind=kind, argv=argv, t=time.time(), pid=os.getpid())) + "\n")
if argv[:1] == ["--help"]:
    note("help")
    print("Usage: claude [options]\n"
          "  --effort <level>                      Effort level for the current session\n"
          "                                        (low, medium, high, xhigh, max)\n"
          "  --model <model>                       Model for the current session. Provide\n"
          "                                        an alias for the latest model (e.g.\n"
          "                                        'fable', 'opus', or 'sonnet') or a\n"
          "                                        model's full name.\n")
    sys.exit(0)
steps = json.load(open(os.environ["FAKE_CLAUDE_SCENARIO"]))
done = [json.loads(l) for l in open(log)] if os.path.exists(log) else []
n = len([d for d in done if d["kind"] == "run"])
step = steps[n] if n < len(steps) else {"do": "missing"}
opt = {a: argv[i + 1] for i, a in enumerate(argv[:-1]) if a.startswith("--")}
after = time.time() + step.get("after", 2)
reset = {"sec": after, "ms": after * 1000, "garbage": "soon", "none": None, "past": time.time() - 100,
         "iso": datetime.datetime.fromtimestamp(after, datetime.timezone.utc).isoformat()}[step.get("reset", "sec")]
note("run", n=n, step=step, resume=opt.get("--resume"), session_id=opt.get("--session-id"), model=opt.get("--model"),
     effort=opt.get("--effort"), prompt=argv[1] if len(argv) > 1 else None, reset=reset)
time.sleep(step.get("delay", 0))
if step["do"] == "no_session":
    sys.stderr.write("No conversation found with session ID: %%s\n" %% opt.get("--resume"))
    sys.exit(1)
session = step.get("session") or opt.get("--resume") or opt.get("--session-id") or str(uuid.uuid4())
print(json.dumps({"type": "system", "subtype": "init", "session_id": session, "model": opt.get("--model")}), flush=True)
if step["do"] == "limit":
    info = {"status": step.get("status", "rejected")}
    if step.get("type", "five_hour") is not None:
        info["rateLimitType"] = step.get("type", "five_hour")
    if reset is not None:
        info[step.get("field", "resetsAt")] = reset
    print(json.dumps({"type": "rate_limit_event", "rate_limit_info": info, "session_id": session}), flush=True)
    print(json.dumps({"type": "result", "subtype": "error", "is_error": True, "session_id": session}), flush=True)
    sys.exit(1)
if step["do"] == "success":
    out_dir = re.search(r"산출물 폴더: (.+)", argv[1]).group(1).strip()
    task = json.load(open(re.search(r"계약 파일: (.+)", argv[1]).group(1).strip()))
    for rel in task["outputs"]:
        os.makedirs(os.path.dirname(os.path.join(out_dir, rel)), exist_ok=True)
        open(os.path.join(out_dir, rel), "w").write("claude:" + session)
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "session_id": session,
                      "usage": {"input_tokens": 1, "output_tokens": 2}}), flush=True)
    sys.exit(0)
print(json.dumps({"type": "result", "subtype": "error", "is_error": True}), flush=True)
sys.exit(1)
'''


def make_fake(case, scenario):
    """임시 폴더에 가짜 claude와 시나리오를 만든다. (실행 파일 경로, 로그 경로, env)."""
    base = tempfile.mkdtemp()
    case.addCleanup(subprocess.run, ["rm", "-rf", base])
    path, log, plan = (os.path.join(base, n) for n in ("claude", "fake.log", "scenario.json"))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(FAKE % {"python": sys.executable})
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    with open(plan, "w", encoding="utf-8") as handle:
        json.dump(scenario, handle)
    env = dict(os.environ, FAKE_CLAUDE_LOG=log, FAKE_CLAUDE_SCENARIO=plan, PYTHONDONTWRITEBYTECODE="1")
    return path, log, env


def runs(log, kind="run"):
    """가짜 claude 실행 기록(kind=run은 --help 제외)."""
    if not os.path.exists(log):
        return []
    with open(log, encoding="utf-8") as handle:
        return [r for r in (json.loads(line) for line in handle) if r["kind"] == kind]


def llm_task(root, name="llm", now=1_000_000.0, task_type="general_dev", depends_on=()):
    """needs_llm=true 작업을 큐에 등록하고 task_key를 돌려준다."""
    return queue.enqueue(root, make_contract(name, task_type=task_type, needs_llm=True, depends_on=depends_on), now)


def events(root, name=None, path="ledger.jsonl"):
    """장부(기본 root/ledger.jsonl)의 줄 목록. name을 주면 그 이벤트만."""
    full = os.path.join(root, path)
    if not os.path.exists(full):
        return []
    with open(full, encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle]
    return [r for r in rows if name is None or r["event"] == name]


SUPERVISOR = [sys.executable, "-m", "harness.supervisor"]  # 실제 하위 프로세스 실행용(cwd=REPO)


class Clock:
    """가짜 시계: sleep은 실제로 기다리지 않고 시각만 앞당긴다. 잠든 시간은 naps에 남는다."""

    def __init__(self, start):
        self.t, self.naps = float(start), []

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.naps.append(seconds)
        self.t += seconds
