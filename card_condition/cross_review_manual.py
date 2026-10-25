"""Interactive review of latest project evidence using the existing checkpoint workflow."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

from .cross_review import EvidencePacketTooLarge, error_diagnostic, execute, validate, digest, korean_response_ok, response_ok, FIELDS, KOREAN_VERSION, GROUNDED_KOREAN_VERSION, GROUNDED_VERSIONS, CRITIC_VERSION, VERSION
from .cross_review_evidence import latest_packet
from .experiment_record import LatestExperimentUnavailable
from .review import atomic_write
from .cross_review_auto import LAUNCH_BLOCKED

ROOT = Path(__file__).resolve().parents[1]
TITLES = {
    'hypothesis_id': '가설 ID(식별자)', 'cause': '원인 가설(미검증)', 'evidence': '관찰 근거',
    'counter_evidence': '반대 증거', 'smallest_experiment': '다음 최소 실험 제안(아직 실행하지 않음)',
    'success_criterion': '성공 기준', 'failure_criterion': '실패 기준',
    'human_confirmation': '필요한 사람 확인',
}


STATUS_LABELS = {
    'experiment_evaluated':'독립 계산 평가 완료(개발용 평가·일반화 미확인)',
    'experiment_execution_failed':'공통 실험 실행 실패(성능 미측정)',
    'no_new_evidence': '새 실험 근거가 없어 종료',
    'unsupported_proposal': '실패 이력·새 근거 대조가 부족해 종료',
    'unresolved': '실험 미채택으로 검토 종료', 'experiment_selected': '실험 제안 선택 완료(실험 실행 전)',
    'call_limit': '호출 상한에 도달해 종료', 'repeated_claim': '같은 주장 반복으로 종료',
    'no_new_evidence_or_hypothesis': '새 질문·근거가 없어 종료',
    'quota_error': 'API 사용 한도 오류로 종료', 'auth_error': 'API 인증 오류로 종료',
    'request_error': 'API 요청 오류로 종료(과거 기록은 응답 형식 오류일 수도 있음)',
    'response_error': 'Gemini 응답 수신 후 JSON·필드 형식 검사 실패로 종료(자동 재호출 없음)',
    'response_language_mismatch': '한국어 응답 조건을 충족하지 않아 종료(원문 저장, 자동 재호출 없음)',
    'token_budget': '토큰 예산에 도달해 종료', 'time_budget': '시간 예산에 도달해 종료',
    'live_blocked': '무료 프로젝트·전용 키 설정 확인이 필요해 호출 차단',
    'prior_request_pending': '이전 요청의 결과가 불명확하여 중복 호출 차단',
    'compare': '기본 검토 완료·추가 검토 대기',
    'awaiting_comparison': '저장된 검토 복원·추가 검토 대기',
}


def show_counts(label, comparison):
    if not comparison:
        return
    before, after = comparison['before'], comparison['after']
    defects, normals = after['tp'] + after['fn'], after['tn'] + after['fp']
    print(label + ': 오탐 ' + str(before['fp']) + '→' + str(after['fp']) + '/' + str(normals)
          + ', 결함 누락 ' + str(before['fn']) + '→' + str(after['fn']) + '/' + str(defects))


def save(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2))


def review_identity(packet, config):
    from .cross_review_evidence_manifest import expand_manifest
    evidence = {key: value for key, value in packet.items() if key not in ('topic', 'manual_run_purpose','fresh_evidence_ids','freshness_reference')}
    if 'latest_sources' in evidence:
        evidence['latest_sources'] = expand_manifest(packet)
    related = evidence.get('evidence', {}).get('related_code', {})
    summary = related.get('summary', {}) if isinstance(related, dict) else {}
    if isinstance(summary, dict) and summary.get('budget_truncated'):
        evidence['evidence'] = dict(evidence['evidence'], related_code=dict(related, summary={key: value for key, value in summary.items() if key != 'excerpt'}))
    return digest([evidence, config['model'], config.get('prompt_version', VERSION)])


def next_steps(folder, result):
    from .cross_review_debate import render
    render(ROOT,folder)
    response = result.get('selected') or result.get('response', {})
    status = result['status']
    if status in ('no_new_evidence','unsupported_proposal'):
        response={}
        category,action='collect_evidence','새 근거가 없거나 제안의 근거 대조가 유효하지 않아 종료했습니다. 기존 실패 실험을 반복하지 말고 필요한 진단 근거부터 정리하세요.'
    elif status not in ('compare', 'awaiting_comparison', 'unresolved', 'experiment_selected','experiment_evaluated',
                      'call_limit', 'repeated_claim', 'no_new_evidence_or_hypothesis','rejected_hypothesis'):
        category, action = 'check_error', '오류·차단 사유와 저장 기록을 먼저 확인하세요. 같은 요청을 재전송하거나 제안을 실험 결론으로 사용하지 마세요.'
    elif response.get('human_confirmation', '').strip():
        category, action = 'check_existing_evidence', '기존 승인 라벨·근거부터 대조하세요. 완료 라벨은 다시 묻지 말고 실제로 부족한 자료만 확인하세요.'
    elif response.get('hypothesis_id') in result['packet']['failed_hypotheses'] and not result['packet'].get('reopen_evidence', {}).get(response['hypothesis_id']):
        category, action = 'reject_repeated_hypothesis', '이미 실패한 가설입니다. 새로운 반증 근거가 없으므로 같은 실험을 반복하지 마세요.'
    elif status in ('repeated_claim', 'no_new_evidence_or_hypothesis'):
        category, action = 'collect_evidence', '주장이 반복됐습니다. 부족한 진단 근거를 정리하고 새 자료가 생기기 전에는 토론을 반복하지 마세요.'
    elif all(response.get(key, '').strip() for key in ('cause', 'smallest_experiment', 'success_criterion', 'failure_criterion')):
        category, action = 'check_experiment', 'Codex에서 제안을 코드·실패 이력과 대조해 변경 변수 하나와 대조 조건을 확정하세요. 채택한 실험만 같은 평가 자료로 실행·비교하세요.'
    else:
        category, action = 'complete_experiment_plan', '실험 또는 판정 기준이 부족합니다. Codex에서 기존 근거로 보완하고, 없는 정답·수치는 추정하지 마세요.'
    automation = json.loads((folder/'automation.json').read_text()) if (folder/'automation.json').exists() else None
    if automation and automation['status']=='trusted_execution_required':
        category,action='review_implementation_proposal','독립 심판의 실험 계획 승인은 받았지만 생성 코드/worker는 적용·실행하지 않았습니다. implementation-proposal.json을 확인하세요. 신뢰된 격리 실행·독립 모델 평가 경로가 없어 자동 학습·성능 채택을 보류합니다.'
    elif automation and automation['status']=='completed':
        category, action = 'experiment_completed', '실험 실행까지 완료했습니다. 동일 평가 자료의 결과와 comparison.html을 확인하세요. 사전 기준 충족은 독립 성능 검증을 뜻하지 않습니다.'
    elif automation and automation['status']=='experiment_rejected':
        category,action='experiment_rejected','공통 실험·별도 평가 결과 사전 기준 미달 또는 개선 없음으로 후보를 폐기했습니다. 원본 소스는 유지했습니다. comparison.html을 확인하고 같은 실험을 반복하지 마세요.'
    elif automation and automation['status']=='execution_failed':
        category,action='check_error','격리 실행 또는 평가가 실패했습니다. 실행 실패를 가설 실패·성능 수치로 해석하지 말고 저장 오류를 확인하세요. 자동 재시도하지 않습니다.'
    elif automation and automation['status']=='needs_human':
        category, action = 'check_existing_evidence', 'Codex 또는 Gemini가 사람 근거를 요구했습니다. automation.json과 기존 승인 자료를 대조하고 실제 부족한 근거만 확인하세요.'
    elif automation and automation['status']=='review_limit':
        category, action = 'collect_evidence', '기본 검토와 교정 슬롯을 소진했습니다. 추가 모델 요청 없이 쟁점·부족한 근거를 보존합니다. 새 근거 없이 같은 검토를 반복하지 마세요.'
    elif automation and automation['status'] in ('stopped','rejected_hypothesis'):
        category, action = 'collect_evidence', '자동 검토가 제안을 보류·거절했습니다. automation.json의 판단 이유를 확인하고 새 반증 근거 없이 실험을 반복하지 마세요.'
    elif automation and automation['status']=='judge_unavailable' and automation.get('unjudged_candidate'):
        response=dict(automation['unjudged_candidate']['plan']['experiment'])
        category,action='review_unjudged_candidate','독립 심판 없이 토론이 끝났습니다(Codex 수정안·Gemini 비판은 저장됨). 이 계획은 심판 승인을 받지 않아 자동 실행하지 않았습니다. Codex가 코드·실패 이력으로 직접 대조해 채택 여부를 정하세요. 심판을 다시 쓰려면 무료 검증 기록을 갱신한 뒤 같은 명령을 다시 실행하면 저장 상태에서 이어갑니다.'
    elif automation and automation['status']=='validation_or_execution_error' and LAUNCH_BLOCKED in str(automation.get('reason','')):
        category,action='run_outside_sandbox','codex app-server가 모델 요청 전에 시작되지 못했습니다(모델 호출·토큰 사용 0). Codex 샌드박스 밖의 일반 터미널(또는 권한 상승 실행)에서 ./review --auto를 다시 실행하면 저장 상태에서 이어갑니다.'
    elif automation:
        category, action = 'check_automation', '자동화 상태와 기록을 확인하세요. 저장된 반론은 보존됐지만 결과 불명 작업을 재실행하거나 완료된 개발로 취급하지 마세요.'
    summary = dict(debate_html=str(folder/'debate.html'), category=category, next_action=action, proposal=response,
                   approved_experiment=result['status'] == 'experiment_selected', performance_improvement_verified=False,
                   result_file=str(folder / 'result.json'))
    if automation:
        summary['automation'] = automation
    save(folder / 'next_steps.json', summary)
    lines = ['# 다음 할 일', '', '이 안내는 프로그램이 만든 요약이며 Gemini의 반론 원문이 아닙니다.',
             '', '검토 상태: ' + STATUS_LABELS.get(status, status), '', action]
    if status in ('no_new_evidence','unsupported_proposal'):
        lines += ['', '실행할 새 실험 제안: 없음. 새 측정·코드 근거가 생길 때까지 종료합니다.']
    elif category == 'run_outside_sandbox':
        lines += ['', '사용 가능한 반론·제안: 없음. 모델 호출 0회, 토큰 사용 0. 같은 명령을 샌드박스 밖에서 다시 실행하세요.']
    elif category == 'check_error':
        lines += ['', '사용 가능한 반론: 없음. 이 기록으로 Gemini의 원인 가설이나 실험 제안을 채택할 수 없습니다.',
                  'Codex에 요청: 저장된 오류와 전송 근거를 진단하세요. 추가 Gemini 호출이나 제안 실험은 하지 마세요.']
    else:
        lines += ['', '## 채택된 실험과 판정 기준' if result.get('selected') else '## 심판 미승인 후보 계획(자동 실행 안 함)' if category == 'review_unjudged_candidate' else '## 저장된 제안(미검증·미채택)', '']
        lines += [('실행한 실험' if key=='smallest_experiment' and automation and automation['status']=='completed' else title)
                  + ': ' + (response.get(key) or '미기재') for key, title in TITLES.items()]
        lines += ['', '검토 합의는 성능 개선이 아닙니다. 실험 결과 전 새 토론을 자동 시작하지 않습니다.',
                  'Codex에 요청: 위 다음 행동부터 수행하세요. 기존 근거·코드와 대조하고 반복 제안은 제외하세요. 실험이 채택되기 전에는 실행하지 마세요. 추가 Gemini 호출은 하지 마세요.']
    lines += ['', '전송 근거: ' + str(folder / 'packet.json'), '', '결과: ' + str(folder / 'result.json')]
    atomic_write(folder / 'next_steps.md', '\n'.join(lines) + '\n')
    print('\n[다음 할 일]', action)
    print('Codex에 전달할 파일:', folder / 'next_steps.md')
    print('에이전트 토론 HTML:',folder/'debate.html')
    if automation and automation.get('comparison_html'):
        print('동일 평가 자료 성능 비교 HTML:', automation['comparison_html'])


def counter_review(packet, response, used):
    """Choose a grounded countercheck locally; never spend an API call planning one."""
    evidence = packet['evidence']
    claim = (response.get('cause', '') + ' ' + response.get('smallest_experiment', '')).casefold()
    if not response.get('cause', '').strip():
        return None
    if 'causal' not in used:
        question = ('현재 원인 가설과 관찰된 증상을 구분하세요. 최신 실험의 전후 수치·남은 오류·관련 코드 중 '
                    '가설과 모순되는 근거를 먼저 대조하고, 기존에 실패한 가설을 되풀이하는지 확인하세요. '
                    '새 반증 근거가 없다면 실패 가설을 다시 열지 마세요.')
        refs = ['latest_result', 'remaining_errors', 'related_code', 'executed_code']
        if any(word in claim for word in ('logsumexp', 'loss', '손실', '목적함수', 'objective')):
            question += ' 학습 손실 함수와 추론 점수·판정 임계값을 구분하고, 손실 함수가 남은 오탐의 원인이라는 주장을 코드로 검증하세요.'
        if any(word in claim for word in ('geometry', 'mask', '공간', '마스크', '위치')):
            question += ' 공간 진단의 적용 대상과 결함 사례 포함 여부를 확인하고, 진단 결과가 원인을 입증하는지 반박하세요.'
            refs.append('latest_diagnostic')
        refs += list(packet.get('failed_hypotheses', {}).get(response.get('hypothesis_id'), []))
        check = 'causal'
    elif 'falsification' not in used:
        question = ('현재 응답의 최소 실험과 성공·실패 기준이 원인 가설을 실제로 반증할 수 있는지 검토하세요. '
                    '최신 실험 계획·남은 오류와 대조해 변경 변수 하나, 대조 조건, 동일 평가 자료의 오탐·누락 분모를 명시하세요. '
                    '사람이 승인한 실제 결함점 평가가 있으면 누락도 보호하고, 없는 정답은 추정하지 마세요. '
                    '이미 시행한 실험과 달라지는 점이 없거나 새 근거가 없으면 추가 토론 대신 부족한 근거를 명시하세요.')
        refs = ['latest_plan', 'latest_result', 'remaining_errors', 'latest_diagnostic']
        check = 'falsification'
    else:
        return None
    refs = list(dict.fromkeys(key for key in refs if key in evidence))
    if 'latest_result' not in refs or len(refs) < 2:
        return None
    return dict(action='second', rationale=question, new_question=question,
                evidence_ids=refs, countercheck_id=check, previous_proposal=response)


def review(base, interactive=False, automatic=False, max_new_calls=None, fresh=False):
    active_path = base / 'active.json'
    active = json.loads(active_path.read_text()) if active_path.exists() else None
    if active and not active['finished']:
        previous_folder = Path(active['directory'])
        previous_packet = json.loads((previous_folder / 'packet.json').read_text())
        if previous_packet.get('source_mode') != 'project-latest':
            save(previous_folder / 'superseded.json', {'reason': 'User switched from example to latest project evidence; old checkpoint retained'})
            print('기존 예제 검토는 기록을 보존하고 최신 자료로 새 검토를 시작합니다.')
            active = None
    if not interactive or not active or active['finished']:
        packet = latest_packet(ROOT)
        config = json.loads((ROOT / 'artifacts/cross-review-20261019/local-config.json').read_text())
        config.update(prompt_version=CRITIC_VERSION if automatic else KOREAN_VERSION, max_calls=3, max_output_tokens=4096, input_budget=72000, output_budget=12288,
                      total_budget=84288, seconds=600)
        validate(packet, config)
        identity = review_identity(packet, config)
        matches = []
        for path in base.glob('*/packet.json'):
            previous_packet = json.loads(path.read_text())
            previous_config = json.loads((path.parent / 'config.json').read_text())
            compatible=(previous_config.get('prompt_version')==GROUNDED_KOREAN_VERSION
                and review_identity(previous_packet,dict(previous_config,prompt_version=KOREAN_VERSION))==identity)
            if review_identity(previous_packet, previous_config) == identity or compatible:
                result_path = path.parent / 'result.json'
                previous_result = json.loads(result_path.read_text()) if result_path.exists() else {}
                response = previous_result.get('response')
                usable = (previous_result.get('status') in ('compare', 'awaiting_comparison', 'unresolved', 'critique_recorded',
                          'experiment_selected', 'call_limit', 'repeated_claim', 'no_new_evidence_or_hypothesis')
                          and response_ok(response,previous_config.get('prompt_version', VERSION))
                          and korean_response_ok(response, previous_config.get('prompt_version', VERSION)))
                matches.append((usable, path.stat().st_mtime_ns, str(path), path))
        if matches and not fresh:
            selected = max(matches)
            folder = selected[3].parent
            packet = json.loads((folder / 'packet.json').read_text())
            config = json.loads((folder / 'config.json').read_text())
            print('같은 자료·모델·프롬프트의 기존 검토를 재사용합니다. 새 검토를 만들지 않습니다.')
            if selected[0]:
                print('오류 기록보다 정상 응답이 저장된 검토를 우선 선택했습니다.')
        else:
            if fresh and matches:
                print('--fresh: 같은 자료의 기존 검토는 기록만 보존하고 새 검토를 시작합니다. 새 모델 요청이 발생할 수 있습니다.')
            folder = base / uuid4().hex[:12]
            packet['topic'] = 'manual-checkpoint-' + folder.name
            packet['manual_run_purpose'] = 'User-requested review of current saved project failures; no new performance evaluation'
            folder.mkdir()
            save(folder / 'packet.json', packet)
            save(folder / 'config.json', config)
            print('새 검토 — 현재 프로젝트의 최신 실패·실험 기록을 사용합니다.')
        active = {'directory': str(folder), 'finished': False}
        save(active_path, active)
    else:
        folder = Path(active['directory'])
        packet = json.loads((folder / 'packet.json').read_text())
        config = json.loads((folder / 'config.json').read_text())
        print('저장된 검토를 이어갑니다.')
    if config['max_calls'] > 3:
        raise ValueError('수동 검토의 max_calls는 최대 3이어야 합니다.')
    print('모델:', config['model'])
    print('기본 검토: 1회 후 자동 저장 / 추가 검토: --interactive에서 r 선택 시에만')
    print('전송 자료:', folder / 'packet.json')
    print('오류 사례:', len(packet['error_cases']), '/ 근거:', ', '.join(packet['evidence']))
    print('최대 호출:', config['max_calls'], '회 / 내부 추론:', '최소' if config.get('thinking_level') == 'minimal' else config.get('thinking_budget', '미확인'),
          '/ 출력 상한:', config['max_output_tokens'])
    print('무료 등급 확인 기록:', (config.get('free_tier_verification') or {}).get('verified_at', '미확인'))
    print('최신 실험:', packet.get('latest_result', '이전 동결 실행'))
    print('[1/4 근거 준비] 저장된 실패·실험 결과를 정리했습니다.')
    metrics = packet['same_evaluation_metrics']
    show_counts('최근 실험 결과', metrics.get('latest_experiment'))
    show_counts('그 이후 진단', metrics.get('latest_followup'))
    points = metrics.get('latest_experiment_actual_points')
    if points:
        before, after = points['before'], points['after']
        print('최근 실험의 실제 사람점 누락:', str(before['fn']) + '→' + str(after['fn']) + '/' + str(after['tp'] + after['fn']))
    print('이 숫자는 기존 결과이며 지금 새로 학습·평가한 수치가 아닙니다.')
    print('저장 위치:', folder, flush=True)
    previous_attempts = len(json.loads((folder / 'result.json').read_text()).get('attempts', [])) if (folder / 'result.json').exists() else 0
    call_ceiling = previous_attempts + max_new_calls if max_new_calls is not None else None
    if max_new_calls is not None:
        print('이번 실행의 Gemini 추가 호출 상한:', max_new_calls, '회', flush=True)
    database = folder / 'state.sqlite'
    print('[2/4 적대적 검토] Codex 개선안 → Gemini 비판 → Codex 답변 → NVIDIA 심판 → Codex 최종 판단·구현' if automatic else '[2/4 Gemini 검토] 근거와 코드를 비판하거나 저장된 검토 상태를 복원합니다.', flush=True)
    print('자동 모드: Codex 최종 승인 후 격리 학습·별도 평가·공통 실험으로 진행합니다. 기준 미달·개선 없음이면 격리 후보를 폐기하며 운영에는 배포하지 않습니다.' if automatic else
          '현재는 원인 검토만 수행합니다. 코드 변경·모델 학습·제안 실험 실행은 하지 않습니다.', flush=True)
    if not interactive and (folder / 'result.json').exists():
        result = json.loads((folder / 'result.json').read_text())
        print('저장 결과 조회: 이번 Gemini 추가 호출 0회')
    elif interactive and (folder / 'result.json').exists() and not database.exists():
        raise ValueError('저장된 응답의 체크포인트가 없어 중복 호출 방지를 위해 재개를 차단합니다.')
    elif automatic:
        result=dict(packet=packet,config=config,status='proposal_pending',attempts=[],pending=[])
    else:
        result = execute(packet, config, database)
    save(folder / 'result.json', {k: v for k, v in result.items() if k != '__interrupt__'})
    if automatic:
        from .cross_review_auto import run_auto
        print('자동 연결: Codex 기본 검토1회 + 필요할 때만 교정1회 + 구현1회, 채택 실험1건. Codex CLI 사용량은 이 채팅과 별도 기록합니다.',flush=True)
        code = run_auto(ROOT, folder, result, call_ceiling=call_ceiling)
        final_result = json.loads((folder / 'result.json').read_text())
        active['finished'] = not bool(final_result.get('pending'))
        save(active_path, active)
        next_steps(folder, final_result)
        return code
    while True:
        if result.get('status') == 'response_language_mismatch':
            break
        if config.get('prompt_version', VERSION) not in GROUNDED_VERSIONS and result.get('response'):
            print('이전 버전의 저장 응답입니다. 영어 원문은 보존하며 새 검토부터 한국어를 요청합니다.')
        for key, title in TITLES.items():
            if key in result.get('response', {}):
                print('\n' + title + ':', result['response'][key] or '미기재')
        if not result.get('pending'):
            break
        print('\n[LangGraph 중단] 응답과 체크포인트를 저장했습니다.')
        if not interactive:
            print('[3/4 다음 행동 정리] 저장 응답을 규칙으로 분류합니다. 별도 AI 호출은 없습니다.')
            print('기본 1회 검토를 마쳤습니다. 추가 호출 없이 저장하고 나갑니다.')
            print('추가 검토·명시적 종료가 필요하면 같은 명령에 --interactive를 붙이세요.')
            break
        used = len(result.get('attempts', []))
        remaining = max(0, config['max_calls'] - used)
        print('[3/4 사용자 근거 대조] 가설은 확정 원인이 아닙니다. 근거와 반대 근거를 비교하세요.')
        print('할 수 있는 일: 최소 실험 제안의 변경 변수·대조 조건·성공/실패 기준 확인.')
        print('실험 구현·학습을 진행하려면 이 제안을 별도 개발 작업으로 요청해야 합니다.')
        print('Gemini 호출:', used, '/', config['max_calls'], '회 — 남은 추가 검토:', remaining, '회')
        can_review = remaining > 0 and not result.get('response', {}).get('human_confirmation', '').strip()
        if not remaining:
            print('호출 상한에 도달했습니다. 종료하거나 저장하세요.')
        elif not can_review:
            print('사람 근거가 필요하다는 제안이므로 추가 API 검토는 차단합니다.')
        decision = None
        while decision is None:
            try:
                choice = input('Enter: 검토 종료 / ' + ('r: 반증 질문·근거 자동 선택 후 추가 검토 / ' if can_review else '') + 'q: 저장 후 나가기 > ').strip().lower()
            except EOFError:
                choice = 'q'
            if choice == 'q':
                next_steps(folder, result)
                print('저장했습니다. 같은 명령을 다시 실행하면 완료된 API 호출을 반복하지 않습니다.')
                return 0
            if choice == '':
                decision = {'action': 'stop', 'rationale': '사용자가 근거 대조 후 수동 검토 종료를 선택함', 'evidence_ids': []}
            elif choice == 'r':
                if len(result.get('attempts', [])) >= config['max_calls']:
                    print('호출 상한에 도달했습니다. 추가 호출 없이 종료하거나 저장하세요.')
                    continue
                if result.get('response', {}).get('human_confirmation', '').strip():
                    print('사람 확인이 필요한 제안입니다. 미확인을 추정하지 않고 종료하거나 저장하세요.')
                    continue
                used_checks = set()
                for previous_round in range(1, result.get('round', 1)):
                    path = folder / ('decision-' + str(previous_round) + '.json')
                    if path.exists():
                        used_checks.add(json.loads(path.read_text()).get('countercheck_id'))
                decision = counter_review(packet, result['response'], used_checks)
                if decision is None:
                    print('새로 대조할 반증 질문·근거가 없어 추가 호출 없이 종료합니다.')
                    decision = dict(action='stop', rationale='새 반증 질문·근거 없음', evidence_ids=[])
                else:
                    print('\n[추가 전송 내용] 질문 생성에는 API를 사용하지 않습니다.')
                    print('대상: 바로 위에 표시된 현재 응답의 원인 가설·실험 제안')
                    print('반증 질문:', decision['new_question'])
                    print('선택 근거:', ', '.join(decision['evidence_ids']))
                    print('대조할 근거 원문(식별자·코드는 원형 유지):')
                    print(json.dumps({key: packet['evidence'][key] for key in decision['evidence_ids']}, ensure_ascii=False, indent=2))
                    print('위 질문·현재 응답과 처음에 저장한 동일 근거 묶음을 전송합니다. 새 자료를 수집하거나 정답을 바꾸지 않습니다.', flush=True)
            else:
                print('Enter, r 또는 q를 입력하세요.')
        save(folder / ('decision-' + str(result.get('round', 1)) + '.json'), decision)
        print('[재개] 저장 지점에서 ' + ('추가 Gemini 검토를 요청합니다.' if decision['action'] == 'second' else '검토를 종료합니다. 실험을 실행하는 동작이 아닙니다.'), flush=True)
        result = execute(packet, config, database, decision=decision)
        save(folder / 'result.json', {k: v for k, v in result.items() if k != '__interrupt__'})
    active['finished'] = not bool(result.get('pending'))
    save(active_path, active)
    attempts = result.get('attempts', [])
    usages = [item.get('usage') or {} for item in attempts]
    usage = {}
    for key in ('prompt_token_count', 'candidates_token_count', 'thoughts_token_count', 'total_token_count'):
        values = [item.get(key) for item in usages]
        usage[key] = sum(values) if values and all(value is not None for value in values) else None
    print('\n[4/4 기록 저장·종료]', STATUS_LABELS.get(result['status'], '검토 종료'))
    if result.get('error_kind'):
        print('응답 검사:', {'invalid_json': 'JSON 문법 오류 또는 응답 본문 없음',
                         'invalid_schema': '필수 필드 누락·추가 또는 문자열 타입 불일치'}.get(result['error_kind'], '형식 오류'))
    print('기록:', folder / 'result.json')
    print('이 검토 호출 시도:', len(attempts), '/ 최대', config['max_calls'], '회')
    print('사용 토큰:', ' / '.join(label + ' ' + str((usage or {}).get(key) if (usage or {}).get(key) is not None else '미확인')
          for key, label in [('prompt_token_count', '입력'), ('candidates_token_count', '출력'),
                             ('thoughts_token_count', 'thinking'), ('total_token_count', '합계')]))
    next_steps(folder, result)
    return 0 if result['status'] in ('compare', 'awaiting_comparison', 'unresolved', 'call_limit', 'repeated_claim', 'no_new_evidence_or_hypothesis') else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--interactive', action='store_true', help='저장된 검토에서 r 추가 검토 / q 저장 / Enter 종료 선택')
    mode.add_argument('--web', action='store_true', help='로컬 웹에서 에이전트 공개 대화·진행 상태를 관찰(AI 호출 없음)')
    mode.add_argument('--auto', action='store_true', help='Codex 검증·실험 채택·구현·공통 실행기까지 자동 연결')
    parser.add_argument('--max-new-gemini-calls', type=int, choices=(1, 2, 3), help='이번 자동 실행에서 허용할 Gemini 추가 호출 수')
    parser.add_argument('--fresh', action='store_true', help='같은 자료의 기존 검토를 이어가지 않고 새 검토 폴더로 시작(새 모델 요청 발생 가능)')
    args = parser.parse_args(argv)
    if args.max_new_gemini_calls is not None and not args.auto:
        parser.error('--max-new-gemini-calls requires --auto')
    if args.fresh and not args.auto:
        parser.error('--fresh requires --auto')
    if os.environ.get('CARD_CONDITION_AUTO_CHILD'):
        print('자동 검토의 Codex 하위 실행에서는 review 재귀 호출을 차단합니다.', file=sys.stderr)
        return 1
    if args.web:
        if args.max_new_gemini_calls is not None:parser.error('--max-new-gemini-calls requires --auto')
        from .review_chat import serve
        serve(ROOT)
        return 0
    if args.interactive and not sys.stdin.isatty():
        print('대화형 터미널에서 실행하세요. Gemini는 호출하지 않았습니다.', file=sys.stderr)
        return 2
    base = ROOT / 'artifacts/manual-cross-review'
    base.mkdir(parents=True, exist_ok=True)
    try:
        from .workspace_lock import workspace_lock
        with workspace_lock(ROOT, 'review'), (base / 'session.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return review(base, interactive=args.interactive, automatic=args.auto, max_new_calls=args.max_new_gemini_calls, fresh=args.fresh)
    except BlockingIOError:
        print('다른 개발·실험·검토가 진행 중입니다. 파일을 수정하지 말고 종료 결과를 확인하세요.', file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print('\n중단 상태를 보존했습니다. 같은 명령으로 이어가세요. 결과 불명 요청은 재호출하지 않습니다.')
        return 130
    except LatestExperimentUnavailable as exc:
        print(str(exc), file=sys.stderr)
        print('Gemini를 호출하지 않았습니다. 표시된 최신 실험 기록을 확인하세요.', file=sys.stderr)
        return 1
    except EvidencePacketTooLarge as exc:
        path=base/'last-error.json'
        save(path,dict(kind='evidence_packet_too_large',actual_bytes=exc.actual_bytes,limit_bytes=exc.limit_bytes,diagnostic=error_diagnostic(exc)))
        print('검토 입력 크기 초과: '+str(exc.actual_bytes)+' bytes / 허용 '+str(exc.limit_bytes)+' bytes.',file=sys.stderr)
        print('평가 수치·실패 조건을 보존한 근거 요약이 필요합니다. AI 호출 없이 종료했습니다.',file=sys.stderr)
        print('비밀값을 제외한 진단 기록: '+str(path),file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        path=base/'last-error.json'
        save(path,dict(kind='input_or_saved_state_error',diagnostic=error_diagnostic(exc)))
        print('입력·설정 또는 저장 상태 오류입니다. 원문 대신 비밀값을 제외한 진단 기록을 확인하세요: '+str(path),file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
