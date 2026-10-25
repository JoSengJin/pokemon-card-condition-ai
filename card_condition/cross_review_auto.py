"""Bounded proposal, critique and independent judgment public entrypoints."""
import json
import os
from pathlib import Path
import selectors
import subprocess
from time import monotonic
from .cross_review import digest
from .cross_review_auto_child import (LAUNCH_BLOCKED, MAX_LAUNCH_RETRIES, archive_launch_failure,
    codex_child_config, launch_failure_detail, launch_not_sent, stored_phase_one_correction, sum_usage)
from .cross_review_auto_context import review_context
from .cross_review_auto_contract import (ACCEPTANCE, CODEX_CONTEXT_VERSION, CODEX_PROMPT_BYTES,
    CODEX_TIMEOUT, CODEX_TOKEN_BUDGET, CRITIQUE_REPLY, EXPERIMENT, EXPERIMENT_TIMEOUT,
    IMPLEMENTATION, PARAMETER, PROTECTED, RATINGS, TEXT, VERDICT, CodexBudgetExceeded,
    UntrustedExecutionError, VerdictValidationError, array, obj)
from .cross_review_auto_results import (implement, measured_gain, render_result, restore_unaccepted,
    stage_implementation, token_report)
from .cross_review_auto_sources import (diagnostic_text, model_file, provided_code_sources,
    review_rules, source_context, verify_sources)
from .cross_review_auto_validation import validate_verdict, verdict_errors
from .experiment_record import read, save


def cli_backend(root, phase, prompt, directory, thread_id=None):
    schema, answer = directory / 'schema.json', directory / 'answer.json'
    save(schema, VERDICT if phase in ('verify','correct') else IMPLEMENTATION)
    # Keep the existing model/auth/approval configuration, but no growing agent history or tools.
    options,env=codex_child_config(root)
    args=['codex','exec','--sandbox','read-only','--cd',str(directory),*options,
          '--skip-git-repo-check','--json','--output-schema',str(schema),'-o',str(answer),'-']
    usages, session_id, items, blocked, errors, stderr_lines, warnings = [], None, {}, None, [], [], []
    process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               cwd=directory, env=env, start_new_session=True)
    def record_error(data):
        nonlocal blocked
        message = data.get('message','')
        if (isinstance(message,str) and message.startswith('Under-development features enabled:')
                and 'To suppress this warning' in message):
            warnings.append(diagnostic_text(json.dumps(data,ensure_ascii=False)))
        else:
            errors.append(diagnostic_text(json.dumps(data,ensure_ascii=False)))
            blocked = 'cli_error'
    def event(line):
        nonlocal session_id, blocked
        try:
            data = json.loads(line)
        except ValueError:
            errors.append('Invalid CLI event: '+diagnostic_text(line))
            blocked = 'invalid_event'
            return
        if not isinstance(data,dict):
            errors.append('CLI event must be an object')
            blocked = 'invalid_event'; return
        kind = data.get('type')
        if kind in ('error','turn.failed'):
            record_error(data)
        if kind == 'thread.started':
            session_id = data.get('thread_id')
        if kind == 'turn.completed':
            usages.append(data.get('usage'))
            if len(usages) > 1:
                blocked = 'unexpected_extra_turn'
        if kind in ('item.started', 'item.completed'):
            item = data.get('item', {})
            item_type = item.get('type', '')
            items[item_type] = items.get(item_type, 0) + 1
            if item_type == 'error':
                record_error(item)
            elif item_type not in ('agent_message', 'reasoning'):
                blocked = 'unexpected_tool'
    try:
        process.stdin.write(prompt.encode()); process.stdin.close()
        buffers = {process.stdout:b'', process.stderr:b''}
        deadline = monotonic() + CODEX_TIMEOUT
        with selectors.DefaultSelector() as selector:
            for stream in buffers: selector.register(stream,selectors.EVENT_READ)
            while selector.get_map():
                remaining = deadline - monotonic()
                ready = selector.select(max(0,remaining)) if remaining > 0 else []
                if not ready:
                    blocked = 'time_budget'; break
                for key,_ in ready:
                    stream = key.fileobj
                    chunk = stream.read1(65536)
                    if not chunk:
                        if buffers[stream]:
                            if stream is process.stdout: event(buffers[stream])
                            else: stderr_lines.append(diagnostic_text(buffers[stream].decode('utf-8',errors='replace')))
                        selector.unregister(stream); continue
                    buffers[stream] += chunk
                    if len(buffers[stream]) > 262144:
                        blocked = 'event_size_limit'; break
                    while b'\n' in buffers[stream]:
                        line,buffers[stream] = buffers[stream].split(b'\n',1)
                        if stream is process.stdout:
                            if line.strip(): event(line)
                        else:
                            stderr_lines.append(diagnostic_text(line.decode('utf-8',errors='replace')))
                            stderr_lines[:] = stderr_lines[-32:]
                        if blocked: break
                    if blocked: break
                if blocked: break
        if blocked:
            try: os.killpg(process.pid, 15)
            except ProcessLookupError: pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            blocked = blocked or 'time_budget'
            os.killpg(process.pid, 9); process.wait()
    finally:
        if process.poll() is None:
            os.killpg(process.pid, 9); process.wait()
        # A killed CLI can still have a final stderr explanation buffered in its pipe.
        tail = process.stderr.read(65536)
        if tail: stderr_lines.append(diagnostic_text(tail.decode('utf-8',errors='replace')))
        process.stdout.close(); process.stderr.close()
        save(directory / 'diagnostics.json', dict(return_code=process.returncode,errors=errors[-8:],
             stderr=diagnostic_text('\n'.join(stderr_lines)),warnings=warnings[-8:],blocked=blocked))
        save(directory / 'execution.json', dict(prompt_bytes=len(prompt.encode()), turn_completions=len(usages),
             item_events=items, blocked=blocked, usage_known=bool(usages)))
    usage = sum_usage(usages, ('input_tokens', 'cached_input_tokens', 'output_tokens', 'reasoning_output_tokens'))
    if blocked or process.returncode != 0 or not answer.exists() or answer.stat().st_size > 131072:
        return None, usage, session_id
    return read(answer), usage, session_id


