"""설치된 `claude` CLI가 모델·effort 지정을 지원하는지 `claude --help`(읽기 전용, 모델 호출 아님)로 확인하고,
지원되지 않거나 확인하지 못한 설정은 조용히 무시하지 않고 applied(실제 적용값)·limitations(제한 사항)로 기록한다.

이 단계에서는 실제 `claude -p` 실행 전이므로 applied.verified는 항상 False다(T7은 실제 적용을 확인한 뒤에만 통과).
"""
import re
import subprocess

_HELP = ["claude", "--help"]


def _run_help(argv):
    done = subprocess.run(argv, capture_output=True, text=True, timeout=30, check=False)
    return done.returncode, done.stdout + done.stderr


def _block(text, flag):
    """도움말에서 flag 옵션의 설명 덩어리(옵션 줄 + 이어지는 들여쓴 줄). 없으면 None."""
    lines, out = text.splitlines(), None
    for line in lines:
        if out is None:
            if re.match(r"\s+(-\w, )?%s(\s|$)" % re.escape(flag), line):
                out = [line]
        elif line.strip() and not line.lstrip().startswith("-") and len(line) - len(line.lstrip()) >= 12:
            out.append(line)
        else:
            break
    return " ".join(x.strip() for x in out) if out else None


def probe_cli_support(run=None):
    """확인 결과 dict. 실행 함수 run(argv) -> (종료코드, 출력)은 주입 가능(시험용). 확인하지 못한 항목은 None(미확인)."""
    result = {"status": "ok", "command": list(_HELP), "model_option": None, "effort_option": None,
              "effort_levels": None, "model_examples": None, "error": None}
    try:
        code, text = (run or _run_help)(list(_HELP))
    except (OSError, subprocess.SubprocessError) as exc:
        return dict(result, status="failed", error="%s: %s" % (type(exc).__name__, exc))
    if code != 0 or not str(text).strip():
        return dict(result, status="failed", error="종료 코드 %r 또는 빈 출력" % (code,))
    model, effort = _block(text, "--model"), _block(text, "--effort")
    levels = re.search(r"\(([a-z]+(?:, ?[a-z]+)+)\)", effort) if effort else None
    return dict(result, model_option=model is not None, effort_option=effort is not None,
                effort_levels=[x.strip() for x in levels.group(1).split(",")] if levels else None,
                model_examples=re.findall(r"'([A-Za-z0-9._-]+)'", model) if model else None)


def with_support(decision, support):
    """결정에 applied({model, effort, verified})와 limitations(문자열 목록)를 덧붙인 새 결정."""
    new = dict(decision)
    applied = {"model": decision["model"], "effort": decision["effort"], "verified": False}
    if not decision["needs_llm"]:
        new.update(applied={"model": None, "effort": None, "verified": None}, limitations=[])
        return new
    limits = ["actual_application_unverified: claude -p 실행 뒤에야 실제 적용 확인(T7 통과 아님)"]
    if support.get("status") != "ok":
        applied.update(model=None, effort=None)
        limits.append("cli_probe_failed: %s — 적용 가능 여부 미확인, 값 미적용으로 기록" % support.get("error"))
    else:
        _check(decision, support, applied, limits)
    new.update(applied=applied, limitations=limits)
    return new


def _check(decision, support, applied, limits):
    """옵션·값 지원 여부를 대조해 applied와 limits를 고친다(지원 안 되면 값을 비우고 이유를 남긴다)."""
    if not support.get("model_option"):
        applied["model"] = None
        limits.append("model_option_missing: --model 옵션 없음(요청 %s 미적용)" % decision["model"])
    elif support.get("model_examples") is not None and decision["model"] not in support["model_examples"]:
        limits.append("model_value_unconfirmed: %s는 도움말 예시에 없음(수용 여부 미확인)" % decision["model"])
    if not support.get("effort_option"):
        applied["effort"] = None
        limits.append("effort_option_missing: --effort 옵션 없음(요청 %s 미적용)" % decision["effort"])
    elif support.get("effort_levels") is None:
        limits.append("effort_values_unconfirmed: 도움말에서 effort 수준 목록을 읽지 못함")
    elif decision["effort"] not in support["effort_levels"]:
        applied["effort"] = None
        limits.append("effort_value_unsupported: %s는 지원 목록 %s에 없음" % (decision["effort"], support["effort_levels"]))
    if decision["effort"] == "xhigh":
        limits.append("xhigh_model_combo_unconfirmed: %s + xhigh 조합의 실제 수용은 미확인" % decision["model"])
