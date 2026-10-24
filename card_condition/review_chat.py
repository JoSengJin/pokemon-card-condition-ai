"""Read-only localhost chat viewer of the existing cross-review journals. No AI calls."""
import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import sqlite3
from urllib.parse import unquote, urlsplit

from .cross_review_debate import transcript
from .experiment_record import read

PHASES = [('verify','Codex','개선안 작성'),('gemini','Gemini','독립 비판'),
          ('correct','Codex','반론 답변·수정안'),('judge','NVIDIA','독립 심판'),
          ('implement','Codex','최종 판단·구현'),('experiment','실험 실행기','개발·별도 평가')]
PUBLIC = {'action','rationale','experiment','acceptance','experiment_parameter','evidence_ids',
          'hypothesis_id','cause','evidence','counter_evidence','smallest_experiment',
          'success_criterion','failure_criterion','human_confirmation','proposal_status',
          'critique_status','difference_from_failed','new_evidence_ids','compared_failed_hypotheses',
          'critique_responses','decision','unresolved_issues','criticism_checks','advocate','skeptic',
          'final_decision','final_rationale','failed_hypotheses_checked','review_claims','code_checks'}


def public_message(value):
    message={k:v for k,v in (value or {}).items() if k in PUBLIC}
    if 'edits' in (value or {}):message['edited_files']=[v.get('path') for v in value['edits']]
    if 'worker' in (value or {}):message['worker_returned']=bool(value['worker'])
    return message


def redact(value):
    if isinstance(value,str):
        return re.sub(r'AIza[\w-]{30,}|nvapi-[\w-]{12,}|sk-[\w-]{20,}|Bearer\s+[^\s"\']+', '[비밀값 숨김]', value)
    if isinstance(value,list):return [redact(v) for v in value]
    if isinstance(value,dict):return {k:redact(v) for k,v in value.items()}
    return value


def review_folder(root, identity):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',identity):raise FileNotFoundError
    base=(root/'artifacts/manual-cross-review').resolve();folder=base/identity
    if folder.is_symlink() or folder.resolve().parent!=base or not (folder/'result.json').is_file():raise FileNotFoundError
    return folder


def reviews(root):
    base=root/'artifacts/manual-cross-review'
    active=read(base/'active.json').get('directory') if (base/'active.json').exists() else None
    items=[]
    for path in base.glob('*/result.json'):
        try:
            folder=review_folder(root,path.parent.name)
            auto=read(folder/'automation.json') if (folder/'automation.json').exists() else {}
            result=read(path)
            items.append(dict(id=folder.name,status=auto.get('status',result.get('status')),
                              updated_at=max(path.stat().st_mtime,(folder/'automation.json').stat().st_mtime if auto else 0)))
        except (ValueError,OSError):continue
    items.sort(key=lambda v:v['updated_at'],reverse=True)
    active_id=Path(active).name if isinstance(active,str) else None
    return dict(reviews=items,active=active_id if active_id in {v['id'] for v in items} else (items[0]['id'] if items else None))


