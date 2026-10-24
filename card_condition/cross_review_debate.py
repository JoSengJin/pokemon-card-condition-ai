"""Small public-message transcript; never export hidden reasoning, prompts or credentials."""
import html
import json
from pathlib import Path
import sqlite3

from .cross_review import FIELDS, KOREAN_VERSION
from .experiment_record import read, save
from .review import atomic_write


def quality(packet, proposal):
    failed=packet.get('failed_hypotheses',{})
    hypothesis=proposal.get('hypothesis_id')
    refs=proposal.get('new_evidence_ids')
    stopped=proposal.get('proposal_status')=='stop'
    return dict(repeat_avoided=(not bool(proposal.get('smallest_experiment','').strip())) if stopped else bool(hypothesis) and (hypothesis not in failed or bool(packet.get('reopen_evidence',{}).get(hypothesis))),
        failed_history_compared=set(proposal['compared_failed_hypotheses'])==set(failed) if isinstance(proposal.get('compared_failed_hypotheses'),list) else None,
        fresh_evidence_cited=None if stopped else bool(refs) and set(refs)<=set(packet.get('fresh_evidence_ids',[])) if isinstance(refs,list) else None,
        experiment_with_criteria=None if stopped else all(isinstance(proposal.get(k),str) and proposal[k].strip() for k in ('smallest_experiment','success_criterion','failure_criterion')),
        measured_performance_gain=None)


def transcript(root, folder):
    result=read(folder/'result.json');packet=result.get('packet',{})
    rounds={};events=[]
    database=folder/'state.sqlite'
    if database.exists():
        with sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True) as db:
            rows=db.execute('SELECT status,result,usage FROM calls ORDER BY rowid').fetchall()
        for i,(status,response,usage) in enumerate(rows,1):
            data=json.loads(response) if response else {}
            rounds.setdefault(i,[]).append(dict(agent='Gemini',phase='옹호·가설 검증' if result.get('config',{}).get('prompt_version')==KOREAN_VERSION else '독립 비판',status=status,round=i,
                message={k:data[k] for k in FIELDS if k in data},usage=json.loads(usage) if usage else None,
                checks=quality(packet,data) if status=='complete' else None,source=str(database)))
    if not rounds and result.get('response'):
        data=result['response']
        rounds[1]=[dict(agent='Gemini',phase='저장된 반론 재사용',status=result.get('status'),round=1,
            message={k:data[k] for k in FIELDS if k in data},usage=None,checks=quality(packet,data),source=str(folder/'result.json'))]
    nemotron=[read(p) for p in (folder/'nemotron').glob('*.json') if p.name!='status.json']
    for entry in nemotron:
        from .cross_review_nemotron import safe_stored_stop
        assessed=safe_stored_stop(entry,packet)
        if assessed:entry=assessed
        response=entry.get('response',{});r=entry.get('round',1)
        message={k:response[k] for k in ('stance','support_score','opposition_score','rationale','evidence_ids') if k in response}
        if not response and entry.get('raw_response'):message['raw_response']=entry['raw_response']
        if entry.get('validation_errors'):message['validation_errors']=entry['validation_errors']
        if entry.get('warnings'):message['warnings']=entry['warnings']
        if response.get('proposal'):message.update({k:response['proposal'][k] for k in FIELDS})
        rounds.setdefault(r,[]).append(dict(agent='Nemotron',phase='상대 제안 반증',status=entry['status'],round=r,
            message=message,usage=entry.get('usage'),elapsed_seconds=entry.get('elapsed_seconds'),
            checks=quality(packet,response['proposal']) if response.get('proposal') else None,reused=entry.get('reused',False),proposal_action=response.get('proposal',{}).get('proposal_status')))
    implementations=[]
    for file in sorted((folder/'codex').glob('*/call.json'),key=lambda p:p.stat().st_mtime_ns):
        call=read(file);input_file=file.parent/'input.json';inputs=read(input_file) if input_file.exists() else {}
        data=call.get('data') or {};phase=call.get('phase',file.parent.name.split('-')[0]);r=inputs.get('round',max(rounds,default=1) if phase=='implement' else 1)
        message={k:data[k] for k in ('action','rationale','evidence_ids','experiment','acceptance','experiment_parameter') if k in data}
        if phase=='implement':message=dict(edited_files=[v.get('path') for v in data.get('edits',[])],worker_returned=bool(data.get('worker')))
        entry=dict(agent='Codex',phase=phase,status=call['status'],round=r,message=message,usage=call.get('usage'),source=str(file))
        if phase=='implement':implementations.append(entry)
        else:rounds.setdefault(r,[]).append(entry)
    for r in sorted(rounds):events.extend(rounds[r])
    events+=implementations
    auto=read(folder/'automation.json') if (folder/'automation.json').exists() else {}
    if auto.get('flow_version')=='codex-first-v1':events=auto.get('events',[])
    provider=read(folder/'nemotron/status.json') if (folder/'nemotron/status.json').exists() else None
    if provider is None and (root/'artifacts/provider-alerts/nemotron.json').exists():provider=read(root/'artifacts/provider-alerts/nemotron.json')
    adversarial=read(folder/'adversarial.json') if (folder/'adversarial.json').exists() else None
    return dict(adversarial=adversarial,review=folder.name,status=result.get('status'),automation_status=auto.get('status'),events=events,
        provider_status=provider,selected=result.get('selected'),experiment_record=str(Path(auto['experiment_folder'])/'record.json') if auto.get('experiment_folder') else None,
        acceptance_passed=auto.get('acceptance_passed'),performance_improved_on_same_cohort=auto.get('performance_improved_on_same_cohort'),
        note='공개 최종 응답과 프로그램 판정만 기록합니다. 내부 사고 과정은 포함하지 않습니다. 찬반 점수는 주관 평가이며 정확도·학습 보상이 아닙니다.')


