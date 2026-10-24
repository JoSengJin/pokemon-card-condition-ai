"""Bounded proposal, critique and independent judgment; generated execution is blocked."""
import ast
import base64
import hashlib
import html
import io
import math
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib
import selectors
import re
from time import monotonic

from .cross_review import digest, execute, proposal_gate, VERSION
from .experiment_record import prepare, read, run, save, sha
from .review import atomic_write

CODEX_TOKEN_BUDGET = 100000
CODEX_TIMEOUT = 600
EXPERIMENT_TIMEOUT = 1800
CODEX_PROMPT_BYTES = {'verify': 32000, 'correct': 32000, 'implement': 32000}
CODEX_CONTEXT_VERSION = 'bounded-v10-app-server'
class CodexBudgetExceeded(ValueError):
    pass


TEXT = {'type': 'string'}


def obj(properties):
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)


def array(items):
    return dict(type='array', items=items)


EXPERIMENT = obj({k: TEXT for k in ('hypothesis_id', 'cause', 'smallest_experiment', 'success_criterion', 'failure_criterion')})
ACCEPTANCE = obj(dict(max_fp={'type': 'integer', 'minimum': 0}, max_fn={'type': 'integer', 'minimum': 0},
                      no_new_errors={'type': 'boolean'}, require_actual_point_guard={'type': 'boolean'}))
PARAMETER = obj(dict(name=TEXT, baseline={'type':'number'}, value={'type':'number'}, scope=TEXT))
CRITIQUE_REPLY=obj(dict(critique_id=TEXT,disposition={'type':'string','enum':['accept','reject','needs_evidence']},rationale=TEXT,evidence_ids=array(TEXT)))
RATINGS = obj(dict(**{k:{'type':'integer','minimum':0,'maximum':100} for k in ('reliability','logic','response','independence')}, evidence_ids=array(TEXT)))
VERDICT = obj(dict(critique_responses=array(CRITIQUE_REPLY),action={'type': 'string', 'enum': ['select', 'second', 'stop', 'wait']}, rationale=TEXT,
                   evidence_ids=array(TEXT), new_question=TEXT, failed_hypotheses_checked=array(TEXT),
                   code_checks=array(obj({k: TEXT for k in ('path', 'sha256', 'quote', 'conclusion')})),
                   implementation_files=array(TEXT), experiment=EXPERIMENT, acceptance=ACCEPTANCE,
                   experiment_parameter=PARAMETER,
                   debate_assessment=obj(dict(advocate=RATINGS,skeptic=RATINGS,unresolved_issues=array(TEXT),revision_required={'type':'boolean'})),
                   review_claims=obj(dict(completed_diagnostic_ids=array(TEXT),missing_evidence_ids=array(TEXT),gemini_required_for_select={'type':'boolean'}))))
IMPLEMENTATION = obj(dict(judge_issue_responses=array(obj(dict(issue=TEXT,plan_quote=TEXT,rationale=TEXT))),final_decision={'type':'string','enum':['proceed','stop','wait']},final_rationale=TEXT,edits=array(obj({k: TEXT for k in ('path', 'before_sha256', 'old', 'new')})), worker=TEXT))
PROTECTED = {'experiment_record.py', 'regression_audit.py', 'review.py'}


def model_file(root, name):
    root = root.resolve()
    path = (root / name).resolve()
    if (not path.is_relative_to(root / 'card_condition') or path.suffix != '.py'
            or path.name.startswith('cross_review') or path.name in PROTECTED or not path.is_file()):
        raise ValueError('Only existing model Python files are editable')
    return path


def verify_sources(root, packet):
    from .experiment_record import project_file
    root=root.resolve()
    for source in packet.get('latest_sources', []):
        if sha(project_file(root,source['path']))!=source['sha256']:
            raise ValueError('Review evidence changed; a new input is required')


def diagnostic_text(value):
    """Bounded diagnostics with credential values removed before any persistence."""
    text = str(value)
    for name, secret in os.environ.items():
        if re.search(r'KEY|TOKEN|SECRET|PASSWORD', name, re.I) and len(secret) >= 6:
            text = text.replace(secret, '[REDACTED]')
    text = re.sub(r'(?i)(bearer\s+)[^\s"\']+', r'\1[REDACTED]', text)
    text = re.sub(r'(?i)(["\']?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|client[_-]?secret)["\']?\s*[:=]\s*)["\']?[^\s,"\'}]+', r'\1[REDACTED]', text)
    text = re.sub(r'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{24,}(?:\.[A-Za-z0-9_-]+)*',
                  lambda m:m.group() if m.group() in ('skip_host_skill_discovery','suppress_unstable_features_warning') else '[REDACTED]', text)
    return text[-8192:]


