"""UserPromptSubmit 훅 진입점: `python -I -B user_prompt_submit.py <하네스 root 절대경로>` (표준입력 JSON).

설치하지 않는다(settings-snippet.json.template은 템플릿이다). 종료 코드는 0이다(근거는 harness/gold_hook.py). 예외 하나: "재개 <대상>"(해제
1단계)은 확인 코드를 사용자에게만 보이려고 종료 코드 2 + stderr로 끝낸다(프롬프트가 지워져 모델은 요청·코드를 보지 못한다, harness/control_release.py).
이 파일이 __main__인 프로세스만 Gold 저장소에 쓸 수 있다. 이것의 한계는 harness/gold_store.py에 적었다.
가져오기 실패처럼 여기까지 오지 못하면 종료 코드가 0이 아니며 아무것도 저장되지 않는다.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from harness import control_release, gold_hook  # noqa: E402

if __name__ == "__main__":
    DATA = sys.stdin.buffer.read()
    ASK = control_release.from_prompt(DATA)
    if len(sys.argv) != 2 or not os.path.isabs(sys.argv[1]):
        MESSAGE = gold_hook.PREFIX + "설정 오류: 하네스 root 절대경로 인자가 필요함. Gold 저장·중단 기록 없음."
    elif ASK is None:
        MESSAGE = gold_hook.handle(sys.argv[1], DATA, time.time())
    elif not ASK[0]:
        MESSAGE = control_release.PREFIX + "해제 안 함. 형식: '재개 <조건 이름>'으로 확인 코드를 받은 뒤 '재개 <조건 이름> <6자리 코드>'."
    elif ASK[1] is None:
        CODE, MESSAGE, SECRET = control_release.request(sys.argv[1], ASK[0], time.time(), "hook")
        MESSAGE = control_release.PREFIX + MESSAGE
        if SECRET:
            sys.stderr.buffer.write(("%s\n확인 코드: %s (보낼 문장: 재개 %s %s)\n" % (MESSAGE, SECRET, ASK[0], SECRET)).encode("utf-8"))
            sys.exit(2)
    else:
        MESSAGE = control_release.PREFIX + control_release.answer(sys.argv[1], ASK[0], ASK[1], "UserPromptSubmit 훅: 재개", time.time(),
                                                                  "hook", True)[1]
    if MESSAGE:
        sys.stdout.buffer.write((MESSAGE + "\n").encode("utf-8"))
