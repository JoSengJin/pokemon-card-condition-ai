"""`./experiment` 실행 어댑터(B5-8, 합성 단계). **실제 ./experiment 연결: 미완료.** executor 표 EXECUTORS(`harness.experiment_exec:EXECUTORS`,
Supervisor `--executors`)에 등록했다. runner가 sandbox 안에서 부르므로 저장소 artifacts/ 쓰기가 막혀 실험 기록을 남기는 실행은 결과 불명이 된다
(sandbox 원칙 유지, 진입점 시험 tests/test_harness_b5_experiment_run_faults가 고정).

사용자 결정(2026-11-28): B5는 실행 어댑터 계약과 합성 시험까지 하고 기존 sandbox 보안 원칙(executor는 실행별 staging에만 쓴다)을 유지한다.
실제 연결(저장소 artifacts/ 쓰기·workspace.lock이 필요해 sandbox 밖 실행이 된다)의 최소 권한·실행 경로는 첫 실험 후보 승인 때 검토한다
(초안: docs/collaboration/tasks/harness-b5-indep-20261128.md). 합성 시험 통과는 실제 실험 실행부터 다음 가설 생성까지의 검증이 아니다.

계약(task_type "experiment", outputs = OUTPUTS):
- 실행 파일은 계약이 아니라 어댑터가 정한다: <workdir>/experiment. 계약 command는 `--` 뒤에만 붙는다(옵션 주입 불가).
- 계획 JSON은 계약에서만 만든다: run_conditions.config.plan(실행 조건: reference_result·acceptance·code_changes 등, 논리 키에 들어감)
  + 설명 키 hypothesis_id·description{hypothesis, change, success_criterion, failure_criterion}(논리 키에서 빠짐: 문구만 다른 같은 실험은
  dedupe가 중복으로 거절). config.plan이 설명 키를 덮어쓰면 거절. 그 밖의 plan 내용 검사는 ./experiment(prepare)가 한다.
- 실행 전 code_sha 대조(dedupe.verify_code, 추적 파일 변경도 거절)는 sandbox 밖 runner가 한다(runner._execute). sandbox는 저장소 git 폴더 읽기를
  거절하므로(봉인 파일이 git 객체에 있다) 어댑터는 git을 쓰지 않는다: runner가 verify_code 직후 record_code로 code_sha 커밋의 파일별 git blob SHA를
  <작업 폴더>/code-check.json(sandbox가 쓰지 못하는 고정 위치, 경로는 runner가 넣는 환경변수 CHECK_ENV)에 쓰고, 어댑터(execute)는 check_code로 그
  파일만 읽어 code_sha·source_root가 이 실행과 같은지, 목록의 모든 추적 파일이 지금 내용(blob SHA 재계산)과 같은지 본다(검증 뒤 실행 대상 변경 차단).
  파일 없음·링크·형식 오류·불일치·읽기 실패는 refused(실행 안 함). 봉인 경로 목록 아래 추적 파일은 sandbox가 읽을 수 없어 목록에서 빼고
  sealed_skipped에 남긴다(목록은 artifacts/ 아래 자료뿐이고 실행 코드가 아니다: tests/test_harness_code_check). 계약 필드는 이 결과에 쓰이지 않는다.
  run()을 직접 부르면(시험·runner 밖) 예전처럼 verify_code를 직접 한다.
- 결과 해석(interpret): 종료 코드와 record.json 상태가 함께 맞아야 한다. 0+completed(+result.json 해시가 record files와 같음) = 완료,
  1+failed = 실험 자체 실패(결정적), 128 초과+interrupted = 중단, 출력에 기록 줄이 없고 1(잠금 사용 중)·2(계획 오류) 안내문이며 실행 전후
  workdir/artifacts/experiments 목록이 같음 = 실행 안 됨(not_started: 예산 차감 취소 대상, 결정 3. 실제 ./experiment는 prepare가 실험 폴더를 만든 뒤
  명령을 실행하고, 그 뒤의 OSError·ValueError에도 2 안내문을 내므로 목록이 바뀌면 결과 불명이다). 그 밖(불일치·running·기록 경로가
  workdir/artifacts/experiments 밖·명령/가설 불일치·시간 초과·신호로 죽음)은 결과 불명(unknown). refused(계약 거절)도 실험 프로세스를 띄우기 전이다.
- 외부 AI 검토 차단(A4): 자식 환경에 CARD_CONDITION_AUTO_CHILD=1(card_condition/development_review.enabled()가 False) + config.plan에
  gemini_calls_allowed·codex_model_calls_allowed가 정수 0이 아니면 거절(refused).
- 오류는 ExperimentError(종류, {"status", ...}). 종류는 runner 실패 종류와 같다(recovery.kind_of가 args[0]을 쓴다): deterministic(거절·실패·
  not_started), interrupted(중단·결과 불명: 작업권을 남겨 INTERRUPTED → 결과 확인 전 대기. 재실행 안전 목록은 비어 있어 자동 재실행되지 않는다).
  sandbox 안에서는 sandbox_child가 종류와 status를 결과 줄로 넘긴다(sandbox.ChildError.kind·status).
- workdir: runner가 실행 직전 code_sha를 대조한 source_root(환경변수 SOURCE_ENV, runner가 넣는다). 없으면 refused.
한계: 시간 초과 때 subprocess.run은 직접 자식만 죽인다(실제 ./experiment가 띄운 프로세스 그룹은 남을 수 있다 → 결과 불명으로 둔다).
호출 깊이: execute → run → interpret → cas.sha_file (3), run → dedupe.verify_code (1), run → build_plan (1), execute → check_code (1),
runner._execute → record_code → claude_perm.sealed_paths·jsonio.write_json (runner.main 기준 4).
"""
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess

