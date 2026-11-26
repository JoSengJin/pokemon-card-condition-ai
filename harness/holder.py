"""작업권 기록의 주인(pid)이 flock 없이 살아 있는지 판정한다.

claim이 flock을 잡았다면 "잠금을 쥔 프로세스"는 없다. 그런데 기록된 pid가 같은 부팅에서 살아 있다면
다음 둘 중 하나다: 좀비(죽었지만 부모가 회수하지 않음 → 인수해도 된다) 또는 잠금 없이 계속 실행 중인
프로세스(작업권을 쥔 프로세스가 아닌 쪽이 실행하거나, exec로 잠금 fd를 잃은 경우 → 인수하면 이중 실행).
후자를 인수하지 않는 것이 이중 실행 방지가 멈춤보다 우선이라는 결정의 구현이다.
전제: 작업권을 쥔 프로세스가 끝까지 실행하고 exec하지 않는다(queue.claim이 pid==os.getpid()를 강제한다).
"""
import os
import subprocess

from . import lease


def is_zombie(pid, run=subprocess.run):
    """`ps -o stat= -p <pid>`가 Z로 시작하면 True, 아니면 False. 조회 실패·해석 불가는 None(추정하지 않는다)."""
    try:
        done = run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    stat = done.stdout.strip()
    if done.returncode != 0 or not stat:
        return None
    return stat.startswith("Z")


def verdict(prev, boot, me=None, zombie=None):
    """이전 작업권 기록을 인수해도 되는가: "dead"(인수) | "alive"(정지) | "unknown"(판정 불가, 정지).

    기록이 없음·깨짐·부팅 식별자 다름·pid 죽음·내 pid(같은 프로세스가 놓고 간 기록)·좀비는 dead다.
    zombie는 pid -> True/False/None 조회 함수(시험 주입용, 기본 is_zombie).
    """
    if not lease.is_alive(prev, lambda: boot):
        return "dead"
    if prev["pid"] == (os.getpid() if me is None else me):
        return "dead"
    found = (zombie or is_zombie)(prev["pid"])
    return {True: "dead", False: "alive"}.get(found, "unknown")
