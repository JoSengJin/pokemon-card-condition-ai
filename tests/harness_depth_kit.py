"""B5 시험 공용 도구(시험 없음): harness/ 정적 호출 그래프로 함수의 최장 호출 경로(전이 수)를 잰다(PAIR_CODING 2.1 호출 깊이 ≤4).

규칙(검증 스크립트 struct.py와 같고 `from .x import f`·`from harness import x`도 따라간다): 모듈 최상위 함수만 노드다. `mod.f(...)`(가져온 harness 모듈)·`f(...)`(같은
파일 함수 또는 `from .mod import f`)·모듈 수준 별칭(`current = pointer.current`)을 호출로 본다. 객체 메서드·동적 호출(executor 표 등)은
잡지 못한다(정적으로 확정할 수 없는 경로는 각 시험·문서에 따로 적는다). 순환은 한 번만 따라간다.
"""
import ast
import glob
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


def call_graph(repo=REPO):
    """{(모듈, 함수): {(모듈, 함수), ...}} — harness 안에 정의된 대상만 남긴다."""
    calls = {}
    for path in sorted(glob.glob(os.path.join(repo, "harness", "*.py"))):
        mod = os.path.basename(path)[:-3]
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        mods, names = {}, {}
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and (node.level == 1 or (node.module or "").split(".")[0] == "harness"):
                sub = None if node.module in (None, "harness") else node.module.split(".")[-1]  # from . / from harness import 모듈
                for a in node.names:
                    (mods if sub is None else names)[a.asname or a.name] = a.name if sub is None else (sub, a.name)
            elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Attribute) and isinstance(node.value.value, ast.Name):
                for target in node.targets:
                    if isinstance(target, ast.Name) and node.value.value.id in mods:
                        names[target.id] = (mods[node.value.value.id], node.value.attr)
        for func in tree.body:
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            found = set()
            for node in ast.walk(func):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    found.add(names.get(node.func.id, (mod, node.func.id)))
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) \
                        and node.func.value.id in mods:
                    found.add((mods[node.func.value.id], node.func.attr))
            calls[(mod, func.name)] = found
    return {key: {c for c in found if c in calls} for key, found in calls.items()}


def longest(name, graph=None, seen=()):
    """("mod.func") -> (전이 수, 경로 목록). 예: ("budget.charge") -> (2, ["budget.charge", "ledger.verify", "ledger._check_line"])."""
    graph = call_graph() if graph is None else graph
    key = tuple(name.split(".")) if isinstance(name, str) else name
    best = (0, ["%s.%s" % key])
    for callee in sorted(graph.get(key, ())):
        if callee in seen or callee == key:
            continue
        depth, path = longest(callee, graph, seen + (key,))
        if depth + 1 > best[0]:
            best = (depth + 1, ["%s.%s" % key] + path)
    return best
