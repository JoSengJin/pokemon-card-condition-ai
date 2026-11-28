"""시험용 git 원본 폴더(3차 결함 H1: 실험·학습·평가의 code_sha는 source_root의 git HEAD와 대조한다). 시험 사례는 없다.

- git_source(path)는 path를 git 저장소로 만들고 고정 내용 code.py 하나를 고정 작성자·시각·메시지로 커밋한다. 그래서 모든 시험 폴더의
  HEAD가 같은 CODE다(계약에 상수로 적을 수 있다). 입력 자료 파일은 추적하지 않는다(추적 파일 변경만 '깨끗하지 않음'으로 본다).
- 사용자 git 설정(서명·훅·기본 브랜치)을 읽지 않도록 전역·시스템 설정을 끄고 고정 환경에서 실행한다.
"""
import os
import shutil
import subprocess
import tempfile

ENV = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": tempfile.gettempdir(), "GIT_CONFIG_GLOBAL": os.devnull,
       "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@example.invalid", "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
       "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z"}


def git(path, *args):
    """path에서 git 명령을 고정 환경으로 실행하고 표준 출력(앞뒤 공백 제거)을 돌려준다."""
    return subprocess.run(["git", "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main", "-C", path] + list(args),
                          env=ENV, check=True, capture_output=True, text=True).stdout.strip()


def git_source(path, text="CODE = 1\n"):
    """path(없으면 만든다)를 git 저장소로 만들고 code.py(text)를 커밋한다. 이미 저장소면 그대로 둔다. HEAD를 돌려준다(기본 text면 항상 CODE)."""
    os.makedirs(path, exist_ok=True)
    if os.path.isdir(os.path.join(path, ".git")):
        return git(path, "rev-parse", "HEAD")
    git(path, "init", "-q")
    with open(os.path.join(path, "code.py"), "w", encoding="utf-8") as handle:
        handle.write(text)
    git(path, "add", "code.py")
    git(path, "commit", "-q", "-m", "code")
    return git(path, "rev-parse", "HEAD")


_HERE = tempfile.mkdtemp()
CODE = git_source(_HERE)  # 고정 커밋 SHA(모든 git_source 폴더의 HEAD)
shutil.rmtree(_HERE, True)
