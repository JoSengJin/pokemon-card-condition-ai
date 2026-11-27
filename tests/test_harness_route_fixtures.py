"""route 시험 공용 도구(시험 없음). 정책 표 기대값은 승인 문서(model-routing-design.md 1-1)를 시험에 따로 적은 것이다."""
import json
import os

from harness import route

APPROVED = {  # task_type: (model, effort)  — 승인 표 12행. None은 LLM 미사용
    "general_dev": ("sonnet", "medium"),
    "complex_algorithm": ("sonnet", "high"),
    "image_analysis_general": ("sonnet", "medium"),
    "silver_labeling": ("sonnet", "medium"),
    "defect_analysis_precise": ("sonnet", "high"),
    "label_cross_validation": ("sonnet", "high"),
    "label_disagreement": ("opus", "high"),
    "misanalysis_general": ("sonnet", "medium"),
    "repeated_failure_analysis": ("opus", "high"),
    "model_redesign": ("opus", "high"),
    "experiment_log_summary": ("haiku", "low"),
    "deterministic": (None, None),
}

# 설치본 claude 2.1.310 `--help`의 해당 구간(2026-11-27 직접 실행해 복사)
HELP = """Options:
  --disallowed-tools <tools...>         Comma or space-separated list of tool names to deny
  --effort <level>                      Effort level for the current session
                                        (low, medium, high, xhigh, max)
  --environment <environment_id>        Create a new cloud session that runs on
                                        the given self-hosted environment
                                        (ccpool_...).
  --model <model>                       Model for the current session. Provide
                                        an alias for the latest model (e.g.
                                        'fable', 'opus', or 'sonnet') or a
                                        model's full name.
  -n, --name <name>                     Set a display name for this session
"""


def contract(task_type="general_dev", needs_llm=True, **extra):
    return dict({"task_type": task_type, "needs_llm": needs_llm, "needs_vision": False, "risk": "low"}, **extra)


def policy():
    return route.load_policy()


def write_policy(path, mutate):
    data = route.load_policy()
    mutate(data)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    return route.load_policy(path)


def decision(task_type="general_dev", history=None, **runtime):
    return route.route(contract(task_type), history, policy(), runtime or None)


FAIL = {"cause": "quality_gate_miss"}
