"""runner 시험 공용 도구(시험 없음)."""
import json
import os
import pathlib

from tests.test_harness_support import make_contract, spawn_runner


def task(name, task_type="calc", n="10", fails="0", **kw):
    """executor가 읽는 inputs(name·n·fails)를 가진 합성 작업 계약."""
    return make_contract(name, inputs={"name": name, "n": n, "fails": fails}, task_type=task_type, **kw)


def run(case, root, marks, **kw):
    """runner를 별도 프로세스로 실행하고 요약(JSON)을 돌려준다."""
    proc = spawn_runner(root, marks, **kw)
    case.addCleanup(proc.kill)
    out = proc.communicate(timeout=120)[0]
    case.assertEqual(proc.returncode, 0)
    return json.loads(out)


def count(marks, name, tag="run"):
    """executor 실행 표식 수(= 그 작업이 실행된 횟수)."""
    return len([n for n in os.listdir(marks) if n.startswith("%s-%s-" % (name, tag))])


def write_result(task_, out_dir):
    pathlib.Path(out_dir, "result.txt").write_text("x")
    return ["result.txt"]


def link_result(out_dir, elsewhere):
    """산출물이 out/ 밖 파일을 가리키는 심볼릭 링크(완료할 수 없는 출력)."""
    os.symlink(os.path.join(elsewhere, "x"), os.path.join(out_dir, "result.txt"))
    return ["result.txt"]