def snapshot(root,identity):
    folder=review_folder(root,identity);result=read(folder/'result.json')
    auto=read(folder/'automation.json') if (folder/'automation.json').exists() else {}
    data=transcript(root,folder)
    events=[dict(v,message=public_message(v.get('message',{}))) for v in data['events']]
    if auto.get('flow_version')=='codex-first-v1' or (folder/'codex').is_dir():
        # Calls are journaled before sending. Include them even before a flow event or validation succeeds.
        by_phase={v.get('id'):v for v in events}
        for phase,agent,label in PHASES:
            calls=list((folder/'codex').glob(phase+'-*/call.json')) if agent=='Codex' else []
            if phase=='judge':calls=[p for p in (folder/'nemotron').glob('*.json') if p.name!='status.json' and read(p).get('role')=='judge']
            if not calls:continue
            call=read(sorted(calls,key=lambda p:p.stat().st_mtime_ns)[-1])
            event=by_phase.get(phase)
            if event is None:
                event=dict(id=phase,agent=agent,phase=label,round=1,source=str(calls[-1]));events.append(event);by_phase[phase]=event
            body=call.get('data') or call.get('response') or {}
            received_invalid=not body and bool(call.get('raw_response'))
            if received_invalid:
                try:body=json.loads(call['raw_response'])
                except (ValueError,TypeError):body={}
                if not isinstance(body,dict):body={}
            event.update(status='response_error' if received_invalid else call['status'],message=public_message(body),usage=call.get('usage'))
            if received_invalid:
                event['unvalidated_response']=True
                event['raw_response']=call['raw_response']
                event['validation_errors']=call.get('validation_errors',[])

            stream_file=calls[-1].parent/'stream.json'
            if not body and stream_file.is_file() and not stream_file.is_symlink() and stream_file.stat().st_size<=262144:
                stream=read(stream_file)
                from .cross_review_app_server import stream_redact
                event.update(stream_text=stream_redact(stream.get('text','')),stream_status=stream.get('status'),stream_validated=False)
            if call.get('error_kind'):event['error_kind']=call['error_kind']
        # Gemini writes its SQLite journal before a complete flow event is available.
        gemini=[v for v in events if v['agent']=='Gemini']
        db=folder/'state.sqlite'
        if db.exists():
            with sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True) as connection:
                rows=connection.execute('SELECT status,result,usage FROM calls ORDER BY rowid').fetchall()
            for index,(status,response,usage) in enumerate(rows,1):
                if index<=len(gemini):continue
                events.append(dict(id='gemini-pending-'+str(index),agent='Gemini',phase='독립 비판',round=index,status=status,
                    message=public_message(json.loads(response)) if response else {},usage=json.loads(usage) if usage else None,source=str(db)))
        order={key:i for i,(key,_,_) in enumerate(PHASES)}
        events.sort(key=lambda v:(v.get('round',1),order.get(v.get('id'),1 if v['agent']=='Gemini' else 3)))
    for event in events:
        event.setdefault('id',hashlib.sha256(json.dumps(event,sort_keys=True,default=str).encode()).hexdigest()[:16])
    reason=auto.get('reason','');issue=None
    if 'Failure history mismatch' in reason:
        corrections=[read(p).get('data',{}) for p in (folder/'codex').glob('correct-*/call.json')]
        extra=sorted(set(corrections[-1].get('failed_hypotheses_checked',[]))-set(result['packet'].get('failed_hypotheses',{}))) if corrections else []
        issue=dict(title='프로그램이 교정 응답의 이력 분류를 차단했습니다.',
            explanation='Codex는 실행 실패에서 성능을 추정하지 않는다고 답했지만, 가설 실패 ID 목록에 실행 실패 ID를 섞었습니다. 응답 형식·근거 분류 검사에서 멈췄으며 모델 실험의 실패 판정은 아닙니다.',ids=extra)
    elif 'preflight' in reason:
        issue=dict(title='모델 요청 전 입력·예산 검사에서 중단했습니다.',explanation=reason,ids=[])
    elif auto.get('status')=='judge_unavailable' and reason=='response_error':
        issue=dict(title='심판 응답 검증 실패로 개발을 차단했습니다.',explanation='NVIDIA의 공개 응답은 수신·저장됐지만 근거 ID 또는 응답 구조 검증을 통과하지 못했습니다. 원문은 아래에 표시하며 승인으로 사용하지 않습니다. 추가 호출·개발·학습은 실행하지 않았습니다.',ids=[])
    elif reason:issue=dict(title='프로그램의 종료 판단',explanation=reason,ids=[])
    usage=read(folder/'token_report.json') if (folder/'token_report.json').exists() else None
    stages=[]
    for key,agent,label in PHASES:
        matching=[e for e in events if e.get('id')==key or key=='gemini' and e['agent']=='Gemini']
        status=matching[-1]['status'] if matching else 'not_started'
        if key=='experiment':status=auto.get('experiment_status','not_started')
        stages.append(dict(id=key,agent=agent,label=label,status=status))
    value=dict(id=identity,status=auto.get('status',result.get('status')),reason=reason,issue=issue,
        events=events,stages=stages,usage=usage,source=result.get('packet',{}).get('latest_result'),
        acceptance_passed=auto.get('acceptance_passed'),performance_improved=auto.get('performance_improved_on_same_cohort'),
        experiment_status=auto.get('experiment_status'),read_only=True,
        note='공개 최종 응답과 프로그램 상태를 표시합니다. 내부 사고 과정·전체 입력 프롬프트는 공개하지 않습니다. app-server의 공개 응답은 생성 중 표시됩니다. 미완성 응답은 검증·승인으로 사용하지 않습니다.')
    return redact(value)


class ChatServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,root,port=8786):
        self.root=Path(root).resolve()
        super().__init__(('127.0.0.1',port),ChatHandler)
        self.origin=f'http://127.0.0.1:{self.server_port}'


class ChatHandler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,status,value,content_type='application/json; charset=utf-8'):
        body=value if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers();self.wfile.write(body)
    def do_GET(self):
        if self.headers.get('Host')!=self.server.origin.removeprefix('http://'):return self.send(403,dict(error='invalid_host'))
        if self.headers.get('Origin') not in (None,self.server.origin):return self.send(403,dict(error='invalid_origin'))
        path=unquote(urlsplit(self.path).path)
        try:
            if path=='/':return self.send(200,Path(__file__).with_suffix('.html').read_bytes(),'text/html; charset=utf-8')
            if path=='/nvidia':return self.send(200,Path(__file__).with_name('nvidia_dashboard.html').read_bytes(),'text/html; charset=utf-8')
            if path=='/api/nvidia':
                from .nvidia_dashboard import metrics
                return self.send(200,metrics(self.server.root))
            if path=='/api/reviews':return self.send(200,reviews(self.server.root))
            if path.startswith('/api/reviews/'):return self.send(200,snapshot(self.server.root,path.removeprefix('/api/reviews/')))
            return self.send(404,dict(error='not_found'))
        except FileNotFoundError:return self.send(404,dict(error='not_found'))
        except (ValueError,OSError,sqlite3.Error,KeyError,TypeError):
            return self.send(503,dict(error='record_updating',message='기록을 갱신 중입니다. 잠시 후 다시 읽습니다.'))


def serve(root,port=8786):
    with ChatServer(root,port) as server:
        print('에이전트 대화 화면:',server.origin,flush=True)
        print('관찰 전용 · AI 호출 없음 · 기존 ./review --auto의 새 기록을 자동 표시합니다.',flush=True)
        try:server.serve_forever()
        except KeyboardInterrupt:pass