def codex_child_config(root):
    args=['-c','project_doc_max_bytes=0','-c','memories.use_memories=false',
          '-c','memories.generate_memories=false','-c','web_search="disabled"',
          '-c','suppress_unstable_features_warning=true']
    for feature in ('memories', 'shell_tool', 'code_mode', 'apps', 'plugins',
                    'multi_agent', 'skill_search', 'browser_use', 'computer_use', 'image_generation', 'view_image'):
        args += ['--disable', feature]
    config_paths = [Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex'))) / 'config.toml', root / '.codex/config.toml']
    servers = set()
    for config_path in config_paths:
        if config_path.exists():
            config = tomllib.loads(config_path.read_text())
            servers.update(config.get('mcp_servers', {}))
            for profile in config.get('profiles', {}).values():
                servers.update(profile.get('mcp_servers', {}))
    for server in sorted(servers):
        if not server or not server.isascii() or any(not (ch.isalnum() or ch in '_-') for ch in server):
            raise ValueError('Unsupported MCP server name; do not construct an ambiguous override')
        args += ['-c', 'mcp_servers.'+server+'.enabled=false']
    args += ['--enable','code_mode_host','--enable','skip_host_skill_discovery']
    env = {k:v for k,v in os.environ.items() if k not in (
        'POKEMON_CARD_CONDITION_GEMINI_API_KEY','GEMINI_API_KEY','GOOGLE_API_KEY',
        'OPENAI_API_KEY','CODEX_API_KEY','NVIDIA_API_KEY','NEMOTRON_API_KEY','POKEMON_CARD_CONDITION_NVIDIA_API_KEY',
        'CODEX_APP_TOOLS_PIPE_PATH','CODEX_SESSION_ID','CODEX_THREAD_ID')}
    env['CARD_CONDITION_AUTO_CHILD']='1'
    return args,env


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


def source_context(root, packet, allowed=None):
    """Only plan-linked workers and their imported functions; never cut a function mid-body."""
    from .experiment_record import project_file
    root = root.resolve()
    plan = read(project_file(root, str(Path(packet['latest_result']).parent / 'plan.json')))
    names = list(allowed or []) + packet.get('implementation_sources' if allowed is not None else 'verification_sources', [])
    names += [x['path'] for x in plan.get('code_changes', [])]
    if allowed is None:
        names += list(plan.get('tracked_sha256', {}))
        names += [v['path'] for v in packet['evidence'].values() if isinstance(v,dict) and str(v.get('path','')).endswith('.py')]
    trusted=root/'trusted-experiment.json'
    if trusted.exists():
        setting=read(trusted)
        names=list(allowed or [])+setting['editable_sources']+setting.get('trainer_sources',[])
    catalog = [project_file(root,n) for n in dict.fromkeys(names + list(plan.get('input_sha256', {})))
               if str(n).endswith('.py')]
    pending, trees, requested = list(dict.fromkeys(names)), {}, {}
    while pending and len(trees) < 4:
        file = project_file(root, pending.pop(0))
        if file in trees or file.suffix != '.py' or not any(file.is_relative_to(root/d) for d in ('card_condition','artifacts')):
            continue
        text = file.read_text(); tree = ast.parse(text)
        trees[file] = (text, tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            if node.module.startswith('card_condition.'):
                candidates = [root/(node.module.replace('.', '/')+'.py')]
            else:
                candidates = [p for p in catalog if p.stem == node.module and p.is_relative_to(root/'artifacts')]
            if len(candidates) != 1 or not candidates[0].is_file():
                continue
            imported = candidates[0]
            requested.setdefault(imported,set()).update(a.name for a in node.names)
            if imported not in trees:
                pending.append(str(imported.relative_to(root)))
    sources = []
    for file,(text,tree) in trees.items():
        wanted = requested.get(file)
        selected = list(tree.body)
        omitted = []
        if wanted and '*' not in wanted:
            definitions = {n.name:n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))}
            keep = set(wanted)
            while True:
                dependencies = {n.id for name in keep & definitions.keys() for n in ast.walk(definitions[name]) if isinstance(n,ast.Name)}
                expanded = keep | (dependencies & definitions.keys())
                if expanded == keep: break
                keep = expanded
            omitted = [name for name in definitions if name not in keep]
            selected = [n for n in tree.body if not isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) or n.name in keep]
        lines=text.splitlines(True)
        excerpt=('\n'.join(''.join(lines[n.lineno-1:n.end_lineno]) for n in selected) if wanted else text)
        complete=len(excerpt.encode())<=10000
        if not complete:
            excerpt=''  # Oversized source is explicit missing evidence, never a misleading prefix.
        try:
            model_file(root,str(file.relative_to(root)));editable=allowed is None or str(file.relative_to(root)) in allowed
        except ValueError:
            editable=False
        sources.append(dict(path=str(file.relative_to(root)),sha256=sha(file),excerpt=excerpt,
                            truncated=not complete,omitted_definitions=omitted,editable=editable))
    return dict(sources=sources,omitted_sources=list(dict.fromkeys(pending)))


def provided_code_sources(context):
    sources=list(context['source_context']['sources'])
    contract=context.get('baseline_training_contract',{})
    if all(contract.get(k) for k in ('source','source_sha256','quote')):
        match=next((v for v in sources if v['path']==contract['source']),None)
        if match is None:sources.append(dict(path=contract['source'],sha256=contract['source_sha256'],excerpt=contract['quote']))
        else:
            if match['sha256']!=contract['source_sha256']:raise ValueError('Conflicting provided source SHA')
            sources=[dict(v,excerpt=v['excerpt']+'\n'+contract['quote']) if v is match else v for v in sources]
    return sources


