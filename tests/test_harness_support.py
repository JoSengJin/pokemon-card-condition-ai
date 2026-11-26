"""하네스 시험 공용 도구(시험 없음). 실제 하위 프로세스 작업자와 합성 상황 생성기."""
import functools
import os
import subprocess
import sys

from harness import checkpoint, lease, queue

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOT = "boot-test-1"
SHA_A = "ab" * 32

WORKER = r'''
import os, sys, time
from harness import queue
root, key, boot, gate = sys.argv[1:5]
while not os.path.exists(gate):
    time.sleep(0.005)
res = queue.claim(root, key, os.getpid(), boot, time.time(), boot_id_fn=lambda: boot)
print("CLAIMED " + res["run_id"] if res["ok"] else "REFUSED " + res["reason"], flush=True)
if res["ok"]:
    sys.stdin.readline()
'''

CHURN = r'''
import os, sys, time
from harness import queue, lease
root, key, boot, gate, rounds = sys.argv[1:6]
print("READY", flush=True)  # 모두 준비된 뒤에 동시에 출발시키려고
while not os.path.exists(gate):
    time.sleep(0.001)
wins = overlaps = 0
for _ in range(int(rounds)):
    res = queue.claim(root, key, os.getpid(), boot, time.time(), boot_id_fn=lambda: boot)
    if not res["ok"]:
        continue
    wins += 1
    try:  # 작업권을 쥔 동안 O_EXCL 표식을 만든다. 이미 있으면 두 프로세스가 동시에 쥐고 있었다는 뜻
        os.close(os.open(os.path.join(root, "SENTINEL"), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except FileExistsError:
        overlaps += 1
        lease.release(res["lease"], remove=True)
        continue
    time.sleep(0.0005)
    os.unlink(os.path.join(root, "SENTINEL"))
    lease.release(res["lease"], remove=True)
print(wins, overlaps, flush=True)
'''

EXEC_CLAIM = r'''
import os, sys, time
from harness import queue
root, key, boot = sys.argv[1:4]
res = queue.claim(root, key, os.getpid(), boot, time.time(), boot_id_fn=lambda: boot)
print("CLAIMED" if res["ok"] else "REFUSED", flush=True)
os.execv("/bin/sleep", ["sleep", "30"])  # 같은 pid가 계속 실행되지만 잠금 fd(close-on-exec)는 사라진다
'''

FAIL_CRASH = r'''
import os, sys, time
from harness import queue
root, key, boot = sys.argv[1:4]
res = queue.claim(root, key, os.getpid(), boot, time.time(), boot_id_fn=lambda: boot)
queue.ledger.append = lambda *args: os.kill(os.getpid(), 9)  # 실패 기록 파일을 쓴 직후, 작업권 해제 전에 kill -9
queue.fail(root, key, res["run_id"], res["lease"], "deterministic", "TypeError", time.time())
'''

claim = functools.partial(queue.claim, boot_id_fn=lambda: BOOT)  # 시험용 부팅 식별자 주입


def make_contract(tag="a", depends_on=(), outputs=("result.txt",)):
    return {"task_type": "unit-" + tag, "inputs": {"in.txt": SHA_A}, "outputs": list(outputs),
            "depends_on": list(depends_on), "needs_llm": False, "needs_vision": False,
            "risk": "low", "retry_policy": {}, "escalation_level": 0}


def alive_with(boot=BOOT, pid_alive=None):
    """부팅 식별자를 고정한 is_alive. 기본은 실제 pid 생존 조회(os.kill)."""
    extra = {} if pid_alive is None else {"pid_alive": pid_alive}
    return functools.partial(lease.is_alive, boot_id_fn=lambda: boot, **extra)


def finish(root, task, now, payload=b"v1"):
    """enqueue -> claim -> 산출물 쓰기 -> complete(합성 정상 완료). (task_key, run_id)."""
    key = queue.enqueue(root, task, now)
    res = claim(root, key, os.getpid(), BOOT, now)
    for rel in task["outputs"]:
        path = os.path.join(root, "tasks", key, "out", rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(payload)
    queue.complete(root, key, res["run_id"], res["lease"], now + 1)
    return key, res["run_id"]


def start_workers(case, root, count, worker=WORKER, rounds=1):
    """작업을 등록하고 실제 하위 프로세스 count개를 gate 파일이 생길 때까지 대기시킨다(동시 출발용).

    (key, gate, 프로세스 목록). 정리는 거꾸로 실행되므로 kill -> wait -> 파이프 닫기 순이다.
    """
    key = queue.enqueue(root, make_contract(), 1_000_000.0)
    gate = os.path.join(root, "go")
    procs = [subprocess.Popen([sys.executable, "-c", worker, root, key, BOOT, gate, str(rounds)], cwd=REPO,
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True) for _ in range(count)]
    for proc in procs:
        for cleanup in (proc.stdout.close, proc.stdin.close, proc.wait, proc.kill):
            case.addCleanup(cleanup)
    return key, gate, procs


def dead_lease(root, key, started, run_id="r-dead", pid=999999):
    """중단된 실행이 남긴 작업권 파일(시작 시각·run_id 지정). 생존 여부는 alive_with(pid_alive=...)로 주입한다."""
    handle = lease.lock(os.path.join(root, "tasks", key, "lease.json"))
    lease.stamp(handle, pid, BOOT, started, {"run_id": run_id, "resumed": False})
    lease.release(handle)


def fingerprint(**override):
    """체크포인트·현재 실행 지문(코드·자료 SHA, seed, 난수·옵티마이저·데이터 순서)."""
    return dict({name: "v-" + name for name in checkpoint.REQUIRED}, **override)
