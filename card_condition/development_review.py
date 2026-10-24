"""Synchronous review handoff from the approved development session's common runner."""
from contextlib import contextmanager
from contextvars import ContextVar
import os
from pathlib import Path

from .experiment_record import read, save, sha, LatestExperimentUnavailable

_IN_REVIEW = ContextVar('development_review_active', default=False)


@contextmanager
def review_scope():
    token = _IN_REVIEW.set(True)
    try:
        yield
    finally:
        _IN_REVIEW.reset(token)


def enabled(root):
    policy = root / 'development-review.json'
    if not policy.exists() or _IN_REVIEW.get() or os.environ.get('CARD_CONDITION_AUTO_CHILD'):
        return False
    setting = read(policy)
    return setting.get('enabled') is True and setting.get('session_id') == os.environ.get('CODEX_THREAD_ID')


def after_experiment(root, folder):
    if not enabled(root):
        return None
    from .cross_review_evidence import latest_packet
    from .cross_review_manual import main as review_main
    record = read(folder / 'record.json')
    journal = folder / 'development_handoff.json'
    if journal.exists():
        print('개발 연결 기록 재사용:', journal, '(자동 재호출 없음)')
        return read(journal)
    state = dict(status='checking', source_record=str(folder/'record.json'), session_id=os.environ['CODEX_THREAD_ID'],
                 next_action='검토 중에는 파일을 수정하지 말고 종료 결과를 기다리세요.')
    save(journal, state)

    def finish(status, action, **extra):
        state.update(status=status, next_action=action, **extra)
        save(journal, state)
        save(root/'artifacts/development-cycle/latest.json', dict(handoff=str(journal), **state))
        print('개발 연결:', status, '/', action, '\n결과:', journal)
        return state

    if record['status'] != 'completed':
        return finish('execution_'+record['status'], '실행 오류·중단 원인부터 확인하세요. 가설 실패나 성능 수치로 해석하거나 같은 요청을 자동 재시도하지 마세요.')
    if read(folder/'plan.json').get('gemini_calls_allowed') == 0:
        return finish('ai_calls_forbidden', '이번 계획은 Gemini 호출을 금지합니다. 실제 자동 검토는 실행하지 않고 다음 승인 개발을 이어가세요.', gemini_calls=0, codex_model_calls=0)

    try:
        packet = latest_packet(root)  # Reuse existing stagnation/measurement/source checks.
        if (root/packet['latest_result']).resolve() != (folder/'result.json').resolve():
            return finish('superseded', '다른 최신 실험이 있으므로 이 결과로 검토하지 않습니다. 최신 기록을 확인하고 개발을 이어가세요.')
        if not packet.get('fresh_evidence_ids'):
            return finish('no_new_evidence', '새 반증 근거가 없어 검토를 생략했습니다. 같은 실험을 반복하지 말고 독립 진단·다음 승인 작업을 진행하세요.')
        state.update(status='review_running', source_result_sha256=sha(folder/'result.json'))
        save(journal, state)  # Persist before any model request; uncertain work is never retried.
        print('정체 감지: 기존 사전 판정 기준 미달. 개발 수정을 멈추고 ./review --auto 경로를 실행합니다.', flush=True)
        with review_scope():
            code = review_main(['--auto'])
        active = read(root/'artifacts/manual-cross-review/active.json')
        review_folder = Path(active['directory']).resolve()
        base = (root/'artifacts/manual-cross-review').resolve()
        if not review_folder.is_relative_to(base):
            raise ValueError('Review output is outside this project')
        result = read(review_folder/'result.json')
        if result['packet']['latest_result'] != packet['latest_result']:
            raise ValueError('Review output does not match this experiment')
        automation = read(review_folder/'automation.json') if (review_folder/'automation.json').exists() else {}
        status = automation.get('status', result['status'])
        experiment = automation.get('experiment_folder')
        record_path = str(Path(experiment)/'record.json') if experiment else None
        return finish('review_finished',
            '구현 제안은 미적용·미실행입니다. 격리 실행·독립 평가 경로가 없어 자동 학습을 보류했습니다. 같은 요청을 재호출하지 말고 제안과 차단 사유를 확인하세요.'
            if status=='trusted_execution_required' else
            '독립 계산 평가와 채택/후보 폐기를 확인하고 다음 승인 개발을 이어가세요. 운영 배포·일반화 개선은 별도입니다.'
            if status in ('completed','experiment_rejected') else
            '검토 기록·판정을 읽고 다음 승인 개발을 이어가세요. 자동 실험의 채택/복원을 먼저 확인하고 이전 실험 snapshot으로 새 변경을 덮어쓰지 마세요.'
            if code == 0 else '검토 중단 사유를 확인하세요. 실패·결과 불명 요청을 재호출하지 말고 사람 의존 작업만 대기하며 독립 개발을 이어가세요.',
            review_status=status, review_exit_code=code, review_directory=str(review_folder),
            implementation_proposal=automation.get('implementation_proposal'),code_applied=automation.get('code_applied'),worker_executed=automation.get('worker_executed'),
            debate_html=str(review_folder/'debate.html'), next_steps=str(review_folder/'next_steps.json'), token_report=str(review_folder/'token_report.json'),
            experiment_record=record_path, acceptance_passed=automation.get('acceptance_passed'),
            performance_improved_on_same_cohort=automation.get('performance_improved_on_same_cohort'),
            source_restored=automation.get('source_restored'))
    except LatestExperimentUnavailable as exc:
        return finish('not_stalled', '최신 실험은 검토 조건에 해당하지 않습니다. 저장 판정과 다음 승인 개발을 확인하세요.', reason=str(exc))
    except (KeyboardInterrupt, EOFError):
        return finish('review_interrupted', '검토 연결이 중단됐습니다. 체크포인트를 확인하고 결과 불명 요청은 자동 재시도하지 마세요.')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return finish('handoff_error', '검토 연결 기록을 확인하세요. 모델 요청을 자동 재시도하지 말고 독립 개발만 이어가세요.', error_kind=type(exc).__name__)
