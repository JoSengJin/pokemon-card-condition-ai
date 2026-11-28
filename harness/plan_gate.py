"""최소 PLAN_GATE(VS3, 사용자 승인 원문 artifacts/harness-resume-20261127/decisions-vs3-20261128.md). LLM을 쓰지 않는 결정론 코드다.

경로: EXPERIMENT_VERIFIED → ANALYZE(Claude A군 misanalysis_general, 산출물 next_plan.json) → gate → supervisor/declared.json → graph.register_missing.
Supervisor가 회차마다 declared.json을 읽은 뒤 gate를 부르고, gate가 돌려준 선언만 register_missing에 넘긴다.

1. VERIFIED 실험(유형 experiment, outputs = experiment_exec.OUTPUTS)마다 ANALYZE 계약을 declared.json에 더한다. 입력은 ./experiment가 원본 저장소에
   남긴 동결 기록 artifacts/experiments/<experiment_id>/{record,result,plan}.json(하네스 root 안 파일은 Claude 입력으로 복사되지 않는다).
   SHA는 하네스가 아는 값: out 사본의 완료 manifest(record·result), record.json의 files["plan.json"]. 실행 직전 stage_inputs가 다시 대조한다.
   development_handoff.json은 하네스 경로에서 생기지 않는다(task 문서 1-3).
2. VERIFIED이고 하네스가 1로 만든 계약과 정확히 같은 ANALYZE의 next_plan.json(Claude 제안 = 검증 대상, 실행 명령 아님)을 검사한다. 이미 그 분석에
   의존하는 실험·학습·평가가 등록됐으면 다시 보지 않는다(재개 뒤 중복 등록 없음). 검사(원문 1절 네 가지):
   - 변수 하나: 대조(분석한 실험의 계약) config.plan과 제안 plan의 실제 차이(키 경로 튜플, 자료형 구분)가 정확히 ("experiment_parameter", "value")
     하나여야 한다(기존 관례 cross_review_auto_validation_plan.check_experiment_parameter). Claude의 variable 선언은 차이와 같아야 할 뿐 근거가 아니다.
     코드도 변수다: source_root HEAD의 코드 지문(dedupe.verify_code)이 대조 커밋과 다르면 대기.
   - 사전 등록: 가설 문구는 Claude, 성공·실패 기준 문구·acceptance·reference_result·code_changes·입력(평가 자료)·command·seed는 대조에서 그대로
     물려받는다(Claude가 바꿀 자리가 없다). experiment_exec.build_plan(실행 때와 같은 검사)을 통과해야 한다.
   - 기각 가설: dedupe.find_duplicate(상태 무관, 가설 ID·설명은 키에서 빠짐)로 같은 실행 조건의 실험이 있으면 거절. 원본 artifacts/experiments의
     ./experiment 기록(하네스 밖 실행 포함)도 _external로 대조한다. 비교할 수 없는 기록이 있으면 통과가 아니라 그 계획만 대기(D4, strict).
     승인 변수 value는 기존 파라미터 정의(cross_review_auto_contract.PARAMETER의 JSON number, check_experiment_parameter)대로 수로 본다(D2):
     baseline·대조 값과 같은 수면 거절하고, 기각 대조는 제안 표기와 같은 수의 int·float 표기로 각각 한다. 전역 dedupe의 config 자료형 규칙
     (사람 등록 config의 1 ≠ 1.0, 4차 I3·사용자 숫자 표기 결정 "자료형을 확인할 수 없으면 변환하지 않는다")은 바꾸지 않는다: 이 변수만 정의상 자료형이 수다.
   - 예산: budget.usage로 이번 주 실험 사용량을 읽기만 한다(한도면 대기). 실제 차감은 실행 직전 runner의 charge 하나뿐(중복 차감 경로 없음).
   next_plan.json 키는 PLAN_KEYS만(command·inputs·run_conditions 등 다른 키는 거절). 통과한 계약 = 대조 계약 + code_sha(HEAD) + 새 plan·가설 문구,
   depends_on = [그 분석].
3. LLM 작업에 직·간접 의존하는 실험·학습·평가 선언(아직 미등록)은 이번 회차에 2가 만든 계약과 정확히 같을 때만 돌려준다(declared.json 직접 작성으로
   검증을 우회하지 못한다). LLM 의존이 없는 선언(사람이 쓰는 대조 실험 등)은 그대로 둔다(신뢰 경계: root/supervisor는 하네스와 사용자만 쓴다.
   Claude A군은 ./out/**만 쓰고 sandbox executor는 root에 쓰지 못한다 — 실환경 권한 확인은 B4).
거절(refused: 제안 위반)과 대기(waiting: 지금 확인할 수 없음)는 그 계획만 멈추고 graph.note_rejected로 장부·알림에 한 번 남긴다(같은 사유 반복 없음,
키 "plan:<분석 task_key>"). 대기는 회차마다 다시 본다. 독립 작업은 계속한다. 통과한 선언은 plan_gate_declared 장부 줄을 남긴다(declared.json 저장 뒤,
줄이 없을 때만). 그 줄이 실행 허가다: runner는 LLM 작업에 직·간접 의존하는 실험·학습·평가를 그 줄이 있을 때만 실행한다(D3, 3의 선언 차단은 알림용 앞단).
한계: declared.json은 새 선언이 있을 때만 다시 쓰며 사용자 선언도 JSON 정규화된다. 사용자 선언에 JSON으로 적을 수 없는 값(supervisor가 NaN으로 읽은
거대 정수 등)이 있으면 파일을 쓰지 않고 알린다(그 회차 등록은 메모리의 선언으로 그대로 한다: 파생은 결정론이라 다음 회차에 다시 만든다).
사용자가 같은 순간 파일을 고치면 덮어쓸 수 있다.
호출 깊이(시작 supervisor.run 기준 +1): gate → find_duplicate → logical_key → _command 3, gate → budget.usage → ledger.verify → _check_line 3,
gate → _derive → verify_code·_head·_diff·build_plan 2, gate → _screen → task_key 2, gate → note_rejected → append 2.
"""
import json
import os
import re
import subprocess
import sys

