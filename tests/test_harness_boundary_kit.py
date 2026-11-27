"""2차 결함 G1·G2·G4·G6·G7 시험용 executor(sandbox 안에서 실행, 시험 없음). 모델·네트워크 없음.

- 하네스 root는 HARNESS_TEST_ROOT(시험이 넘기는 환경변수)에서 읽는다: executor가 받는 out_dir은 실행별 staging 폴더라 root를 경로로 알 수 없다.
- 관찰 결과는 HARNESS_MARK_DIR(하네스 root·저장소 밖 임시 폴더)에 남긴다. 실제 프로필은 그 폴더 쓰기를 허용하지 않으므로 시험이
  marked_profile로 그 시험 프로세스의 프로필에만 덧붙인다(실제 runner 프로필은 그대로).
"""
import hashlib
import json
import os
import time

from harness import contract as ct


def _try(got, name, fn):
    try:
        fn()
        got[name] = "ok"
    except OSError as exc:
        got[name] = "denied:%d" % exc.errno


def lingerer(task, out_dir):
    """정상 산출물을 쓰고, 확정 out/ 쓰기와 예측 가능한 임시 이름 링크 심기를 시도한 뒤, 같은 그룹 자식과 setsid 손자를 남긴다.
    손자는 1초 뒤 확정 out/·staging 산출물을 바꾸려 한다(G1·G7). 결과는 marks/now.json·late.json, 자식은 marks/child.txt."""
    root, marks = os.environ["HARNESS_TEST_ROOT"], os.environ["HARNESS_MARK_DIR"]
    final = os.path.join(root, "tasks", ct.task_key(task), "out")
    with open(os.path.join(out_dir, "result.txt"), "w") as handle:
        handle.write("PAYLOAD")
    got = {}
    _try(got, "write_final", lambda: open(os.path.join(final, "result.txt"), "a").close())
    _try(got, "plant_final_tmp_link", lambda: os.symlink(os.path.join(marks, "victim"), os.path.join(final, "result.txt.tmp.1")))
    with open(os.path.join(marks, "now.json"), "w") as handle:
        json.dump(got, handle)
    if os.fork() == 0:  # 같은 프로세스 그룹 자식: 실행이 끝나면 하네스가 그룹째 끝내야 한다
        time.sleep(1.0)
        open(os.path.join(marks, "child.txt"), "w").close()
        os._exit(0)
    if os.fork() == 0:  # setsid 손자(그룹 밖): 하네스가 끝내지 못하는 한계. 확정 산출물은 바꾸지 못해야 한다
        os.setsid()
        if os.fork() != 0:
            os._exit(0)
        fd = os.open("/dev/null", os.O_RDWR)
        for n in (0, 1, 2):
            os.dup2(fd, n)
        time.sleep(1.0)
        late = {}
        _try(late, "append_final", lambda: open(os.path.join(final, "result.txt"), "a").write("changed"))
        _try(late, "append_staging", lambda: open(os.path.join(out_dir, "result.txt"), "a").write("changed"))
        with open(os.path.join(marks, "late.json"), "w") as handle:
            json.dump(late, handle)
        os._exit(0)
    return ["result.txt"]


def shaper(task, out_dir):
    """inputs.mode대로 산출물 자리를 링크·하드 링크·FIFO·폴더로 만들거나, out_dir을 root/tasks 링크로 바꾸거나(swap),
    다른 작업 폴더에 쓰려 한다(write_other, 결과는 산출물에)."""
    mode, root, path = task["inputs"]["mode"], os.environ["HARNESS_TEST_ROOT"], os.path.join(out_dir, "result.txt")
    if mode == "symlink":
        os.symlink(os.path.join(root, "supervisor", "opstate.json"), path)
    elif mode == "hardlink":
        open(os.path.join(os.environ["TMPDIR"], "twin"), "w").write("twin")
        os.link(os.path.join(os.environ["TMPDIR"], "twin"), path)
    elif mode == "fifo":
        os.mkfifo(path)
    elif mode == "dir":
        os.makedirs(os.path.join(path, "inner"))
    elif mode == "swap":
        os.rmdir(out_dir)
        os.symlink(os.path.join(root, "tasks"), out_dir)
    else:
        got = {}
        _try(got, "write_other", lambda: open(os.path.join(root, "tasks", "other", "done.json"), "w").write("{}"))
        with open(path, "w") as handle:
            json.dump(got, handle)
    return ["result.txt"]


def reader(task, out_dir):
    """실험 executor: 1초 뒤 하네스가 넘긴 입력 사본(HARNESS_INPUT_DIR)을 읽어 본 내용의 sha256과, 사본 쓰기 시도 결과를 산출물에 남긴다(G6)."""
    time.sleep(1.0)
    copy = os.path.join(os.environ["HARNESS_INPUT_DIR"], "data", "a.json")
    with open(copy, "rb") as handle:
        seen = hashlib.sha256(handle.read()).hexdigest()
    got = {"seen": seen}
    _try(got, "write_input_copy", lambda: open(copy, "a").write("x"))
    with open(os.path.join(out_dir, "metrics.json"), "w") as handle:
        json.dump(got, handle)
    return ["metrics.json"]


def marked_profile(base, marks):
    """시험 전용: sandbox.profile에 표식 폴더 쓰기 허용만 덧붙인 함수(mock.patch.object(sandbox, "profile", ...)로 쓴다)."""
    return lambda *args: base(*args) + '\n(allow file-write* (subpath "%s"))' % os.path.realpath(marks)


EXECUTORS = {"lingerer": lingerer, "shaper": shaper, "experiment": reader}
ALIASED = {"experiment": reader, "deterministic": reader}  # 실험 executor를 다른 유형 이름으로 감싼 표(G4: 거절돼야 한다)
