"""sandbox-exec 안에서 도는 executor 실행 자식(harness.sandbox 전용). python -m harness.sandbox_child list|run spec [task_type out_dir].

- list: spec(module:ATTR)의 dict 키를 JSON 목록으로 낸다. run: 표준 입력의 계약으로 executor를 부르고 결과를 마지막 줄 JSON으로 낸다.
  executor가 print로 쓰는 출력은 stderr로 돌린다(결과 줄과 섞이지 않게).
- 부모(runner)가 죽으면(부모 pid가 바뀜) 0.1초 안에 자기 프로세스 그룹째 끝난다(sandbox.run_one이 새 세션으로 띄운다): runner가 kill -9로
  죽은 뒤 executor와 그 자식이 혼자 계속 돌며 다음 runner와 겹쳐 실행되지 않게(macOS에는 부모 사망 신호 옵션이 없다). setsid 자손은 남는 한계.
- list는 실험·학습·평가(dedupe.CONDITION_TYPES) executor 함수를 다른 유형 이름에도 등록한 표를 거절한다(종료 코드 2, 2차 결함 G4: 실험을
  deterministic 같은 실행 조건 없는 유형으로 감싸 중복 판정 없이 다시 실행하는 경로). 다른 이름의 함수가 안에서 실험을 돌리는 것은 알 수 없다(한계).
"""
import importlib
import json
import os
import sys
import threading
import time

from . import recovery
from .dedupe import CONDITION_TYPES


def _watch(parent):
    """부모 pid가 바뀌면(부모 사망) 즉시 프로세스를 끝낸다(스레드 본체)."""
    while os.getppid() == parent:
        time.sleep(0.1)
    if os.getpgid(0) == os.getpid():  # 그룹 대표(새 세션)일 때만 그룹째 끝낸다(남의 그룹을 끝내지 않게)
        os.killpg(os.getpid(), 9)
    os._exit(70)


def main(argv):
    """자식 진입점. 결과 JSON 한 줄을 출력한다."""
    threading.Thread(target=_watch, args=(os.getppid(),), daemon=True).start()
    module, _, attr = argv[1].partition(":")
    table = getattr(importlib.import_module(module), attr)
    if argv[0] == "list":
        wrapped = {id(table[n]) for n in table if n in CONDITION_TYPES}
        if any(id(table[n]) in wrapped for n in table if n not in CONDITION_TYPES):
            print("실험·학습·평가 executor를 다른 유형 이름에도 등록한 표는 쓰지 않는다", file=sys.stderr, flush=True)
            return 2
        print(json.dumps(sorted(table)), flush=True)
        return 0
    real, sys.stdout = sys.stdout, sys.stderr
    try:
        produced = table[argv[2]](json.loads(sys.stdin.read()), argv[3])
        reply = {"ok": True, "produced": list(produced)}
    except (Exception, SystemExit) as exc:  # noqa: BLE001 — runner와 같은 규칙(recovery.kind_of)으로 종류를 정해 돌려준다
        status = getattr(exc, "status", None)  # 실험 어댑터의 상태(not_started 등): runner가 예산 차감 취소 여부를 정한다(B5-4)
        reply = {"ok": False, "kind": recovery.kind_of(exc), "error": "%s: %s" % (type(exc).__name__, exc),
                 "status": status if isinstance(status, str) else None}
    sys.stdout = real
    print(json.dumps(reply, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