from . import contract as ct
from . import budget, cas, claude_perm, dedupe, experiment_exec, graph, ledger, seal_check, states
from .jsonio import read_json, write_json

ANALYZE_TYPE = "misanalysis_general"  # A 묶음(claude_perm.BUNDLE_OF), 라우팅 sonnet·medium
NEXT_PLAN = "next_plan.json"
PLAN_KEYS = ("hypothesis_id", "hypothesis", "change", "variable", "plan")
VARIABLE = ("experiment_parameter", "value")  # 승인 변수(점이 든 키로 위장하지 못하게 경로 튜플로 비교)
PARAM_KEYS = ("name", "baseline", "value", "scope")
_EID = re.compile(r"\d{8}T\d{6}-[0-9a-f]{8}")  # experiment_record.prepare의 실험 폴더 이름
_MISSING = object()
_RECORD_STATUS = ("running", "completed", "failed", "interrupted")  # experiment_record.records()가 받는 상태
_FROZEN = {"schema_version": 1, "threshold": .5, "independent": False, "production_adopted": False}  # experiment_record.prepare가 plan.json에 덧붙이는 값
_NOTES = ("hypothesis_id",) + experiment_exec.TEXT_KEYS  # 기각 대조에서 빼는 설명 키(dedupe NOTE_KEYS와 같은 뜻)
# 한 계획의 검사에서 나는 예외(그 계획만 대기). Claude 파일 내용으로 생길 수 있는 부류를 모두 넣는다(D1: 산술 OverflowError 등은 ArithmeticError,
# KeyError·IndexError는 LookupError, 인코딩 오류는 ValueError). 장부·운영 상태 오류(LedgerError·OpStateError)는 넣지 않는다(전체 정지 유지).
_PLAN_ERRORS = (ValueError, TypeError, LookupError, ArithmeticError, AttributeError, RecursionError, OSError, subprocess.SubprocessError,
                budget.BudgetError, experiment_exec.ExperimentError)  # ContractError는 ValueError


class Hold(Exception):
    """args = ("refused"|"waiting", 사유). 그 계획만 멈춘다."""