def review_rules(path):
    if not path.exists():return ''
    # Exact child-relevant rules; parent-only reporting/coordination is not model input.
    prefixes=('- 독립 카드','- 완료한 라벨','- 학습과 검증','- 실험 전에',
              '- 공통 기록은','- 읽기 전용 Codex','- 실험 하나를','- 토큰 절약형')
    return '\n'.join(line for line in path.read_text().splitlines() if line.startswith(prefixes))


def review_context(root, folder, phase, payload):
    root = root.resolve()
    packet = read(folder / 'packet.json')
    from .cross_review_evidence import expand_evidence,compact_evidence
    packet['evidence']=expand_evidence(packet['evidence'])
    verify_sources(root, packet)
    rules = root / 'AGENTS.md'
    context = dict(payload, context_version=CODEX_CONTEXT_VERSION,
                   project_rules=review_rules(rules),
                   project_rules_source=dict(path='AGENTS.md',sha256=sha(rules)) if rules.exists() else None,
                   source_context=source_context(root,packet,payload.get('allowed_files') if phase=='implement' else None))
    from .cross_review_contract import shared_core
    context['shared_core']=shared_core(root,folder,packet)
    context['baseline_training_contract']=context['shared_core']['baseline_training_contract']
    from .cross_review_contract import registered_evidence
    registered=registered_evidence(root,packet)
    context['valid_evidence_ids']=sorted(registered)
    if phase=='correct' and payload.get('flow_role')=='advocate':
        cited={v['path'] for v in payload.get('response',{}).get('code_checks',[])}
        if cited:
            omitted=[v['path'] for v in context['source_context']['sources'] if v['path'] not in cited]
            context['source_context']['sources']=[v for v in context['source_context']['sources'] if v['path'] in cited]
            context['source_context']['omitted_sources']+=omitted
            context['source_context']['selection']='Cited complete definitions only; omitted code cannot be cited.'
            checks=payload['response']['code_checks']
            for source in context['source_context']['sources']:
                text=source['excerpt'];tree=ast.parse(text)
                definitions=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))]
                quotes=[v['quote'] for v in checks if v['path']==source['path']]
                lines=text.splitlines(True)
                chosen={n.name for n in definitions if any(q in ''.join(lines[n.lineno-1:n.end_lineno]) for q in quotes)}
                if chosen and all(any(q in ''.join(lines[n.lineno-1:n.end_lineno]) for n in definitions if n.name in chosen) for q in quotes):
                    while True:
                        dependencies={v.id for n in definitions if n.name in chosen for v in ast.walk(n) if isinstance(v,ast.Name)}
                        expanded=chosen|{n.name for n in definitions if n.name in dependencies}
                        if expanded==chosen:break
                        chosen=expanded
                    kept=[n for n in tree.body if n not in definitions or n.name in chosen]
                    source['excerpt']='\n'.join(''.join(lines[n.lineno-1:n.end_lineno]) for n in kept)
                    source['omitted_definitions']+= [n.name for n in definitions if n.name not in chosen]
            context['response']=dict(context['response'])
            context['response']['code_check_paths']=[v['path'] for v in context['response'].pop('code_checks')]
            context['response']['experiment']=dict(context['response']['experiment'])
            context['response']['experiment'].pop('success_criterion',None)
            context['response']['experiment'].pop('failure_criterion',None)
            context['response']['criteria_reference']='Keep fixed acceptance, required cohorts and actual-point guard; no success claim.'

    if packet.get('execution_inputs'):
        context['execution_inputs'] = packet['execution_inputs']
    else:
        from .experiment_record import project_file
        plan = read(project_file(root, str(Path(packet['latest_result']).parent / 'plan.json')))
        context['execution_inputs'] = {k:plan[k] for k in ('feature_sources','input_sha256','execution_inputs') if k in plan}
    if phase in ('verify','correct'):
        context.pop('packet_file',None)
        context.pop('failed_hypotheses',None)  # Included once inside evidence below.
        context['evidence'] = {k:packet[k] for k in ('stagnation_reason','error_cases','same_evaluation_metrics','failed_hypotheses','evidence')}
        context['evidence']['evidence']=registered
        context['evidence']['failed_executions'] = packet.get('failed_executions', {})
        context['evidence']['completed_diagnostics'] = packet.get('completed_diagnostics', {})
        if packet.get('execution_inputs'):
            # Cache hashes/schema are needed by implementation, not duplicated in the verdict input.
            context['execution_inputs'] = {k:v for k,v in packet['execution_inputs'].items()
                if k in ('fixed_ensemble','experiment_constraints','clarification','source_context_note')}
        if context['source_context']['sources']:
            code = context['evidence']['evidence'].get('related_code', {})
            if isinstance(code, dict) and isinstance(code.get('summary'), dict):
                code['summary'].pop('excerpt', None)  # Measurement diff; actual fitter/model sources are inline.
            summary = context['evidence']['evidence'].get('latest_plan',{}).get('summary',{})
            # Parent verifies the frozen references. Verdict needs cohort IDs and exact gates,
            # not the same source file path repeated for every inherited guard.
            if isinstance(summary.get('required_cohorts'),list):
                summary['required_cohorts']=[{k:v for k,v in cohort.items() if k!='reference_result'}
                    for cohort in summary['required_cohorts']]
            for key in ('change',):
                if isinstance(summary.get(key),str) and len(summary[key])>400:
                    summary[key]=summary[key][:400]+' [요약 생략: 전체 worker·수치 기준 참조]'
            for key,value in context['evidence']['evidence'].items():
                if key.startswith('failed_execution_') and isinstance(value,dict):
                    value['summary']={k:v for k,v in value.get('summary',{}).items()
                        if k not in ('change','hypothesis')}
                if key.startswith('failed_') and not key.startswith('failed_execution_') and isinstance(value,dict):
                    comparison=value.get('summary',{}).get('comparison',{})
                    if comparison:
                        value['summary']['comparison']={k:v for k,v in comparison.items()
                            if k in ('before','after','new_misses','new_false_positives','recovered')}
            if 'change' in summary:
                summary.pop('change')
                summary['change_reference']='linked complete worker / frozen plan path and SHA'
            latest=context['evidence']['evidence'].get('latest_result',{}).get('summary',{})
            latest.pop('comparison',None)
            latest.pop('point_comparison',None)
            latest['metrics_reference']='same_evaluation_metrics.latest_experiment / latest_experiment_actual_points'
        # The program verifies the frozen packet's measurement hashes; only code needs LLM SHA citations.
        for value in context['evidence']['evidence'].values():
            if isinstance(value,dict) and 'summary' in value:
                value.pop('path',None);value.pop('sha256',None)
                points=value['summary'].get('point_comparison')
                if isinstance(points,dict):
                    value['summary']['point_comparison']={k:v for k,v in points.items() if k in ('before','after','new_misses','new_false_positives')}
        context['execution_inputs'] = {k:v for k,v in context.get('execution_inputs',{}).items() if k!='input_sha256'}
        if phase=='correct' and context.get('flow_role')!='advocate':
            context['response']={k:v for k,v in context.get('response',{}).items()
                if k in ('hypothesis_id','cause','smallest_experiment')}
            if 'correction' in context:
                context['correction']=dict(context['correction'])
                rationale=context['correction'].get('previous_rationale')
                if isinstance(rationale,str) and len(rationale)>180:
                    context['correction']['previous_rationale']=rationale[:180]+' [전체 판정은 호출 기록에 보존]'
    else:
        context['worker_contract'] = dict(reference_env='CARD_CONDITION_EXPERIMENT_REFERENCE',output_env='CARD_CONDITION_EXPERIMENT_DIR',
            output_file='observations.json',keys=['rows','scores','point_ids','point_scores','required_cohorts'],
            project_root=str(root),reference_keys=['rows','before_scores','point_ids','point_scores','source','source_sha256','required_cohorts'],
            parameter_source='CARD_CONDITION_EXPERIMENT_DIR/plan.json: experiment_parameter.value. 선택된 수치 그대로 사용, 배율 탐색 금지.',
            rules='고정 평가 rows/정답/순서/point_ids 보존. 실제 예측만 저장. 학습·평가 그룹 분리. 기존 사람점 보호. 성공 여부는 공통 실행기가 계산.')
        context['reference_summary'] = packet['same_evaluation_metrics']
        context['worker_contract']['required_cohorts'] = ('reference.required_cohorts가 있으면 각 id/rows/point_ids를 그대로 유지하고 '
            '동일 후보로 실제 평가한 scores/point_scores를 observations.required_cohorts 목록에 저장한다. '
            '기준 점수를 후보 예측으로 복사하거나 필수 평가를 생략하지 않는다. 없으면 이 출력은 생략한다.')
        from .cross_review_execution import VERSION as EXECUTION_VERSION
        setting=root/'trusted-experiment.json'
        context['isolated_execution']=dict(adapter=EXECUTION_VERSION,
            training_input_env='CARD_CONDITION_TRAIN_INPUT',model_output_env='CARD_CONDITION_MODEL_OUTPUT',
            parameter_env='CARD_CONDITION_EXPERIMENT_PARAMETER',project_root_env='CARD_CONDITION_PROJECT_ROOT',
            training_input_keys=['features','masks','targets','point_tokens','weights','ids'],
            model_output=dict(coef='finite float list, feature dimension',bias='finite scalar'),
            training_diagnostics='Bootstrap records LBFGS iterations, final max_gradient and converged in training-diagnostics.json on success/failure. No worker reporting required. Process observations, not independently verified; missing values remain null.',
            trainer_sources=read(setting).get('trainer_sources',[]) if setting.exists() else [],
            rules='Worker executes separately for each fixed fold. Only training input is available; no evaluation data, truth, scores or network. Export numeric model.json only. Do not evaluate or write observations. Import candidate model code from project root; use provided weights. No batch/scale search.')
        context.pop('worker_contract',None)
        context.pop('contract',None)
    if phase in ('verify','correct'):
        transport=expand_evidence(read(folder/'packet.json')['evidence'],decode_tables=False)
        for key,value in context['evidence']['evidence'].items():
            if isinstance(value,dict) and 'required_cohorts' in value.get('summary',{}):
                original=transport.get(key,{}).get('summary',{})
                if isinstance(original.get('required_cohorts'),dict) and original['required_cohorts'].get('format')=='cohort_table_v1':
                    value['summary']['required_cohorts']=original['required_cohorts']
        context['evidence']['evidence_reference_format']='Resolve $ref JSON Pointers from document root. Cohort tables use explicit schema columns; counts and criteria are exact.'
    context['context_reference_root']='document'
    context=compact_evidence(context,document=True)
    return context


