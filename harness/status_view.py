"""status.collect 결과의 모바일 요약(B6-2): 채팅에 붙일 짧은 텍스트(MAX_LINES줄 이하)와 같은 내용의 정적 HTML(JS·외부 자원 없음).

모든 줄은 _clean 한 곳을 지난다: 비밀 모양 값 가림(evidence.mask, 최선 노력) → 홈 폴더 경로 가림 → 한 줄로 접기 → WIDTH자로 자르기.
사람에게 보여 주는 표시일 뿐이며 어떤 상태도 바꾸지 않는다. 호출 깊이: render_html → render_text → _clean → evidence.mask 3.
"""
import html
import os
import re
import time

from . import evidence, opstate

WIDTH = 160
MAX_LINES = 20  # render_text의 줄 구성이 지키는 상한(조건 3 + 대기 항목 2 + 알림 3)
LABELS = {opstate.INTEGRITY_HALT: "무결성 정지", opstate.USER_STOPPED: "사용자 중단", opstate.DONE: "종료",
          opstate.BUDGET_EXCEEDED: "개발 예산 초과", opstate.RATE_LIMITED_SHORT: "사용량 한도(단기)",
          opstate.RATE_LIMITED_WEEKLY: "사용량 한도(주간)", opstate.RATE_LIMITED_UNKNOWN: "사용량 한도(종류 미상)",
          opstate.RUNNING: "정지 조건 없음"}
TODO = {opstate.INTEGRITY_HALT: "무결성 정지 원인 확인", opstate.USER_STOPPED: "사용자 중단 해제는 사용자만(해제 명령은 아직 없음)",
        opstate.DONE: "종료 상태 확인", opstate.BUDGET_EXCEEDED: "예산 재승인 여부 결정"}


def _clean(text, width=WIDTH):
    text = str(text)[:4000]
    text = evidence.mask(text, 4 * len(text) + 20)  # limit을 넉넉히: mask는 끝부분을 남기므로 앞이 잘리지 않게
    text = re.sub(r"/(?:Users|home)/[^/\s'\"]+", "~", text.replace(os.path.expanduser("~"), "~"))
    text = " ".join(text.split())
    return text if len(text) <= width else text[:width - 1] + "…"


def _when(value):
    try:
        return time.strftime("%m-%d %H:%M %Z", time.localtime(value))
    except (TypeError, ValueError, OverflowError, OSError):
        return "시각 불명"


def _resume(report):
    """자동 재개 한 줄. 자동으로 풀리는 것은 사용량 한도 조건뿐이다(정지 조건이 있으면 그것도 안 풀린다)."""
    if report["state"] in opstate.HALTING:
        return "자동 재개: 없음(정지 조건이 있는 동안 Supervisor는 아무것도 시작하지 않고, 정지는 자동으로 풀리지 않음)"
    if report["state"] not in opstate.RATE_LIMITED:
        return "자동 재개: 대기 중인 한도 없음"
    gate = report["conditions"][report["state"]]
    if gate.get("exhausted"):
        return "자동 재개: 없음(시각 미상 한도 3회 소진)"
    if gate.get("next_try_at") is None:
        return "자동 재개: 없음(재개 시각 기록 없음)"
    left = max(0, gate["next_try_at"] - report["now"])
    note = "" if report["supervisor_running"] else " · Supervisor가 실행 중이 아니라 켜기 전에는 재개되지 않음"
    return "자동 재개: 한도 다음 시도 %s(약 %.0f분 뒤)%s" % (_when(gate["next_try_at"]), min(left / 60.0, 1e6), note)


