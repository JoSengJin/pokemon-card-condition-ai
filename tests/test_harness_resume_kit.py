"""자동 재개 시험 공용 도구(시험 없음)."""
import contextlib


def allow_resume(case, task_type):
    """그 작업 유형의 자동 재개를 켠 상태(3단계에서 활성화 목록 patch로 바뀐다. 2단계에는 자동 재개 목록이 아직 없어 그대로 둔다)."""
    return contextlib.nullcontext()