def sum_usage(usages, keys):
    return {key: sum(u[key] for u in usages) if usages and all(isinstance(u, dict) and type(u.get(key)) is int for u in usages) else None
            for key in keys}


LAUNCH_BLOCKED = '[codex-launch-blocked]'
MAX_LAUNCH_RETRIES = 3


def launch_not_sent(directory):
    """True only when the app-server provably never received a turn: no model request, no usage."""
    try:
        value = read(directory / 'execution.json')
    except (OSError, ValueError):
        return False
    return (value.get('transport') == 'app-server' and value.get('turn_requests') == 0
            and not value.get('turn_completions') and value.get('usage') is None)


def archive_launch_failure(folder, directory):
    """Move a never-sent attempt out of codex/ so it counts neither as a call nor as unknown usage."""
    target_root = folder / 'superseded-codex'
    target_root.mkdir(exist_ok=True)
    taken = sorted(target_root.glob(directory.name.split('-')[0] + '-*'))
    if len(taken) >= MAX_LAUNCH_RETRIES:
        raise ValueError(LAUNCH_BLOCKED + ' Codex app-server did not start ' + str(len(taken)) + ' times; fix the environment first')
    target = target_root / (directory.name + '-launch-failure-' + str(len(taken) + 1))
    directory.rename(target)
    return target


