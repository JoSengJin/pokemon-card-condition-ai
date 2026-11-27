"""작업 유형별 Claude 권한 묶음과 실행 환경(작업 계약 3단계). 묶음은 코드가 정하며 계약 필드로 넓힐 수 없다.

- 묶음(routing_policy.json 유형 기준): A = 읽기 + 산출물 폴더 쓰기만(EXPERIMENT 요약·오분석·반복 실패 분석), B·C는 필요한 통제(비전 예산
  차감·Silver 반영 중복 방지·이미지 접근 범위 / 명령 실행 Sandbox 강제·검증 반영 단계)가 아직 구현되지 않아 실행하지 않는다(RUNNABLE).
  묶음이 없거나 정의하지 않은 유형도 실행하지 않는다(claude_job이 그 작업만 대기시킨다).
- A 옵션(A_OPTIONS)은 Claude Code 공식 문서(code.claude.com/docs/en/cli-reference·permissions, 2026-11-27 열람)에서 확인한 것만 쓴다.
  실환경 미확인(이 설치본에서 실행해 보지 않았다): --restricted(문서: v2.1.248+, 명령·코드 실행 도구와 WebFetch 제거, 파일 도구를 작업
  폴더로 한정, managed 설정과 --settings만 로드), --tools "Read,Write,Edit,Glob,Grep"(내장 도구 제한, Bash·Agent 없음),
  --strict-mcp-config(.mcp.json·~/.claude.json·플러그인 MCP 무시, --mcp-config 없음 = MCP 없음), --disallowedTools "mcp__*"(MCP 도구 제거),
  --permission-mode dontAsk(승인 필요한 호출은 자동 거절, 작업 폴더 안 읽기는 허용), --allowedTools "Edit(./out/**)"(Edit 규칙은 파일을
  고치는 모든 내장 도구에 적용, ./는 cwd 기준 gitignore 형식), --disable-slash-commands(skill·명령 비활성).
- cwd는 작업 폴더(root/tasks/<task_key>). 하네스 상태 폴더(root/supervisor·장부·예산)는 cwd 밖이라 읽기·쓰기 모두 자동 거절 대상이고,
  작업 폴더 안의 하네스 파일(lease.json·done.json·complete.json)은 쓰기 허용 규칙(out/ 아래만)에 없어 거절 대상이다(문서 기준).
- 계약 입력은 stage_inputs가 source_root(기본 저장소) 아래에서 SHA를 확인해 작업 폴더 in/으로 복사한다. 링크·폴더 밖·하네스 root 안·
  이름에 gold/seal이 든 경로(봉인·Gold 임시 규칙)는 거절한다.
- 환경변수는 ENV_ALLOW만 넘긴다(구독 인증 최소 추정값. API 키·토큰류는 넘기지 않는다). 인증이 이것으로 되는지는 실환경 미확인.
- 자동 재개 활성화 목록 AUTO_RESUME(작업 유형 → 실환경 증거 {"evidence": 경로, "sha256": 그 파일 sha256})은 빈 dict로 시작한다. 증거 파일이
  있고 해시가 맞는 유형만 켜진 것으로 본다(auto_resume_allowed). 목록에 없으면 한도 해제·실행 중 사망 뒤에도 자동 재개하지 않는다(첫 실행은 허용).
호출 깊이: 모든 함수가 말단이다(서로·다른 harness 함수를 부르지 않는다).
"""
import hashlib
import os
import shutil

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLE_OF = {"experiment_log_summary": "A", "misanalysis_general": "A", "repeated_failure_analysis": "A",
             "image_analysis_general": "B", "silver_labeling": "B", "defect_analysis_precise": "B",
             "label_cross_validation": "B", "label_disagreement": "B",
             "general_dev": "C", "complex_algorithm": "C", "model_redesign": "C"}
RUNNABLE = ("A",)
A_OPTIONS = ("--restricted", "--tools", "Read,Write,Edit,Glob,Grep", "--strict-mcp-config", "--disallowedTools", "mcp__*",
             "--permission-mode", "dontAsk", "--allowedTools", "Edit(./out/**)", "--disable-slash-commands")
ENV_ALLOW = ("HOME", "PATH", "USER", "LOGNAME", "SHELL", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR")
AUTO_RESUME = {}  # 실환경 시험으로 권한·부작용 제한과 중복 반영 방지를 확인한 유형만 증거와 함께 추가한다(A → B → C 순)
FORBIDDEN_PARTS = ("gold", "seal")  # 임시 규칙: 경로 조각에 이 글자가 들어 있으면 봉인·Gold 자료로 보고 복사하지 않는다


def options(task_type):
    """실행 가능한 묶음이면 그 CLI 옵션 목록, 아니면 None(실행하지 않는다)."""
    return list(A_OPTIONS) if BUNDLE_OF.get(task_type) in RUNNABLE else None


def env_of(env):
    """허용 목록의 환경변수만 남긴 새 dict."""
    return {k: v for k, v in env.items() if k in ENV_ALLOW}


def auto_resume_allowed(task_type):
    """그 유형의 자동 재개가 실환경 증거와 함께 켜져 있는가(증거 파일이 일반 파일이고 sha256이 기록과 같을 때만)."""
    entry = AUTO_RESUME.get(task_type)
    if not isinstance(entry, dict) or not isinstance(entry.get("evidence"), str) or not isinstance(entry.get("sha256"), str):
        return False
    path = os.path.join(REPO, entry["evidence"])
    if os.path.islink(path) or not os.path.isfile(path):
        return False
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest() == entry["sha256"]


def stage_inputs(task_dir, contract, source_root, harness_root):
    """계약 inputs({상대 경로: sha256})를 source_root에서 task_dir/in/으로 복사하고 복사본 SHA를 확인한다. 복사한 경로 목록.
    안전하지 않은 경로·링크·없는 파일·SHA 불일치는 ValueError(그 작업은 실행하지 않는다)."""
    base, guard = os.path.realpath(source_root), os.path.realpath(harness_root)
    copied = []
    for rel, want in sorted(contract["inputs"].items()):
        parts = rel.split("/")
        if rel.startswith("/") or any(p in ("", ".", "..") for p in parts) \
                or any(word in p.lower() for p in parts for word in FORBIDDEN_PARTS):
            raise ValueError("허용하지 않는 입력 경로(절대·상위·봉인·Gold): %r" % rel)
        cur = source_root
        for part in parts:  # 중간 폴더·파일 어느 것도 링크면 거절
            cur = os.path.join(cur, part)
            if os.path.islink(cur):
                raise ValueError("입력 경로에 링크가 있다: %r" % rel)
        real = os.path.realpath(cur)
        if os.path.commonpath([base, real]) != base or os.path.commonpath([guard, real]) == guard or not os.path.isfile(real):
            raise ValueError("입력이 원본 폴더 밖·하네스 root 안이거나 일반 파일이 아니다: %r" % rel)
        dest = os.path.join(task_dir, "in", *parts)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        tmp = "%s.tmp.%d" % (dest, os.getpid())
        shutil.copyfile(real, tmp)
        with open(tmp, "rb") as handle:
            got = hashlib.sha256(handle.read()).hexdigest()
        if got != want:
            os.unlink(tmp)
            raise ValueError("입력 SHA 불일치: %r" % rel)
        os.replace(tmp, dest)
        copied.append(rel)
    return copied