def _analyze(exp_key, exp_dir):
    """VERIFIED 실험 하나의 ANALYZE 계약. 동결 기록을 판별할 수 없으면 ValueError."""
    record = read_json(os.path.join(exp_dir, "out", "record.json"))
    done = read_json(os.path.join(exp_dir, "done.json"))
    eid = record.get("experiment_id") if isinstance(record, dict) else None
    files = record.get("files") if isinstance(record, dict) else None
    if not isinstance(record, dict) or record.get("status") != "completed" or not isinstance(eid, str) or not _EID.fullmatch(eid) or not isinstance(files, dict) \
            or not isinstance(files.get("plan.json"), str) or not re.fullmatch(r"[0-9a-f]{64}", files["plan.json"]):
        raise ValueError("실험 기록(record.json)에서 동결 기록 위치·plan.json SHA를 판별할 수 없다")
    base = "artifacts/experiments/" + eid + "/"
    return {"task_type": ANALYZE_TYPE, "inputs": {base + "record.json": done["manifest"]["record.json"],
                                                 base + "result.json": done["manifest"]["result.json"], base + "plan.json": files["plan.json"]},
            "outputs": [NEXT_PLAN], "depends_on": [exp_key], "needs_llm": True, "needs_vision": False, "risk": "low",
            "retry_policy": {}, "escalation_level": 0}


def _diff(old, new):
    """두 JSON 값이 다른 자리(키 경로 튜플) 목록. dict만 펼치고 그 밖은 JSON 글자로 비교한다(1 ≠ 1.0 ≠ true). 재귀 없음."""
    found, stack = [], [((), old, new)]
    while stack:
        path, a, b = stack.pop()
        if isinstance(a, dict) and isinstance(b, dict):
            stack.extend((path + (k,), a.get(k, _MISSING), b.get(k, _MISSING)) for k in set(a) | set(b))
        elif a is _MISSING or b is _MISSING or json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True):
            found.append(path)
    return sorted(found, key=repr)


def _head(source_root):
    """source_root의 git HEAD(소문자 16진). 판별할 수 없으면 Hold(waiting). 확정은 dedupe.verify_code가 한다."""
    env = dict({k: v for k, v in os.environ.items() if not k.startswith("GIT_")}, GIT_OPTIONAL_LOCKS="0")
    done = subprocess.run(["git", "-c", "core.fsmonitor=false", "-C", os.path.realpath(source_root), "rev-parse", "HEAD"], env=env,
                          capture_output=True, text=True, timeout=120, check=False)
    head = done.stdout.strip().lower()
    if done.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", head):
        raise Hold("waiting", "source_root HEAD를 읽지 못함")
    return head