def stored_phase_one_correction(folder, phase, payload, directory):
    """A review folder holds one verify and one correction; replay the stored pre-critique correction.

    Its error list can differ from today's only because validators changed, which must not orphan the
    already-paid response (the digest would differ and the one-correction cap would otherwise block it).
    """
    if phase != 'correct' or 'correction' not in payload or 'critiques' in payload:
        return None
    stored = [p for p in (folder / 'codex').glob('correct-*/call.json') if p.parent != directory]
    if len(stored) != 1:
        return None
    try:
        entry, previous = read(stored[0]), read(stored[0].parent / 'input.json')
    except (OSError, ValueError):
        return None
    if entry.get('status') != 'complete' or 'correction' not in previous or 'critiques' in previous:
        return None
    return dict(entry, directory=str(stored[0].parent))


def launch_failure_detail(directory):
    if launch_not_sent(directory):
        return (' ' + LAUNCH_BLOCKED + ' codex app-server가 모델 요청 전에 시작되지 못했습니다(모델 호출·토큰 사용 0). '
                'Codex 샌드박스 밖의 일반 터미널(또는 권한 상승 실행)에서 ./review --auto를 다시 실행하면 저장 상태에서 이어갑니다.')
    return ''


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
    prompt = '한국어 JSON. evidence_ids는 valid_evidence_ids 안에서만 선택한다. 도구 없이 동결 근거·project_rules만 사용하고 source_context 원문·SHA를 인용한다. '
    if phase in ('verify','correct'):
        from .cross_review_roles import CODEX_ADVOCATE
        prompt += CODEX_ADVOCATE+' failed_hypotheses_checked는 가설 실패 ID 전부만, review_claims.completed_diagnostic_ids는 완료 진단 ID 전부다. 실행 실패는 반증이 아니다. critique_responses는 실제 Gemini 비판 ID마다 정확히 하나, 비판 전에는 빈 목록이다. debate_assessment 점수는 심판 전0. 검증할 변수·사전 수치 기준이 있으면 select, 남은 Gemini>0이고 반증이 필요하면 second, 근거 부족 stop, 실제 사람/자료 의존 wait. implementation_files에는 수정할 허용 모델 소스만 넣는다. 새 격리 worker는 구현 단계의 별도 출력이므로 이 목록에 넣지 않는다. 모델 소스 수정 없이 worker에서 고정 실험 변수를 적용할 수 있으면 빈 목록도 가능하다. experiment_parameter(name/baseline/value/scope)를 확정하고 효과를 추정하지 않는다. missing_evidence_ids는 실제 없는 것만. gemini_required_for_select=false. '
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


class VerdictValidationError(ValueError):
    def __init__(self,errors):
        self.errors=errors
        super().__init__('; '.join(item['check']+': '+item['error'] for item in errors))