from . import cas, claude_perm, dedupe
from .contract import ContractError
from .jsonio import write_json

OUTPUTS = ("plan.json", "record.json", "result.json")
TEXT_KEYS = ("hypothesis", "change", "success_criterion", "failure_criterion")
_LINE = re.compile(r"^실험 기록: (.+) / 상태: (\S+)$", re.M)
_NOT_STARTED = {1: "다른 개발·실험·검토가 진행 중입니다", 2: "실험 계획·기준 결과·코드 경로를 확인하세요"}
_ENV = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "en_US.UTF-8", "PYTHONIOENCODING": "utf-8",
         "CARD_CONDITION_AUTO_CHILD": "1"}  # A4: development_review.enabled()를 끈다(./review --auto의 Codex·Gemini 호출 차단, 설정·세션 ID와 무관)
NO_AI_KEYS = ("gemini_calls_allowed", "codex_model_calls_allowed")
SOURCE_ENV = "HARNESS_SOURCE_ROOT"
CHECK_ENV, CHECK_NAME = "HARNESS_CODE_CHECK", "code-check.json"  # runner가 넣는 환경변수(경로), 작업 폴더 안 고정 파일 이름
MODES = ("100644", "100755", "120000")  # 추적 파일 모드(일반·실행·링크). 폴더 안 submodule(160000) 등은 검증 못 하므로 거절


class ExperimentError(Exception):
    """args = (종류 deterministic|interrupted, {"status": refused|failed|not_started|interrupted|unknown, "detail": ...})."""

    @property
    def status(self):
        """args[1]의 status(없으면 None). runner는 not_started·refused일 때만 이 시도의 예산 차감을 취소한다."""
        return self.args[1].get("status") if len(self.args) > 1 and isinstance(self.args[1], dict) else None


def build_plan(task):
    """계약 → 계획 dict. 형식이 맞지 않으면 ExperimentError(deterministic, refused). 말단."""
    cond = task.get("run_conditions") if isinstance(task.get("run_conditions"), dict) else {}
    plan, text = (cond.get("config") or {}).get("plan"), cond.get("description")
    if not isinstance(plan, dict) or not plan or set(plan) & set(TEXT_KEYS + ("hypothesis_id",)):
        raise ExperimentError("deterministic", {"status": "refused", "detail": "config.plan이 없거나 설명 키를 덮어쓴다"})
    if not isinstance(text, dict) or set(text) != set(TEXT_KEYS) or not all(isinstance(v, str) and v.strip() for v in text.values()) \
            or not isinstance(cond.get("hypothesis_id"), str) or not cond["hypothesis_id"].strip():
        raise ExperimentError("deterministic", {"status": "refused", "detail": "hypothesis_id·description(%s)이 필요하다" % (TEXT_KEYS,)})
    if any(type(plan.get(key)) is not int or plan[key] != 0 for key in NO_AI_KEYS):  # bool·"0"·0.0 거절, 계획을 몰래 바꾸지 않는다(fail-closed)
        raise ExperimentError("deterministic", {"status": "refused", "detail": "계획에 %s가 정수 0으로 있어야 한다" % (NO_AI_KEYS,)})
    return dict(plan, hypothesis_id=cond["hypothesis_id"], **text)


