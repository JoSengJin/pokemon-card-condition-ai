"""One cooperative writer for development edits, experiments and automatic reviews."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import get_ident

ENV_FD = 'CARD_CONDITION_WORKSPACE_LOCK_FD'
_HELD = {}


@contextmanager
def workspace_lock(root, operation):
    root = Path(root).resolve()
    identity = (str(root), os.getpid(), get_ident())
    if identity in _HELD:
        yield _HELD[identity]
        return
    path = root / 'artifacts/development-cycle/workspace.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    inherited = os.environ.get(ENV_FD)
    if inherited is not None:
        # Only a descriptor for this checkout's lock can delegate ownership.
        fd = int(inherited)
        if not path.exists() or (os.fstat(fd).st_dev, os.fstat(fd).st_ino) != (path.stat().st_dev, path.stat().st_ino):
            raise ValueError('Inherited workspace lock belongs to another file')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _HELD[identity] = fd
        try:
            yield fd
        finally:
            del _HELD[identity]
        return
    with path.open('a+') as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _HELD[identity] = stream.fileno()
        stream.seek(0); stream.truncate()
        stream.write(json.dumps(dict(pid=os.getpid(), operation=operation), ensure_ascii=False)); stream.flush()
        try:
            yield stream.fileno()
        finally:
            del _HELD[identity]
            # Closing the final descriptor releases the lease, including delegated children.


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(__file__).resolve().parents[1]
    command = args[1:] if args[:1] == ['--'] else args
    try:
        with workspace_lock(root, 'development edit') as fd:
            if command == ['--check']:
                print('개발·실험 잠금 사용 가능')
                return 0
            if not command:
                print('사용: ./develop -- <수정 명령> 또는 ./develop --check', file=sys.stderr)
                return 2
            env = dict(os.environ, **{ENV_FD: str(fd)})
            return subprocess.run(command, cwd=root, env=env, pass_fds=(fd,)).returncode
    except BlockingIOError:
        print('다른 개발·실험·검토가 사용 중입니다. 코드를 수정하지 말고 종료 결과를 확인하세요.', file=sys.stderr)
        return 1
    except (OSError, ValueError):
        print('개발 잠금 또는 실행 명령을 확인하세요.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
