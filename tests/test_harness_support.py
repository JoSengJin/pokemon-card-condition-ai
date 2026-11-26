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
res = queue.claim(root, key, os.getpid(), boot, time.time())
print("CLAIMED " + res["run_id"] if res["ok"] else "REFUSED " + res["reason"], flush=True)
if res["ok"]:
    sys.stdin.readline()
'''


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
    res = queue.claim(root, key, os.getpid(), BOOT, now, is_alive=alive_with())
    for rel in task["outputs"]:
        path = os.path.join(root, "tasks", key, "out", rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(payload)
    queue.complete(root, key, res["run_id"], res["lease"], now + 1)
    return key, res["run_id"]


def spawn_claimers(root, key, count, gate):
    """실제 하위 프로세스 count개를 gate 파일이 생길 때까지 대기시켜 둔다(동시 출발용). 각 프로세스는 claim 뒤 stdin을 기다린다."""
    return [subprocess.Popen([sys.executable, "-c", WORKER, root, key, BOOT, gate], cwd=REPO,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True) for _ in range(count)]


def dead_lease(root, key, started, run_id="r-dead", pid=999999):
    """중단된 실행이 남긴 작업권 파일(시작 시각·run_id 지정). 생존 여부는 alive_with(pid_alive=...)로 주입한다."""
    handle = lease.lock(os.path.join(root, "tasks", key, "lease.json"))
    lease.stamp(handle, pid, BOOT, started, {"run_id": run_id, "resumed": False})
    lease.release(handle)


def fingerprint(**override):
    """체크포인트·현재 실행 지문(코드·자료 SHA, seed, 난수·옵티마이저·데이터 순서)."""
    return dict({name: "v-" + name for name in checkpoint.REQUIRED}, **override)