def _derive(root, parent, analyze_key, source_root):
    """대조 계약(parent)과 분석의 next_plan.json → 다음 실험 계약. 위반은 Hold(refused), 확인할 수 없음은 Hold(waiting)."""
    cond = parent["run_conditions"]
    control, desc = (cond.get("config") or {}).get("plan"), cond.get("description")
    spec = control.get("experiment_parameter") if isinstance(control, dict) else None
    if not isinstance(spec, dict) or set(spec) != set(PARAM_KEYS) or not isinstance(control.get("reference_result"), str) \
            or not isinstance(control.get("acceptance"), dict) or not isinstance(desc, dict) \
            or not all(isinstance(desc.get(k), str) and desc[k].strip() for k in ("success_criterion", "failure_criterion")):
        raise Hold("waiting", "대조 실험에 승인 변수 experiment_parameter·사전 등록 기준(reference_result·acceptance·성공/실패 기준)이 없다")
    try:
        nxt = read_json(os.path.join(root, "tasks", analyze_key, "out", NEXT_PLAN), parse_int=dedupe.json_number)
    except ValueError as exc:
        raise Hold("refused", "next_plan.json이 JSON이 아니다: %s" % exc)
    if not isinstance(nxt, dict) or set(nxt) != set(PLAN_KEYS) or not isinstance(nxt["plan"], dict) \
            or not all(isinstance(nxt[k], str) and nxt[k].strip() for k in PLAN_KEYS[:4]):
        raise Hold("refused", "next_plan.json은 %s만(문구는 비지 않은 문자열, plan은 dict) 가진다" % (PLAN_KEYS,))
    changed = _diff(control, nxt["plan"])
    if changed != [VARIABLE] or nxt["variable"] != ".".join(VARIABLE):
        raise Hold("refused", "변수 하나(%s)가 아니다: 실제 차이 %s, 선언 %r" % (".".join(VARIABLE), [".".join(p) for p in changed[:5]],
                                                                   nxt["variable"][:80]))
    value = nxt["plan"]["experiment_parameter"]["value"]
    # float 범위 비교: int도 예외 없이 본다(D1: 거대 정수의 math.isfinite는 OverflowError. 기존 check_experiment_parameter도 받지 못하는 값)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not -sys.float_info.max <= value <= sys.float_info.max:
        raise Hold("refused", "experiment_parameter.value는 유한한 숫자여야 한다")
    if value == spec["baseline"] or value == spec["value"]:  # D2: 수로 비교(1 = 1.0). 기존 check_experiment_parameter는 baseline과 같은 값을 거절한다
        raise Hold("refused", "experiment_parameter.value가 baseline 또는 대조 실험 값과 같은 수다(자료형만 다른 같은 수 포함)")
    head = _head(source_root)
    new = dict(parent, depends_on=[analyze_key], run_conditions=dict(
        cond, code_sha=head, config=dict(cond["config"], plan=nxt["plan"]), hypothesis_id=nxt["hypothesis_id"],
        description=dict(desc, hypothesis=nxt["hypothesis"], change=nxt["change"])))
    try:
        trees = dedupe.verify_code(new, source_root, [cond["code_sha"].lower()])
    except ct.ContractError as exc:
        raise Hold("waiting", "코드를 확인할 수 없다: %s" % exc)
    if trees.get(cond["code_sha"].lower()) != trees[head]:
        raise Hold("waiting", "source_root 코드가 대조 실험과 다르다(두 번째 변수, 문서 docs/*.md 외 변경)")
    experiment_exec.build_plan(new)  # 실행 때와 같은 사전 등록 검사(문구 비어 있음 등은 ExperimentError)
    # D2: 같은 수의 다른 표기(2 ↔ 2.0, 정확히 같은 수일 때만). 기각 대조에만 쓴다(등록하는 계약은 new 하나)
    twins = [dict(new, run_conditions=dict(new["run_conditions"], config=dict(cond["config"], plan=dict(nxt["plan"], experiment_parameter=dict(
        nxt["plan"]["experiment_parameter"], value=form))))) for form in (float(value), int(value)) if form == value and type(form) is not type(value)]
    return [new] + twins