def interpret(code, stdout, workdir, command, hypothesis_id):
    """(상태, 실험 폴더 또는 None). 상태: completed|failed|interrupted|not_started|unknown. 말단에 가깝다(cas.sha_file만 부른다)."""
    found = _LINE.findall(stdout or "")
    if not found:
        hint = _NOT_STARTED.get(code)
        return ("not_started" if hint and hint in (stdout or "") else "unknown"), None
    if len(found) != 1:
        return "unknown", None
    path, said = found[0]
    base = os.path.realpath(os.path.join(workdir, "artifacts", "experiments"))
    folder = os.path.dirname(os.path.realpath(path))
    if os.path.basename(path) != "record.json" or os.path.dirname(folder) != base or os.path.islink(path) or not os.path.isfile(path):
        return "unknown", None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, ValueError):
        return "unknown", None
    if not isinstance(record, dict) or record.get("schema_version") != 1 or record.get("status") != said \
            or record.get("command") != command or record.get("hypothesis_id") != hypothesis_id:
        return "unknown", None
    result = os.path.join(folder, "result.json")
    if said == "completed" and code == 0 and os.path.isfile(result) and not os.path.islink(result) \
            and cas.sha_file(result) == (record.get("files") or {}).get("result.json"):
        return "completed", folder
    if (said, code) == ("failed", 1):
        return "failed", folder
    if said == "interrupted" and code > 128:
        return "interrupted", folder
    return "unknown", folder


def record_code(task, task_dir, source_root):
    """runner(sandbox 밖)가 verify_code 직후 부른다. code_sha 커밋의 파일별 {경로: [모드, git blob SHA]}를 <task_dir>/code-check.json에 쓰고 그
    경로를 돌려준다(sandbox는 작업 폴더에 쓰지 못한다). 봉인 경로 목록 아래 파일은 sandbox가 읽을 수 없어 files에서 빼고 sealed_skipped에 남긴다.
    git을 못 읽거나 submodule 같은 모드가 있으면 예외(runner가 실행하지 않는다). 말단."""
    top, sha = os.path.realpath(source_root), str(task["run_conditions"]["code_sha"]).lower()
    if not dedupe._SHA.fullmatch(sha):
        raise ValueError("code_sha 형식이 틀렸다")
    env = dict({k: v for k, v in os.environ.items() if not k.startswith("GIT_")}, GIT_OPTIONAL_LOCKS="0")
    shown = subprocess.run(["git", "-c", "core.fsmonitor=false", "-C", top, "ls-tree", "-r", "-z", "--full-tree", sha + "^{tree}"], env=env,
                           capture_output=True, timeout=120, check=False)
    if shown.returncode != 0:
        raise ValueError("code_sha 커밋의 파일 목록을 읽지 못함")
    sealed, files, skipped = claude_perm.sealed_paths([claude_perm.REPO, top]), {}, []
    for entry in filter(None, shown.stdout.split(b"\0")):
        meta, _, rel = entry.decode("utf-8").partition("\t")
        mode, kind, blob = meta.split(" ")
        if kind != "blob" or mode not in MODES:
            raise ValueError("검증할 수 없는 추적 항목(%s %s): %s" % (mode, kind, rel))
        spot = os.path.join(top, rel)
        if any(os.path.commonpath([spot, s]) == s for s in sealed):
            skipped.append(rel)
        else:
            files[rel] = [mode, blob]
    path = os.path.join(os.path.realpath(task_dir), CHECK_NAME)
    write_json(path, {"code_sha": sha, "source_root": top, "files": files, "sealed_skipped": sorted(skipped)})
    return path


def check_code(task, workdir):
    """어댑터(sandbox 안)가 실행 직전 부른다. runner가 쓴 code-check.json(경로는 환경변수 CHECK_ENV만, 계약 필드는 쓰지 않는다)을 O_NOFOLLOW로
    읽어 code_sha·source_root가 이 실행과 같고 files의 모든 파일이 지금 내용·모드(blob SHA 재계산, git 없음)와 같으며 실행 파일 experiment가 목록에
    있는지 본다. 하나라도 어긋나거나 읽을 수 없으면 ExperimentError(deterministic, refused). 말단."""
    path, top = os.environ.get(CHECK_ENV), os.path.realpath(workdir)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as handle:
            seen = os.fstat(fd)
            data = json.loads(handle.read().decode("utf-8")) if stat.S_ISREG(seen.st_mode) and seen.st_nlink == 1 else None
        files = data["files"]
        if os.path.basename(path) != CHECK_NAME or os.path.realpath(path) != path or set(data) != {"code_sha", "source_root", "files", "sealed_skipped"} \
                or data["code_sha"] != str(task["run_conditions"]["code_sha"]).lower() or data["source_root"] != top \
                or not isinstance(files, dict) or "experiment" not in files or not isinstance(data["sealed_skipped"], list):
            raise ValueError("code-check 내용이 이 실행과 맞지 않는다")
        for rel, (mode, blob) in files.items():
            if mode not in MODES or os.path.isabs(rel) or ".." in rel.split("/"):
                raise ValueError("code-check 항목 형식 오류: %r" % (rel,))
            spot = os.path.join(top, rel)
            if mode == "120000":
                target = os.fsencode(os.readlink(spot))
                digest = hashlib.sha1(b"blob %d\0" % len(target) + target)
            else:
                digest = hashlib.sha1()
                with open(os.open(spot, os.O_RDONLY | os.O_NOFOLLOW), "rb") as handle:
                    seen = os.fstat(handle.fileno())
                    digest.update(b"blob %d\0" % seen.st_size)
                    chunk = handle.read(1 << 20)
                    while chunk:
                        digest.update(chunk)
                        chunk = handle.read(1 << 20)
                    if bool(seen.st_mode & 0o100) != (mode == "100755") or not stat.S_ISREG(seen.st_mode):
                        raise ValueError("모드 불일치: %s" % rel)
            if digest.hexdigest() != blob:
                raise ValueError("검증 뒤 내용이 바뀌었다: %s" % rel)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ExperimentError("deterministic", {"status": "refused", "detail": "code_sha 확인 결과(code-check)를 믿을 수 없다: %s: %s" % (type(exc).__name__, exc)})