def verdict_errors(root,result,verdict,require_parameter=False):
    root=root.resolve()
    verify_sources(root,result['packet'])
    from .cross_review_contract import registered_evidence
    from .experiment_record import project_file
    allowed=registered_evidence(root,result['packet'])
    errors=[]
    def check_shape():
        if not isinstance(verdict,dict):raise ValueError('Invalid Codex verdict')
        keys=set(VERDICT['properties'])
        if not keys-{'experiment_parameter','review_claims','debate_assessment','critique_responses'} <= set(verdict) <= keys or verdict['action'] not in ('select', 'second', 'stop', 'wait'):
            raise ValueError('Invalid Codex verdict')
        if not isinstance(verdict['rationale'], str) or not verdict['rationale'].strip():
            raise ValueError('Codex must justify its verdict')

    def check_critique_responses():
        if 'critique_responses' in verdict:
            replies=verdict['critique_responses']
            if (not isinstance(replies,list) or any(not isinstance(v,dict) or set(v)!=set(CRITIQUE_REPLY['properties'])
                    or v['disposition'] not in ('accept','reject','needs_evidence') or not isinstance(v['critique_id'],str)
                    or not isinstance(v['rationale'],str) or not v['rationale'].strip() or not isinstance(v['evidence_ids'],list)
                    or not v['evidence_ids'] or any(not isinstance(k,str) or k not in allowed for k in v['evidence_ids']) for v in replies)):
                raise ValueError('Invalid critique responses')

    def check_debate_assessment():
        if 'debate_assessment' in verdict:
            from .cross_review_adversarial import WEIGHTS
            assessment=verdict['debate_assessment']
            if (not isinstance(assessment,dict) or set(assessment)!=set(VERDICT['properties']['debate_assessment']['properties'])
                    or type(assessment['revision_required']) is not bool
                    or not isinstance(assessment['unresolved_issues'],list)
                    or any(not isinstance(v,str) for v in assessment['unresolved_issues'])):
                raise ValueError('Invalid debate assessment')
            for side in ('advocate','skeptic'):
                rating=assessment[side]
                if (not isinstance(rating,dict) or set(rating)!=set(RATINGS['properties'])
                        or any(type(rating[k]) is not int or not 0<=rating[k]<=100 for k in WEIGHTS)
                        or not isinstance(rating['evidence_ids'],list)
                        or any(not isinstance(v,str) for v in rating['evidence_ids'])):
                    raise ValueError('Invalid independent judge ratings')

    def check_claims_schema():
        if require_parameter or 'review_claims' in verdict:
            claims=verdict.get('review_claims')
            if not isinstance(claims,dict) or set(claims)!=set(VERDICT['properties']['review_claims']['properties']):
                raise ValueError('Explicit review claims are required')

    def check_claims_dependency():
        if require_parameter or 'review_claims' in verdict:
            claims=verdict.get('review_claims')
            if claims['gemini_required_for_select'] is not False:
                raise ValueError('Zero remaining Gemini calls does not prohibit experiment selection')

    def check_completed_diagnostics():
        if require_parameter or 'review_claims' in verdict:
            claims=verdict.get('review_claims')
            if set(claims['completed_diagnostic_ids'])!=set(result['packet'].get('completed_diagnostics',{})):
                raise ValueError('Completed diagnostic history was omitted or misstated; expected='+','.join(sorted(result['packet'].get('completed_diagnostics',{}))))

    def check_missing_evidence():
        if require_parameter or 'review_claims' in verdict:
            claims=verdict.get('review_claims')
            if set(claims['missing_evidence_ids']) & (set(allowed)|set(result['packet'].get('completed_diagnostics',{}))):
                raise ValueError('Claimed missing evidence is already supplied')

    def check_evidence_ids():
        if verdict['action'] in ('select','second') or require_parameter:
            refs = verdict['evidence_ids']
            if not refs or any(ref not in allowed for ref in refs):
                raise ValueError('Codex cited unknown evidence; unexpected='+','.join(sorted(set(refs)-set(allowed)))+'; allowed='+','.join(sorted(allowed)))

    def check_failure_history():
        if verdict['action'] in ('select','second') or require_parameter:
            if set(verdict['failed_hypotheses_checked']) != set(result['packet']['failed_hypotheses']):
                expected=set(result['packet']['failed_hypotheses']);checked_ids=set(verdict['failed_hypotheses_checked'])
                raise ValueError('Failure history mismatch; missing='+','.join(sorted(expected-checked_ids))+'; unexpected='+','.join(sorted(checked_ids-expected)))

    def check_code_sources():
        if verdict['action'] in ('select','second') or require_parameter:
            checked = set()
            from .experiment_record import project_file
            contract=read(root/'trusted-experiment.json').get('baseline_training_contract',{}) if (root/'trusted-experiment.json').exists() else {}
            linked = {s['path'] for s in provided_code_sources(dict(source_context=source_context(root,result['packet']),baseline_training_contract=contract))}
            for check in verdict['code_checks']:
                if check['path'] not in linked:
                    raise ValueError('Code citation was not provided in the frozen context')
                file = project_file(root, check['path'])
                if (sha(file) != check['sha256'] or len(check['quote'].strip()) < 10
                        or check['quote'] not in file.read_text() or not check['conclusion'].strip()):
                    raise ValueError('Code citation does not match actual source')
                checked.add(str(file.relative_to(root)))
            for name in verdict['implementation_files']:
                model_file(root, name)  # Read-only evidence never becomes editable through a citation.
            if (verdict['action'] in ('select','second') and not checked) or not set(verdict['implementation_files']).issubset(checked):
                raise ValueError('Every editable source must be checked')

    def check_acceptance():
        if verdict['action']=='select':
            from .experiment_record import acceptance_rules
            acceptance_rules(verdict['acceptance'])

    def check_actual_point_guard():
        if verdict['action']=='select':
            from .experiment_record import point_reference
            from .cross_review_evidence import experiment
            baseline=experiment(project_file(root,result['packet']['latest_result']))
            _,points=point_reference(baseline['result'],baseline['rows'])
            if bool(points)!=verdict['acceptance']['require_actual_point_guard']:
                raise ValueError('Actual point guard must match existing human evidence; expected='+str(bool(points))+'; received='+str(verdict['acceptance']['require_actual_point_guard'])+'; inherited cohort guards remain mandatory')

    def check_experiment_parameter():
        if verdict['action']=='select':
            parameter=verdict.get('experiment_parameter')
            if require_parameter or parameter is not None:
                if (not isinstance(parameter,dict) or set(parameter)!=set(PARAMETER['properties'])
                        or not all(isinstance(parameter.get(k),str) and parameter[k].strip() for k in ('name','scope'))
                        or any(type(parameter.get(k)) not in (int,float) or not math.isfinite(parameter[k]) for k in ('baseline','value'))
                        or parameter['baseline']==parameter['value']):
                    raise ValueError('Select requires one fixed finite experimental parameter')

    def check_numeric_acceptance():
        if verdict['action']=='select':
            prior=read(project_file(root,str(Path(result['packet']['latest_result']).parent/'plan.json'))).get('acceptance',{})
            rules=verdict['acceptance']
            if (any(rules[k]>prior[k] for k in ('max_fp','max_fn') if k in prior)
                    or prior.get('no_new_errors') and not rules['no_new_errors']):
                raise ValueError('Cannot relax the previous numeric acceptance')

    def check_second_question():
        if verdict['action']=='second' and not verdict['new_question'].strip():raise ValueError('A new falsification question is required')
    checks=(('shape',check_shape),('critique_responses',check_critique_responses),('debate_assessment',check_debate_assessment),('claims_schema',check_claims_schema),('claims_dependency',check_claims_dependency),('completed_diagnostics',check_completed_diagnostics),('missing_evidence',check_missing_evidence),('evidence_ids',check_evidence_ids),('failure_history',check_failure_history),('code_sources',check_code_sources),('acceptance',check_acceptance),('actual_point_guard',check_actual_point_guard),('experiment_parameter',check_experiment_parameter),('numeric_acceptance',check_numeric_acceptance),('second_question',check_second_question))
    for name,check in checks:
        try:check()
        except (ValueError,TypeError,KeyError,AttributeError) as error:
            errors.append(dict(check=name,error=str(error)))
            if name=='shape':break
    return errors


