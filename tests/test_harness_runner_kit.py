"""runner 시험 공용 도구(시험 없음)."""
import ast
import json
import os
import pathlib
import subprocess
import sys

from tests.test_harness_support import REPO, RUNNER_PATH, make_contract


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


def spawn_runner(root, marks, extra_env=None, args=()):
    """실제 하위 프로세스로 runner를 실행한다. 환경은 새로 만든다: PATH에 claude 없음, 모델 관련 환경변수 없음."""
    env = {"PATH": RUNNER_PATH, "HARNESS_MARK_DIR": marks, "PYTHONDONTWRITEBYTECODE": "1"}
    env.update(extra_env or {})
    return subprocess.Popen([sys.executable, "-m", "harness.runner", root, "tests.test_harness_executors:EXECUTORS",
                             *args], cwd=REPO, env=env, stdout=subprocess.PIPE, text=True)


def llm_free_violations(src):
    """runner 소스가 모델·네트워크·하위 프로세스를 쓰지 못하게 하는 정적 검사(허용 목록 방식). 위반 목록."""
    tree, bad = ast.parse(src), []
    main = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "main"), None)
    inside_main = {id(n) for n in ast.walk(main)} if main else set()
    imports = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name.split(".")[0] not in {"importlib", "json", "os", "sys", "time"} for a in node.names):
            bad.append("import %s" % [a.name for a in node.names])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and (node.module or "").split(".")[0] not in {"importlib", "json", "os", "sys", "time"}:
            bad.append("from %s" % node.module)
        elif isinstance(node, ast.Name) and node.id in {"__import__", "eval", "exec", "compile"}:
            bad.append("name %s" % node.id)
        elif isinstance(node, ast.Attribute) and (node.attr in {"system", "popen", "Popen", "run", "call", "check_output",
                                                              "fork", "forkpty", "urlopen", "connect"}
                                                  or node.attr.startswith(("exec", "spawn", "posix_spawn"))):
            bad.append("attr %s" % node.attr)
        elif isinstance(node, ast.Attribute) and node.attr == "import_module":
            imports += 1  # 실행기 모듈을 읽는 main의 한 곳만 허용한다
            if id(node) not in inside_main:
                bad.append("import_module outside main")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and any(w in node.value.lower() for w in ("claude", "anthropic")):
            bad.append("string %r" % node.value[:30])
    if imports > 1:
        bad.append("import_module x%d" % imports)
    return bad
