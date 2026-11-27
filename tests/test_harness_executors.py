"""runner 시험용 executor(결정론적 Python 계산, 모델·네트워크 없음). 실행 표식은 HARNESS_MARK_DIR에 남긴다."""
import os
import time


def _mark(task, tag):
    """실행 한 번당 표식 파일 하나(이름에 작업 이름·종류·pid). 같은 작업·종류의 표식 수 = 실행 횟수(이번 포함)."""
    prefix = "%s-%s-" % (task["inputs"]["name"], tag)
    open(os.path.join(os.environ["HARNESS_MARK_DIR"], "%s%d-%d" % (prefix, os.getpid(), time.time_ns())), "w").close()
    return len([n for n in os.listdir(os.environ["HARNESS_MARK_DIR"]) if n.startswith(prefix)])


def _compute(task, out_dir):
    """inputs.n까지의 합을 result.txt에 쓴다."""
    time.sleep(0.02)  # 두 runner가 겹치게
    with open(os.path.join(out_dir, "result.txt"), "w") as handle:
        handle.write(str(sum(range(int(task["inputs"]["n"]) + 1))))
    return ["result.txt"]


def calc(task, out_dir):
    _mark(task, "run")
    return _compute(task, out_dir)


def flaky(task, out_dir):
    """앞의 FAILS번은 ConnectionError(네트워크 차단 모사), 그 뒤에는 성공한다. FAILS=99면 계속 실패."""
    if _mark(task, "run") <= int(task["inputs"]["fails"]):
        raise ConnectionError("네트워크 차단 모사")
    return _compute(task, out_dir)


def poison(task, out_dir):
    """task_type에 따라 비정상 동작: buggy=코드 오류, exiter=sys.exit(), oom=SIGKILL(메모리 부족 강제 종료 모사)."""
    _mark(task, "run")
    if task["task_type"] == "exiter":
        raise SystemExit(3)
    if task["task_type"] == "oom":
        os.kill(os.getpid(), 9)
    raise TypeError("코드 오류 주입")


def slow(task, out_dir):
    """HARNESS_SLOW=hang이면 시작 표식만 남기고 오래 멈춘다(kill -9 시험용), 아니면 바로 끝난다."""
    _mark(task, "start")
    deadline = time.time() + 60
    while os.environ.get("HARNESS_SLOW") == "hang" and time.time() < deadline:
        time.sleep(0.05)
    return calc(task, out_dir)


EXECUTORS = {"calc": calc, "flaky": flaky, "slow": slow, "buggy": poison, "exiter": poison, "oom": poison}