def validate_verdict(root,result,verdict,require_parameter=False):
    errors=verdict_errors(root,result,verdict,require_parameter=require_parameter)
    if errors:raise VerdictValidationError(errors)


def token_report(folder, result):
    calls = [read(p) for p in (folder / 'codex').glob('*/call.json')]
    codex = sum_usage([c.get('usage') for c in calls], ('input_tokens', 'cached_input_tokens', 'output_tokens', 'reasoning_output_tokens'))
    codex['total_tokens'] = codex['input_tokens']+codex['output_tokens'] if codex['input_tokens'] is not None and codex['output_tokens'] is not None else None
    gemini = sum_usage([c.get('usage') for c in result.get('attempts', [])],
                       ('prompt_token_count', 'candidates_token_count', 'thoughts_token_count', 'total_token_count'))
    report = dict(codex_calls=len(calls), codex_usage=codex, gemini_calls=len(result.get('attempts', [])), gemini_usage=gemini,
                  before_automation_codex_usage=None, reduction_percent=None,
                  comparison_note='동일 작업의 자동화 이전 Codex 실측 기준 없음. CLI 사용량과 현재 채팅 사용량은 별개이며 절감률 미측정.')
    reuse = folder / 'response_reuse.json'
    if reuse.exists():
        report.update(gemini_calls=0, gemini_response_imports=len(result.get('attempts', [])),
                      response_reuse=read(reuse))
    from .cross_review_nemotron import usage_totals
    extra=[read(p) for p in (folder/'nemotron').glob('*.json') if p.name!='status.json']
    report.update(nemotron_calls=sum(bool(v.get('attempted')) for v in extra),nemotron_usage=usage_totals(extra))
    save(folder / 'token_report.json', report)
    return report


class UntrustedExecutionError(ValueError):
    pass


def implement(root, folder, selected, verdict, data):
    raise UntrustedExecutionError('Generated workers require an isolated trusted evaluation path; automatic execution is disabled')


def stage_implementation(root, folder, verdict, data):
    """Save a reviewable proposal only. No project edits and no worker execution."""
    if set(data)!={'edits','worker'} or not isinstance(data['worker'],str):
        raise ValueError('Invalid implementation proposal')
    ast.parse(data['worker'])
    edits=[];proposed={}
    if not isinstance(data['edits'],list):raise ValueError('Invalid edits')
    for edit in data['edits']:
        if set(edit)!={'path','before_sha256','old','new'} or edit['path'] not in verdict['implementation_files']:
            raise ValueError('Unapproved source edit')
        file=model_file(root,edit['path']);check=next(c for c in verdict['code_checks'] if c['path']==edit['path'])
        if sha(file)!=edit['before_sha256'] or sha(file)!=check['sha256']:
            raise ValueError('Source changed after verification')
        current=proposed.get(edit['path'],file.read_text())
        if not edit['old'] or current.count(edit['old'])!=1:
            raise ValueError('Edit anchor must match exactly once')
        proposed[edit['path']]=current.replace(edit['old'],edit['new'],1)
        ast.parse(proposed[edit['path']])
        edits.append(edit)
    path=folder/'implementation-proposal.json'
    save(path,dict(edits=edits,worker=data['worker'],applied=False,executed=False,
        blocker='Trusted isolated execution and independent model evaluation are not configured'))
    return path