def _external(src, new):
    """원본 artifacts/experiments/*/의 ./experiment 기록(Codex ./review --auto·수동 실행 포함, 상태 무관) 중 new와 실행 조건이 같은 기록의 경로(없으면
    None, D4). 같음 = 설명 키를 뺀 동결 plan.json이 prepare와 같은 방식으로 만든 new의 계획과 ==(수는 값으로: 승인 변수 2 = 2.0), record.command가
    new의 command와 같고(자리표시자 {input:…} 자리는 실행 때 사본 경로로 바뀌므로 아무 값), record.source_hashes가 지금 원본 파일과 같음.
    판별할 수 없는 기록(record.json이 없는 실험 폴더, 읽을 수 없음, 형식·상태, plan.json이 record의 SHA와 다름, 같은 조건인데 코드 해시를 못 냄)이
    하나라도 있으면 Hold(waiting). 기록 형식의 근거는 card_condition/experiment_record.py(prepare·records) 코드뿐이다(실제 기록은 열어 보지 않았다).
    봉인 보호(2026-11-28 신뢰 경계 조사): Supervisor는 sandbox 밖이라, 봉인 경로 목록(harness/sealed_paths.json) 아래 실험 폴더·record.json·plan.json은 열기 전에
    seal_check로 걸러 건너뛴다(내용·해시 모두 안 읽음). source_hashes가 봉인 경로를 가리키는 기록은 해시하지 않고 Hold(waiting). 목록 오류도 Hold(waiting).
    건너뛴 폴더는 비교하지 않으므로 봉인 실험과 같은 조건의 새 계획은 못 잡는다(한계, 거절 쪽이 아니라 통과 쪽 공백).
    한계: ./experiment는 code_changes 파일 해시만 남기므로 그 밖 코드가 달라도 같다고 본다(거절 쪽). 회차마다 모든 기록을 읽는다(기록 수에 비례)."""
    base = os.path.join(src, "artifacts", "experiments")
    mine = {k: v for k, v in dict(experiment_exec.build_plan(new), **_FROZEN).items() if k not in _NOTES}
    command = new["run_conditions"]["command"]
    sealed = seal_check.load([claude_perm.REPO, src])  # 목록 오류는 ValueError → 그 계획만 대기(fail-closed)
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        folder = os.path.join(base, name)
        if any(seal_check.under(os.path.join(folder, part), sealed) for part in ("", "record.json", "plan.json")):
            continue  # 봉인 폴더·파일은 열지 않는다(Supervisor는 sandbox 밖). shortcut: 봉인 실험과 같은 조건의 새 계획은 못 알아본다(이름만으로는 비교 불가), 사용자가 봉인 해제·요약 자료를 정할 때 보완
        if not _EID.fullmatch(name) and not os.path.isfile(os.path.join(folder, "record.json")):
            continue  # experiment_record.records()처럼 */record.json이 기록이다(prepare 이름 형식 폴더는 record.json이 없어도 미완성 기록으로 본다)
        try:
            record, plan = read_json(os.path.join(folder, "record.json")), read_json(os.path.join(folder, "plan.json"))
            ok = isinstance(record, dict) and isinstance(plan, dict) and record.get("schema_version") == 1 and record.get("status") in _RECORD_STATUS \
                and isinstance(record.get("command"), list) and isinstance(record.get("source_hashes"), dict) \
                and record["files"]["plan.json"] == cas.sha_file(os.path.join(folder, "plan.json"))
            if ok and any(seal_check.under(os.path.join(src, p), sealed) for p in record["source_hashes"]):
                raise ValueError("source_hashes가 봉인 경로를 가리킨다")  # 해시하려고 봉인 파일을 열지 않는다: 판별 불가(대기)
            same = ok and {k: v for k, v in plan.items() if k not in _NOTES} == mine and len(record["command"]) == len(command) \
                and all(a == b or dedupe.PLACEHOLDER.search(b) for a, b in zip(record["command"], command)) \
                and all(cas.sha_file(os.path.join(src, p)) == h for p, h in record["source_hashes"].items())
        except (OSError, ValueError, LookupError, TypeError, AttributeError, RecursionError) as exc:
            raise Hold("waiting", "판별할 수 없는 ./experiment 기록 %s: %s" % (name, type(exc).__name__))
        if not ok:
            raise Hold("waiting", "판별할 수 없는 ./experiment 기록 %s: 형식(schema_version·status·command·source_hashes·plan.json SHA)" % name)
        if same:
            return "artifacts/experiments/" + name
    return None


def _screen(declared, infos, derived):
    """(register_missing에 넘길 선언, 거절 사유). LLM 작업에 직·간접 의존하는 미등록 실험·학습·평가 선언은 derived와 같을 때만 남긴다."""
    contracts = {k: c for k, (s, c) in infos.items() if c is not None}
    contracts.update({k: c for k, c in declared.items() if isinstance(c, dict) and k not in contracts})
    deps = {k: [d for d in c.get("depends_on") if isinstance(d, str)] if isinstance(c.get("depends_on"), list) else []
            for k, c in contracts.items()}
    tainted = {k for k, c in contracts.items() if c.get("needs_llm") is True}
    while True:
        more = {k for k in contracts if k not in tainted and any(d in tainted for d in deps[k])}
        if not more:
            break
        tainted |= more
    kept, notes = {}, {}
    for key, task in declared.items():
        gated = isinstance(task, dict) and task.get("task_type") in dedupe.CONDITION_TYPES and key not in infos \
            and any(d in tainted for d in deps.get(key, []))
        if gated and not (len(deps[key]) == 1 and derived.get(deps[key][0]) == task):
            notes[str(key)] = "plan_gate_required: LLM 작업 출력에 의존하는 실험·학습·평가 선언은 PLAN_GATE가 만든 계약과 같아야 한다"
            continue
        kept[key] = task
    return kept, notes