def run(task, out_dir, workdir, timeout=None, checked=False):
    """계약의 실험 하나를 <workdir>/experiment로 실행한다. 완료면 OUTPUTS(out_dir 안 사본) 목록, 아니면 ExperimentError.
    checked=True(execute만)면 code_sha 대조를 runner 결과(check_code)로 이미 했다."""
    if task.get("task_type") != "experiment" or sorted(task.get("outputs") or []) != sorted(OUTPUTS):
        raise ExperimentError("deterministic", {"status": "refused", "detail": "experiment 유형·outputs %s만 받는다" % (OUTPUTS,)})
    plan = build_plan(task)
    try:
        if not checked:
            dedupe.verify_code(task, workdir)  # 실행 직전 code_sha = workdir HEAD, 추적 파일 변경 없음
    except ContractError as exc:
        raise ExperimentError("deterministic", {"status": "refused", "detail": str(exc)})
    command = task["run_conditions"]["command"]
    write_json(os.path.join(out_dir, "plan.json"), plan)
    base = os.path.join(workdir, "artifacts", "experiments")
    seen = sorted(os.listdir(base)) if os.path.isdir(base) else None  # 실행 전 실험 폴더 목록(not_started 확인용)
    argv = [os.path.join(workdir, "experiment"), "--plan", os.path.join(os.path.abspath(out_dir), "plan.json"), "--"] + list(command)
    try:
        done = subprocess.run(argv, cwd=workdir, env=_ENV, stdin=subprocess.DEVNULL, capture_output=True, encoding="utf-8",
                              errors="replace", timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        raise ExperimentError("interrupted", {"status": "unknown", "detail": "time_budget"})
    except OSError as exc:  # 실행 파일을 띄우지 못함: 실행되지 않았음이 확인된 경우
        raise ExperimentError("deterministic", {"status": "not_started", "detail": str(exc)})
    status, folder = interpret(done.returncode, done.stdout, workdir, list(command), plan["hypothesis_id"])
    if status == "not_started" and (sorted(os.listdir(base)) if os.path.isdir(base) else None) != seen:
        status = "unknown"  # 안내문이 있어도 새 실험 폴더가 생겼다: 실행되지 않았음을 확정할 수 없다
    info = {"status": status, "return_code": done.returncode, "experiment_dir": folder}
    if status == "completed":
        for name in ("record.json", "result.json"):
            shutil.copyfile(os.path.join(folder, name), os.path.join(out_dir, name))
        with open(os.path.join(out_dir, "record.json"), "r", encoding="utf-8") as handle:  # 사본을 다시 대조(해석과 복사 사이 변경)
            copied = json.load(handle)
        if copied.get("status") == "completed" and cas.sha_file(os.path.join(out_dir, "result.json")) == copied["files"].get("result.json"):
            return list(OUTPUTS)
        info["status"] = "unknown"
    raise ExperimentError("deterministic" if status in ("failed", "not_started") else "interrupted", info)


def execute(task, out_dir):
    """executor 표 항목(runner 계약 (contract, out_dir) -> 출력 목록). workdir = runner가 넣은 SOURCE_ENV(대조한 source_root)."""
    workdir = os.environ.get(SOURCE_ENV)
    if not workdir:
        raise ExperimentError("deterministic", {"status": "refused", "detail": "%s 없음(runner 밖에서 불림)" % SOURCE_ENV})
    check_code(task, workdir)
    return run(task, out_dir, workdir, checked=True)


EXECUTORS = {"experiment": execute}