def restore_unaccepted(root, folder):
    transaction = read(folder / 'implementation/apply.json')
    for index, item in enumerate(transaction['files']):
        file = model_file(root, item['path'])
        baseline=folder / 'implementation' / (str(index)+'-before.py')
        if sha(baseline)!=item['before_sha256'] or sha(file) not in (item['before_sha256'],item['after_sha256']):
            raise ValueError('User source changed; do not overwrite during rollback')
    for index, item in enumerate(transaction['files']):
        atomic_write(root / item['path'], (folder / 'implementation' / (str(index)+'-before.py')).read_text())


def measured_gain(result, *, verified=False):
    if not verified:return False
    cohorts=[result,*result.get('required_cohorts',[])]
    return (result['acceptance_passed'] and any(c['comparison']['informative_improvement'] for c in cohorts)
        and all(c['comparison']['no_new_errors'] and not (c.get('point_comparison') or {}).get('new_misses') for c in cohorts))


def render_result(root, experiment_folder, verified_reference=None):
    root = root.resolve()
    from PIL import Image, ImageDraw, ImageOps
    result = read(experiment_folder / 'result.json')
    blocks = ['<!doctype html><meta charset="utf-8"><title>자동 실험 결과</title>',
              '<h1>개발용 동일 평가 자료 비교 — 독립 검증 아님</h1>',
              '<p>사전 성공 기준 충족: ' + str(result['acceptance_passed']) + '</p>']
    evaluations = [('주 평가', result)] + [('필수 평가: ' + c['id'], c) for c in result.get('required_cohorts', [])]
    for label, result in evaluations:
        cmp = result['comparison']
        blocks.extend(['<h2>' + html.escape(label) + '</h2>',
                       '<p>해당 평가 기준 충족: ' + str(result.get('primary_acceptance_passed', result['acceptance_passed'])) + '</p>',
                       '<pre>' + html.escape(json.dumps(cmp, ensure_ascii=False, indent=2)) + '</pre>'])
        for metric, denominator in [('fp',cmp['before']['fp']+cmp['before']['tn']),('fn',cmp['before']['fn']+cmp['before']['tp'])]:
            old,new=cmp['before'][metric],cmp['after'][metric]
            delta=(new-old)/denominator*100 if denominator else None
            blocks.append('<p>'+metric.upper()+': '+str(old)+'/'+str(denominator)+' → '+str(new)+'/'+str(denominator)
                          +' / 변화 '+(str(round(delta,2))+'%p' if delta is not None else '미확인')+'</p>')
        if result.get('point_comparison'):
            blocks.append('<h2>실제 사람점 누락 비교</h2><pre>'+html.escape(json.dumps(result['point_comparison'],ensure_ascii=False,indent=2))+'</pre>')
        for row, before, after in zip(result['rows'], result['before_scores'], result['scores']):
            blocks.append('<h2>' + html.escape(row['id']) + '</h2><p>사람 정답: ' + str(row['target'])
                          + ' / 이전: ' + str(before) + ' / 이후: ' + str(after) + '</p>')
            image = (root / row.get('image', '')).resolve()
            if row.get('image') and image.is_file() and (image.is_relative_to(root) or verified_reference is not None and any(row==r for r in verified_reference['rows']+sum([c['rows'] for c in verified_reference.get('required_cohorts',[])],[]))):
                with Image.open(image) as original:
                    picture = ImageOps.exif_transpose(original).convert('RGB')
                # Match data.load_manifest's decoded-size + RGB-pixels identity contract.
                if row.get('image_sha256') not in (sha(image),hashlib.sha256(str(picture.size).encode()+picture.tobytes()).hexdigest()):
                    blocks.append('<p>사진 해시 불일치 — 다른 사진을 평가 결과로 표시하지 않습니다.</p>')
                    continue
                box = row['box']
                if len(box) == 4 and all(0 <= x <= 1 for x in box):
                    ImageDraw.Draw(picture).rectangle((box[0]*picture.width, box[1]*picture.height, box[2]*picture.width, box[3]*picture.height), outline='cyan', width=4)
                    picture.thumbnail((700,700))
                    output = io.BytesIO(); picture.save(output, format='JPEG')
                    blocks.append('<img alt="검증 구역" src="data:image/jpeg;base64,' + base64.b64encode(output.getvalue()).decode() + '">')
            else:
                blocks.append('<p>사진 경로 없음 — 수치만 표시</p>')
    atomic_write(experiment_folder / 'comparison.html', '\n'.join(blocks))


def run_auto(root, folder, result, backend=None, gemini_caller=None, token_budget=CODEX_TOKEN_BUDGET, call_ceiling=None):
    from .workspace_lock import workspace_lock
    from .development_review import review_scope
    with workspace_lock(root, 'automatic review'), review_scope():
        return _run_auto(root, folder, result, backend, gemini_caller, token_budget, call_ceiling)


def _run_auto(root, folder, result, backend=None, gemini_caller=None, token_budget=CODEX_TOKEN_BUDGET, call_ceiling=None):
    from .cross_review_flow import run_codex_first
    return run_codex_first(root,folder,result,backend=backend,gemini_caller=gemini_caller,
                           token_budget=token_budget,call_ceiling=call_ceiling)