def gate(root, declared, now, source_root=None):
    """declared(선언 파일 내용) → register_missing에 넘길 선언. 새 ANALYZE·다음 실험 선언을 declared.json에 더한다. dict가 아니면 그대로."""
    if not isinstance(declared, dict):
        return declared
    src, tasks_dir, infos = source_root or claude_perm.REPO, os.path.join(root, "tasks"), {}
    for key in sorted(os.listdir(tasks_dir)) if os.path.isdir(tasks_dir) else []:
        if re.fullmatch(r"[0-9a-f]{64}", key):
            info = states.facts(os.path.join(tasks_dir, key))
            infos[key] = (states.state_of(info, False), info["contract"])
    lined = {d.get("task_key") for d in ledger.events(os.path.join(root, "ledger.jsonl"), "plan_gate_declared") if isinstance(d, dict)}
    # 관문을 통과해(장부 줄) 등록된 다음 실험이 있는 분석만 다시 보지 않는다(D3: 관문 밖 등록이 계보를 막지 못하게, 그런 실험은 runner가 실행하지 않는다)
    children = {d for k, (s, c) in infos.items() if c is not None and c["task_type"] in dedupe.CONDITION_TYPES and k in lined for d in c["depends_on"]}
    added, derived, notes = {}, {}, {}
    for key, (state, task) in infos.items():
        if state != states.VERIFIED or task is None:
            continue
        try:
            if task["task_type"] == "experiment" and sorted(task["outputs"]) == sorted(experiment_exec.OUTPUTS):
                analyze = _analyze(key, os.path.join(tasks_dir, key))
                if ct.task_key(analyze) not in infos and ct.task_key(analyze) not in declared:
                    added[ct.task_key(analyze)] = analyze
            elif task["task_type"] == ANALYZE_TYPE and len(task["depends_on"]) == 1 and key not in children:
                pstate, parent = infos.get(task["depends_on"][0], (None, None))
                if pstate != states.VERIFIED or parent is None or parent["task_type"] != "experiment" \
                        or _analyze(task["depends_on"][0], os.path.join(tasks_dir, task["depends_on"][0])) != task:
                    continue  # 하네스가 만든 분석이 아니다: 그 출력은 계획으로 보지 않는다
                forms = _derive(root, parent, key, src)
                new = forms[0]
                if budget.usage(root, "experiment", budget.period_of("experiment", now)) + 1 > budget.LIMITS["experiment"][1]:
                    raise Hold("waiting", "이번 주 실험 예산이 남지 않았다(실행 직전 차감은 runner, 여기서는 읽기만)")
                dup = next(filter(None, (dedupe.find_duplicate(root, form, ct.task_key(new), src, strict=True) for form in forms)), None) \
                    or _external(src, new)  # D4: 비교할 수 없는 하네스 기록은 대기(strict), 하네스 밖 ./experiment 기록도 대조
                if dup is not None:
                    raise Hold("refused", "기각·중복 가설: 같은 실행 조건의 실험이 이미 있다(가설 ID·설명 무관) %s" % dup)
                derived[key] = new
                if ct.task_key(new) not in declared:
                    added[ct.task_key(new)] = new
        except Hold as exc:
            notes["plan:" + key] = "%s: %s" % exc.args
        except _PLAN_ERRORS as exc:
            notes["plan:" + key] = "waiting: %s: %s" % (type(exc).__name__, str(exc)[:200])
    kept, screened = _screen(dict(declared, **added), infos, derived)
    if added:
        try:
            write_json(os.path.join(root, "supervisor", "declared.json"), dict(declared, **added))
        except ValueError as exc:  # 사용자 선언에 JSON으로 적을 수 없는 값(NaN 등): 파일은 그대로 두고 알린다
            notes["<declared.json>"] = "plan_gate_write_skipped: %s" % str(exc)[:200]
    # 관문 통과 줄(D3: runner가 실행 직전 확인). declared.json 저장 뒤, 등록 전. 이번 회차에 통과한 선언 중 줄이 없는 것만 쓴다:
    # 저장 뒤·줄 전 kill이면 다음 회차의 같은 파생(결정론)이 줄을 채우고, 줄 뒤 kill이면 다시 쓰지 않는다
    for key, task in sorted(dict(added, **{ct.task_key(n): n for n in derived.values()}).items()):
        if key not in lined:
            ledger.append(os.path.join(root, "ledger.jsonl"), now, "plan_gate_declared", {
                "task_key": key, "task_type": task["task_type"], "depends_on": task["depends_on"],
                "value": task.get("run_conditions", {}).get("config", {}).get("plan", {}).get("experiment_parameter", {}).get("value"),
                "code_sha": task.get("run_conditions", {}).get("code_sha")})
    graph.note_rejected(root, dict(notes, **screened), now)
    return kept
