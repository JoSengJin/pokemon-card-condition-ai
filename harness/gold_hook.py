"""UserPromptSubmit 훅의 처리(DESIGN 5-2의 3, 13절). 모델보다 먼저 사용자 원문을 받아 Gold 저장 또는 중단 플래그를 기록한다.

훅 규약의 근거: 설치본 Claude Code 2.1.310 실행 파일에 내장된 설명 문자열을 읽어 확인했다(실행 검증은 아니다).
  입력 JSON에 hook_event_name="UserPromptSubmit"과 prompt가 있다. 종료 코드 0이면 표준출력이 Claude에게 전달된다.
  종료 코드 2는 처리를 막고 원래 프롬프트를 지우며 stderr를 사용자에게만 보인다. 그 밖의 코드는 stderr만 사용자에게 보인다.
미확인: 실제 설치 상태의 동작, 데스크톱·원격 제어 경로, 사용량 한도 중 실행 여부, 표준출력이 사용자 화면에 보이는지.
그래서 항상 종료 코드 0과 짧은 표준출력만 쓴다. 거절·중단에도 프롬프트를 막지 않는다(2는 프롬프트를 지워 대화 기록
대조 근거가 사라질 수 있다). 따라서 붙여넣은 원문은 모델에게도 전달되고, 사용자는 모델의 전달로 결과를 안다.
Gold·중단이 아닌 입력에는 아무것도 출력하지 않는다. 예외: "중단"이 든 짧은 입력(gold_parse.NEAR_STOP_MAX)은 정지를
기록하지 않았다고 알린다.
"""
import json

from . import gold_parse, gold_store, opstate

PREFIX = "[gold-hook] "


def _stop(root, now):
    """USER_STOPPED를 기록하고, 다시 읽어 확인한 사실만 말한다. 해제는 opstate.clear_by_user(사용자)뿐이다."""
    error = ""
    try:
        opstate.set_condition(root, opstate.USER_STOPPED, now, "user", "UserPromptSubmit 훅: 중단")
    except Exception as exc:  # noqa: BLE001 — 상태 파일은 썼는데 장부 기록만 실패할 수 있으므로 아래에서 다시 읽는다
        error = " (기록 중 오류: %s)" % type(exc).__name__
    state = opstate.load(root)
    if opstate.USER_STOPPED in state["conditions"]:
        return "중단 접수: USER_STOPPED를 기록했다%s. 새 개발 작업을 시작하지 말고 사용자에게 알려라." % error
    return "중단 플래그 기록을 확인하지 못함%s. 현재 상태 %s. 새 개발 작업을 시작하지 말고 사용자에게 알려라." \
        % (error, opstate.effective(state))


def handle(root, data, now):
    """표준입력 바이트 → 표준출력에 쓸 한 줄(할 일이 없으면 빈 문자열)."""
    try:
        payload = json.loads(data.decode("utf-8"))
        if payload["hook_event_name"] != "UserPromptSubmit" or not isinstance(payload["prompt"], str):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        return PREFIX + "UserPromptSubmit 입력을 읽지 못함. Gold 저장·중단 기록 없음."
    kind = gold_parse.classify(payload["prompt"])
    if kind is None:
        return ""
    if kind == "near_stop":
        return PREFIX + "정지 기록 안 함. 멈추려면 정확히 '중단'을 보내라. 이 안내를 사용자에게 알려라."
    try:
        if kind == "stop":
            return PREFIX + _stop(root, now)
        record = gold_store.save(root, payload, now)["data"]
    except gold_parse.GoldError as exc:
        return PREFIX + "Gold 저장하지 않음 [%s] %s. 값을 추정·보정하거나 다른 곳에 저장하지 말고 사유를 사용자에게 알려라." \
            % exc.args
    except Exception as exc:  # noqa: BLE001 — 어디까지 됐는지 모르면 성공이라고 말하지 않는다
        what = "중단 플래그 기록" if kind == "stop" else "Gold 저장"
        return PREFIX + "%s 결과를 확인하지 못함(%s). 됐다고 보지 말고 사용자에게 알려라." % (what, type(exc).__name__)
    return PREFIX + "Gold 저장됨: 화면=%s 구역=%d 원문 sha256=%s. 이 답을 다른 파일에 옮겨 적지 말고 저장 결과를 사용자에게 알려라." \
        % (record["screen_id"], len(record["items"]), record["raw_sha256"])