def codex_task(root, folder, phase, payload, thread_id=None, backend=None, token_budget=CODEX_TOKEN_BUDGET):
    directory = folder / 'codex' / (phase + '-' + digest(payload)[:16])
    directory.mkdir(parents=True, exist_ok=True)
    journal = directory / 'call.json'
    if not journal.exists():
        reused = stored_phase_one_correction(folder, phase, payload, directory)
        if reused is not None:
            try:
                directory.rmdir()  # Empty placeholder for the digest that was never used.
            except OSError:
                pass  # Holds a preflight record; keep it.
            return reused
    if journal.exists():
        entry = read(journal)
        if entry['status'] == 'complete':
            return entry
        if entry['status'] in ('error', 'pending') and launch_not_sent(directory):
            archive_launch_failure(folder, directory)  # Provably no request reached the model.
            directory.mkdir(parents=True, exist_ok=True)
            journal = directory / 'call.json'
        else:
            raise ValueError('Previous Codex request is failed or uncertain; never retry automatically')
    if len(list((folder / 'codex').glob('*/call.json'))) >= 3 or list((folder/'codex').glob(phase+'-*/call.json')):
        raise ValueError('At most one review, one correction and one implementation')
    context = review_context(root,folder,phase,payload)
    prompt = ('한국어 JSON. evidence_ids는 valid_evidence_ids 안에서만 선택한다. 도구 없이 동결 근거·project_rules만 사용한다. '
              'code_checks.quote는 source_context.excerpt에 실제로 연속된 원문 한 구절만 복사한다(떨어진 줄 합성·생략 금지). SHA도 대조한다. ')
    if phase in ('verify','correct'):
        from .cross_review_roles import CODEX_ADVOCATE
        prompt += CODEX_ADVOCATE+' failed_hypotheses_checked는 가설 실패 ID 전부만, review_claims.completed_diagnostic_ids는 완료 진단 ID 전부다. 실행 실패는 반증이 아니다. critique_responses는 실제 Gemini 비판 ID마다 정확히 하나, 비판 전에는 빈 목록이다. debate_assessment 점수는 심판 전0. 검증할 변수·사전 수치 기준이 있으면 select, 남은 Gemini>0이고 반증이 필요하면 second, 근거 부족 stop, 실제 사람/자료 의존 wait. implementation_files에는 수정할 허용 모델 소스만 넣는다. 새 격리 worker는 구현 단계의 별도 출력이므로 이 목록에 넣지 않는다. 모델 소스 수정 없이 worker가 worker_importable 함수 인자로 고정 실험 변수를 적용할 수 있으면 빈 목록도 가능하다. experiment_parameter(name/baseline/value/scope)를 확정하고 효과를 추정하지 않는다. missing_evidence_ids는 실제 없는 것만. gemini_required_for_select=false. '
        if phase=='correct':prompt += '마지막 교정이다. correction.errors는 프로그램 검증 오류이며 Gemini 비판이 아니다. 실제 critiques가 없으면 critique_responses를 빈 목록으로 유지한다. 실제 비판 ID에는 모두 답하고 수정안을 반환하라. 정당한 stop/wait는 유지한다. '
    else:
        prompt += ('judge_issue_responses는 심판 needs_evidence의 unresolved_issues와 unresolved criticism_checks의 rationale 각각에 issue 원문, 수정안의 정확한 plan_quote, 대조 이유 rationale를 반환한다. 계획에 명시된 측정·보호 기준으로 해소되지 않으면 proceed하지 않는다. 심판이 미입증 효과 자체를 요구했다면 실험 판정 기준을 인용해 구분한다. 해당 없으면 빈 배열. '
                   '독립 심판과 Gemini 반론, Codex 답변을 종합해 최종 final_decision=proceed/stop/wait와 한국어 final_rationale를 반환하세요. 판단 불가면 실행하지 마세요. isolated_execution 계약이 기존 worker 관행보다 우선합니다. 채택된 실험 하나의 최소 edits와 Python worker를 반환하세요. old는 허용 파일의 원문이며 before_sha256을 확인하세요. '
                   '기존 worker·fitter를 재사용하고 계획의 고정 experiment_parameter.value를 읽어 적용하세요. '
                   '학습 input에는 특징·mask·target·point_tokens·weights·ids만 있습니다. torch.load(weights_only=True)로 읽고 환경변수의 parameter JSON을 사용하세요. '
                   'CARD_CONDITION_PROJECT_ROOT의 card_condition 및 trainer_sources를 import해 기존 학습 코드를 재사용하세요. '
                   '출력 JSON은 coef와 bias뿐이며 평가 점수·rows·metadata는 넣지 마세요. 사람 정답·변수·수치 기준을 바꾸지 않습니다. ')
    if context.get('nemotron'):
        prompt += 'nemotron 점수·반론은 미검증이며 코드로 대조한다. '
    prompt += '\n' + json.dumps(context,ensure_ascii=False,separators=(',',':'))
    prompt_bytes = len(prompt.encode())
    prior = [read(p) for p in (folder/'codex').glob('*/call.json')]
    prior_usage = sum_usage([c.get('usage') for c in prior],('input_tokens','output_tokens'))
    estimate = prompt_bytes + 8000  # Conservative text reservation, not actual provider tokens or a hard cap.
    reason = ('input_size' if prompt_bytes > CODEX_PROMPT_BYTES[phase] else
              'unknown_prior_usage' if prior and any(v is None for v in prior_usage.values()) else
              'token_budget' if sum(v or 0 for v in prior_usage.values()) + estimate >= token_budget else None)
    save(directory/'preflight.json',dict(prompt_bytes=prompt_bytes,input_byte_limit=CODEX_PROMPT_BYTES[phase],
                                       token_reservation=estimate,blocked=reason))
    if reason:
        if reason == 'token_budget':
            raise CodexBudgetExceeded('Codex preflight token budget')
        raise ValueError('Codex preflight blocked: '+reason)
    save(directory / 'input.json', context)
    save(journal, dict(status='pending', phase=phase, usage=None))
    try:
        from .cross_review_app_server import app_server_backend
        data, usage, session_id = (backend or app_server_backend)(root, phase, prompt, directory, None)
        entry = dict(status='complete' if isinstance(data, dict) else 'error', phase=phase,
                     data=data, usage=usage, thread_id=session_id)
        save(journal, entry)
    except Exception as exc:
        if isinstance(exc, (FileNotFoundError, PermissionError)) and not (directory / 'execution.json').exists():
            # The process could not even be created: no request can have reached the model.
            save(directory / 'execution.json', dict(transport='app-server', turn_requests=0, turn_completions=0,
                                                    blocked=type(exc).__name__, usage_known=False, usage=None))
        save(journal, dict(status='error', phase=phase, error_kind=type(exc).__name__, usage=None))
        raise ValueError('Codex invocation failed; no automatic retry' + launch_failure_detail(directory)) from None
    if entry['status'] != 'complete':
        raise ValueError('Codex returned no valid structured result' + launch_failure_detail(directory))
    return entry


def run_auto(root, folder, result, backend=None, gemini_caller=None, token_budget=CODEX_TOKEN_BUDGET, call_ceiling=None):
    from .workspace_lock import workspace_lock
    from .development_review import review_scope
    from .cross_review_flow import run_codex_first
    with workspace_lock(root, 'automatic review'), review_scope():
        return run_codex_first(root,folder,result,backend=backend,gemini_caller=gemini_caller,
                               token_budget=token_budget,call_ceiling=call_ceiling)