def render(root, folder, output=None, provenance='stored'):
    data=transcript(root,folder);data['provenance']=provenance
    output=output or folder/'debate.html'
    save(output.with_suffix('.json'),data)
    esc=lambda value:html.escape(str(value))
    labels={'hypothesis_id':'가설','cause':'주장','evidence':'근거','counter_evidence':'반대 근거','smallest_experiment':'최소 실험',
        'success_criterion':'성공 기준','failure_criterion':'실패 기준','human_confirmation':'사람 확인','rationale':'판단 이유','action':'결정',
        'support_score':'찬성 점수(주관)','opposition_score':'반대 점수(주관)','stance':'입장','evidence_ids':'근거 ID','experiment':'실험 계획',
        'acceptance':'고정 기준','experiment_parameter':'변경 변수','warnings':'프로그램 경고(stop_experiment_ignored=복사 실험 무시 / failed_history_mismatch=실패·완료 진단 혼동)','raw_response':'규격 미통과 공개 응답(채택 불가)','validation_errors':'프로그램이 확인한 오류','edited_files':'변경 대상','worker_returned':'worker 제출','critique_responses':'비판별 답변','criticism_checks':'독립 심판의 반론 대조','unresolved_issues':'미해결 쟁점','decision':'판정','advocate':'개선안 품질 의견','skeptic':'비판 품질 의견'}
    page=['<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>교차 검토 기록</title>',
        '<style>body{font:16px/1.7 system-ui;background:#f4f6f8;color:#182438;max-width:1000px;margin:auto;padding:28px}article,header,section{background:white;padding:22px;border:1px solid #dbe2eb;border-radius:12px;margin-bottom:16px}h1{font-size:27px}h2{font-size:19px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.6 system-ui}.tag{color:#375a85}small{color:#586575}table{border-collapse:collapse}td,th{padding:8px;text-align:left;border-bottom:1px solid #ddd}.notice{border-left:5px solid #cb7026}</style>',
        '<header><span class="tag">'+('모의 예시 — 실제 모델 호출 아님' if provenance=='mock' else '저장된 실행 기록 — 이 화면 생성은 AI 호출 없음')+'</span>',
        '<h1>누가 무엇을 반박했고, 왜 멈췄나</h1><p>검토 '+esc(data['review'])+' · '+esc(data['status'])+' / 자동화 '+esc(data['automation_status'])+'</p><small>'+esc(data['note'])+'</small></header>']
    if data['adversarial']:
        report=data['adversarial']['final_report']; scores=report['judge_scores']
        page+=['<section><h2>독립 심판 · '+esc(report['decision'])+'</h2><p>'+esc(report['conclusion'])+'</p>',
               '<p>실험 경로: '+esc(report['experiment_action'])+' · '+esc(report['answer'])+'</p>',
               '<table><tr><th>검토 품질</th><th>옹호자</th><th>비판자</th></tr>']
        for key,label in [('reliability','출처 신뢰성 · 35%'),('logic','논리 · 25%'),('response','반박 대응 · 20%'),('independence','독립성 · 20%')]:
            page+=['<tr><td>'+label+'</td>'+''.join('<td>'+esc(scores[side]['adjusted'][key] if scores[side]['adjusted'][key] is not None else '미평가')+'</td>' for side in ('advocate','skeptic'))+'</tr>']
        page+=['<tr><th>가중 합계</th>'+''.join('<td>'+esc(scores[side]['weighted_total'] if scores[side]['weighted_total'] is not None else '미평가')+'</td>' for side in ('advocate','skeptic'))+'</tr></table>',
               '<p>심판의 품질 의견이며 사실 확률이 아닙니다. 출처 미확인 또는 단일 원자료의 독립성 점수는 최대49입니다. 과거에 평가하지 않은 점수는 채우지 않습니다.</p>',
               '<b>미해결 쟁점</b><pre>'+esc('\n'.join(report['unresolved_issues']) or '없음')+'</pre>',
               '<details><summary>라운드 변화·근거 검증 기록</summary><pre>'+esc(json.dumps(dict(verified_facts=report['verified_facts'],rounds=data['adversarial']['history']),ensure_ascii=False,indent=2))+'</pre></details></section>']
    if data['provider_status']:
        page+=['<section class="notice"><b>Nemotron 참여 상태</b><p>'+esc(data['provider_status'].get('reason',data['provider_status'].get('status')))+'</p><p>무료 확인 불가·종료·한도 오류에는 제외합니다. 유료 대체 호출은 하지 않습니다.</p></section>']
    if not data['events']:page+=['<section>저장된 에이전트 발언이 없습니다. 토론을 생성해 채우지 않았습니다.</section>']
    for i,event in enumerate(data['events'],1):
        page+=['<article><small>'+str(i)+' · 라운드 '+esc(event['round'])+'</small><h2>'+esc(event['agent'])+' · '+esc(event['phase'])+'</h2><p class="tag">'+esc(event['status'])+'</p>']
        if not event['message']:
            page+=['<p>프로그램 기록: 사용 가능한 발언 본문이 없습니다. 구버전 형식 검사 실패의 원문은 저장되지 않아 복원할 수 없습니다. 반론을 만들어 채우지 않았습니다.</p>']
        for k,v in event['message'].items():
            title='과거 실험 인용 — 중단 판정으로 실행 금지' if event.get('proposal_action')=='stop' and k=='smallest_experiment' else labels.get(k,k)
            if v not in ('',None,[]):page+=['<b>'+esc(title)+'</b><pre>'+esc(json.dumps(v,ensure_ascii=False,indent=2) if isinstance(v,(dict,list)) else v)+'</pre>']
        if event.get('checks'):
            page+=['<details><summary>코드로 검사한 검토 품질 · 모델 정확도 아님</summary><table>']
            for k,title in [('repeat_avoided','실패 가설 반복 회피'),('failed_history_compared','실패 이력 전체 대조'),('fresh_evidence_cited','새 근거 ID 인용'),('experiment_with_criteria','실험·판정 기준 존재')]:
                value=event['checks'][k];page+=['<tr><td>'+title+'</td><td>'+('대상 아님/미확인' if value is None else '1/1 충족' if value else '0/1 미충족')+'</td></tr>']
            page+=['</table></details>']
        page+=['<details><summary>사용량·출처</summary><pre>'+esc(json.dumps({k:event.get(k) for k in ('usage','elapsed_seconds','source','reused')},ensure_ascii=False,indent=2))+'</pre></details></article>']
    page+=['<section><h2>프로그램의 종료·실험 판정</h2><pre>'+esc(json.dumps({k:data[k] for k in ('status','automation_status','experiment_record','acceptance_passed','performance_improved_on_same_cohort')},ensure_ascii=False,indent=2))+'</pre><p>토론 합의는 성능 개선이 아닙니다. 모델 성능은 동일 평가 자료의 실제 누락·오탐으로 판정합니다.</p></section></html>']
    atomic_write(output,''.join(page))
    return output