def render_text(report):
    """status.collect 결과 → 여러 줄 문자열."""
    tasks, conds = report["tasks"], report["conditions"]
    state = report["state"]
    effect = " · 새 작업을 시작하지 않음" if state in opstate.HALTING else \
        " · Claude 작업만 멈춤" if state in opstate.RATE_LIMITED else ""
    lines = ["[하네스 상태] 운영 상태 표시(모델 성능·정확도 아님) · 조회 %s" % _when(report["now"]),
             "상태: %s(%s)%s%s" % (LABELS[state], state, effect,
                                   " · 운영 상태 파일 손상·읽기 실패" if report["unreadable"] else ""),
             "Supervisor: %s" % {True: "실행 중(잠금 확인, pid·시작 시각은 알 수 없음)", False: "실행 중 아님",
                                 None: "실행 여부 확인 불가"}[report["supervisor_running"]]]
    names = sorted(conds, key=opstate.LEVEL.__getitem__)
    for i, name in enumerate(names[:3]):
        more = " (외 %d개)" % (len(names) - 3) if i == 2 and len(names) > 3 else ""
        info = conds[name]
        lines.append("- %s%s %s %s: %s" % (LABELS[name], more, _when(info.get("since")), info.get("actor", "?"),
                                           info.get("reason", "")))
    jobs = [j for j in report["claude_jobs"] if j["status"] in ("blocked", "failed", "stale", "unreadable")]
    waits = [("결과 확인 대기", t["task_key"], t["detail"]) for t in tasks["awaiting"]] \
        + [("중단 한도 정지", t["task_key"], t["detail"]) for t in tasks["stopped"]]
    items = ["  %s %s: %s" % (kind, key[:12], detail.get("reason", detail) if isinstance(detail, dict) else detail)
             for kind, key, detail in waits] \
        + ["  Claude %s %s: %s" % (j["status"], j["task_key"][:12], j["hold_reason"]) for j in jobs] \
        + ["  계약 손상 %s" % k[:12] for k in tasks["bad_contract"]] \
        + ["  읽기 실패 %s: %s" % (k[:12], v) for k, v in tasks["errors"].items()]
    broken = [label for label, value in (("작업 장부", report["ledgers"]["ledger"]),
                                         ("알림 장부", report["ledgers"]["notifications"])) if value != 0]
    broken += ["예산 장부"] if any("error" in v for v in report["budget"].values()) else []
    todo = [TODO[n] for n in names if n in TODO]
    todo += ["한도 3회 소진: 사람 확인"] if any(conds[n].get("exhausted") for n in names) else []
    todo += ["대기·실패 항목 %d건 확인" % len(items)] if items else []
    todo += ["%s 확인" % "·".join(broken)] if broken else []
    lines += ["사람이 할 일: %s" % ("; ".join(todo) or "없음"), _resume(report),
              "작업: %s" % (" · ".join("%s %d" % kv for kv in sorted(tasks["counts"].items())) or "등록 없음"),
              "확인 대기: 결과 확인 %d · 중단 한도 정지 %d · Claude 대기 %d · 계약 손상 %d · 읽기 실패 %d" % (
                  len(tasks["awaiting"]), len(tasks["stopped"]), len(jobs), len(tasks["bad_contract"]), len(tasks["errors"]))]
    lines += items[:2]
    limit = report["unknown_limit"]
    spent = [] if limit is None else [limit.get("error") or "시각 미상 한도 시도 %d/%d" % (limit["attempts"], limit["max"])]
    money = ["%s %s" % (label, "장부 오류" if "error" in v else "%d/%d(남음 %d)" % (v["used"], v["limit"], v["limit"] - v["used"]))
             for label, v in (("실험", report["budget"]["experiment"]), ("비전 구역", report["budget"]["vision_zone"]))]
    lines.append(" · ".join(["예산(이번 주): " + " · ".join(money)] + spent))
    ledgers = ["%s %s" % (label, "정상" if v == 0 else "문제 %s건" % v if type(v) is int else "읽기 실패(%s)" % v)
               for label, v in (("작업 장부", report["ledgers"]["ledger"]), ("알림 장부", report["ledgers"]["notifications"]))]
    lines.append("장부: " + " · ".join(ledgers))
    lines.append("최근 알림:" if report["notifications"] else "최근 알림: 없음")
    lines += ["  %s %s %s" % (_when(n["ts"]), n["kind"], n["message"]) for n in report["notifications"]]
    out = []
    for row in lines:  # 들여쓰기는 유지하고 내용만 정리한다
        indent = len(row) - len(row.lstrip(" "))
        out.append(" " * indent + _clean(row, WIDTH - indent))
    return "\n".join(out)


def render_html(report):
    """render_text와 같은 줄을 담은 정적 HTML 한 장(JS 없이 폰에서 읽힘). 모든 줄은 이스케이프한다."""
    body = "\n".join("<p>%s</p>" % html.escape(row) for row in render_text(report).split("\n"))
    return ('<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>하네스 상태</title>\n'
            "<style>:root{color-scheme:light dark}body{font-size:16px;line-height:1.5;margin:16px;font-family:sans-serif}"
            "p{margin:0 0 6px;white-space:pre-wrap;overflow-wrap:anywhere}p:first-child{font-weight:700}</style>\n"
            "</head>\n<body>\n" + body + "\n</body>\n</html>\n")
