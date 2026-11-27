"""3차 결함 H9: executor sandbox 프로필은 쓰기 범위 밖에서도 sandbox 밖 동작을 부를 길을 막는다(실제 sandbox-exec 하위 프로세스).

- 네트워크 전부(network*: 로컬 TCP·UDP·bind·유닉스 소켓, 외부 포함. executor 계약에 네트워크가 필요 없다), localhost 나가기
  (network-outbound remote ip "localhost:*"), LaunchServices 열기(lsopen), launchservicesd mach-lookup을 거절한다.
- 시험은 다른 서비스에 접속하거나 앱을 열지 않는다: 접속 대상은 시험이 직접 연 대기 소켓(TCP·유닉스)뿐이고, 열기 대상은 처리할 앱이 없는
  URL 체계(-10814 = 앱 없음, -54 = sandbox 거절), mach-lookup은 이름 조회만 한다(메시지를 보내지 않는다).
- 같은 실행에서 정상 산출물은 확정 out/에 그대로 생긴다(정상 executor가 깨지지 않는다).
"""
import ctypes
import json
import os
import shutil
import socket
import tempfile
import unittest

from harness import contract as ct
from harness import sandbox
from tests.test_harness_support import make_contract

SPEC = "tests.test_harness_sandbox_deny:EXECUTORS"
_URL = b"harness-no-such-scheme-q7x://probe"


def _attempt(got, name, fn):
    try:
        fn()
        got[name] = "ok"
    except OSError as exc:
        got[name] = "denied:%d" % exc.errno


def prober(task, out_dir):
    """sandbox 안 executor: 접속·bind·열기·mach 조회를 시도해 결과를 result.txt(정상 산출물)에 쓴다."""
    port, sock = int(task["inputs"]["port"]), task["inputs"]["sock"]
    got = {}
    _attempt(got, "tcp_localhost", lambda: socket.create_connection(("127.0.0.1", port), timeout=2).close())
    _attempt(got, "udp_localhost", lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b"x", ("127.0.0.1", port)))
    _attempt(got, "bind_any", lambda: socket.socket().bind(("0.0.0.0", 0)))
    _attempt(got, "unix", lambda: socket.socket(socket.AF_UNIX).connect(sock))
    cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    cs = ctypes.CDLL("/System/Library/Frameworks/CoreServices.framework/CoreServices")
    cf.CFURLCreateWithBytes.restype = ctypes.c_void_p
    cf.CFURLCreateWithBytes.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32, ctypes.c_void_p]
    cs.LSOpenCFURLRef.restype, cs.LSOpenCFURLRef.argtypes = ctypes.c_int32, [ctypes.c_void_p, ctypes.c_void_p]
    got["lsopen"] = cs.LSOpenCFURLRef(cf.CFURLCreateWithBytes(None, _URL, len(_URL), 0x08000100, None), None)
    libc, right = ctypes.CDLL("/usr/lib/libSystem.B.dylib"), ctypes.c_uint(0)
    libc.bootstrap_look_up.argtypes = [ctypes.c_uint, ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint)]
    got["mach_launchservicesd"] = libc.bootstrap_look_up(ctypes.c_uint.in_dll(libc, "bootstrap_port").value,
                                                         b"com.apple.coreservices.launchservicesd", ctypes.byref(right))
    with open(os.path.join(out_dir, "result.txt"), "w") as handle:
        json.dump(got, handle)
    return ["result.txt"]


EXECUTORS = {"prober": prober}


class SandboxDenyTest(unittest.TestCase):
    def test_network_launchservices_and_lsd_lookup_are_refused_while_outputs_still_work(self):
        base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, base, True)
        root, sock = os.path.join(base, "root"), os.path.join(base, "u.sock")
        tcp, unix = socket.socket(), socket.socket(socket.AF_UNIX)
        for listener, where in ((tcp, ("127.0.0.1", 0)), (unix, sock)):
            self.addCleanup(listener.close)
            listener.bind(where)
            listener.listen(5)
        text = sandbox.profile(root, tempfile.mkdtemp(dir=base))
        for rule in ("(deny network*)", '(deny network-outbound (remote ip "localhost:*"))', "(deny lsopen)",
                     '(deny mach-lookup (global-name "com.apple.coreservices.launchservicesd"))'):
            self.assertIn(rule, text)
        task = make_contract("N", task_type="prober", inputs={"port": str(tcp.getsockname()[1]), "sock": sock})
        final = os.path.join(root, "tasks", ct.task_key(task), "out")
        self.assertEqual(sandbox.run_one(root, SPEC, "prober", task, final), ["result.txt"])
        with open(os.path.join(final, "result.txt"), encoding="utf-8") as handle:
            got = json.load(handle)
        self.assertEqual(got, {"tcp_localhost": "denied:1", "udp_localhost": "denied:1", "bind_any": "denied:1", "unix": "denied:1",
                               "lsopen": -54, "mach_launchservicesd": 1100})
        for listener in (tcp, unix):
            listener.setblocking(False)
            with self.assertRaises(BlockingIOError):  # 대기 소켓에 들어온 접속이 없다
                listener.accept()


if __name__ == "__main__":
    unittest.main()
