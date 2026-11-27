"""UserPromptSubmit 훅 진입점: `python -I -B user_prompt_submit.py <하네스 root 절대경로>` (표준입력 JSON).

설치하지 않는다(settings-snippet.json.template은 템플릿이다). 항상 종료 코드 0이다(근거는 harness/gold_hook.py).
이 파일이 __main__인 프로세스만 Gold 저장소에 쓸 수 있다. 이것의 한계는 harness/gold_store.py에 적었다.
가져오기 실패처럼 여기까지 오지 못하면 종료 코드가 0이 아니며 아무것도 저장되지 않는다.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from harness import gold_hook  # noqa: E402

if __name__ == "__main__":
    DATA = sys.stdin.buffer.read()
    if len(sys.argv) == 2 and os.path.isabs(sys.argv[1]):
        MESSAGE = gold_hook.handle(sys.argv[1], DATA, time.time())
    else:
        MESSAGE = gold_hook.PREFIX + "설정 오류: 하네스 root 절대경로 인자가 필요함. Gold 저장·중단 기록 없음."
    if MESSAGE:
        sys.stdout.buffer.write((MESSAGE + "\n").encode("utf-8"))
