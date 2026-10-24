"""One bounded app-server turn per journal; public text only, never reasoning/tool execution."""
import json
import os
import re
import selectors
import subprocess
from time import monotonic

from .experiment_record import save


def stream_redact(text):
    # Redact accumulated text so a credential split across deltas cannot bypass filtering.
    return re.sub(r'(?:AIza|nvapi-|sk-|Bearer\s+)[^\s"\\]*','[비밀값 숨김]',text)


def app_server_backend(root,phase,prompt,directory,thread_id=None):
    from .cross_review_auto import codex_child_config,VERDICT,IMPLEMENTATION,CODEX_TIMEOUT,diagnostic_text
    options,env=codex_child_config(root)
    process=subprocess.Popen(['codex','app-server','--listen','stdio://',*options],stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=directory,env=env,start_new_session=True)
    session=None;turn=None;started=0;requests=0;completed=False;blocked=None;usage=None;texts={};answers={};errors=[]
    stage='initialize';deadline=monotonic()+CODEX_TIMEOUT;settle=None
    schema=VERDICT if phase in ('verify','correct') else IMPLEMENTATION
    save(directory/'schema.json',schema)
    def public(status):
        save(directory/'stream.json',dict(transport='app-server',status=status,
            text=stream_redact('\n'.join(texts.values())),validated=False))
    def send(value):
        process.stdin.write((json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n').encode());process.stdin.flush()
    def event(data):
        nonlocal session,turn,started,requests,completed,blocked,usage,stage,settle
        if not isinstance(data,dict):raise ValueError('Invalid app-server event')
        method=data.get('method');params=data.get('params') or {}
        if 'id' in data:
            if method:
                # Refuse every server-initiated approval/tool request; never execute an action.
                send(dict(id=data['id'],error=dict(code=-32601,message='Tools disabled in bounded review')))
                raise ValueError('Unexpected app-server tool request')
            if 'error' in data:raise ValueError('App-server request failed')
            if data['id']==0 and stage=='initialize':
                send(dict(method='initialized',params={}))
                send(dict(id=1,method='thread/start',params=dict(cwd=str(directory),sandbox='read-only',
                    approvalPolicy='never',ephemeral=True)))
                stage='thread';return
            if data['id']==1 and stage=='thread':
                session=data['result']['thread']['id']
                if not isinstance(session,str) or not session:raise ValueError('Missing app-server thread')
                send(dict(id=2,method='turn/start',params=dict(threadId=session,cwd=str(directory),
                    input=[dict(type='text',text=prompt)],outputSchema=schema)))
                requests+=1;stage='turn';return
            if data['id']==2 and stage=='turn':return
            raise ValueError('Unexpected app-server response')
        if method in ('error','model/rerouted'):raise ValueError('App-server error or model reroute')
        handled=('turn/started','turn/completed','item/started','item/completed','item/agentMessage/delta','thread/tokenUsage/updated')
        if method not in handled:return  # Includes reasoning: never stored or displayed.
        if not session or params.get('threadId')!=session:raise ValueError('App-server thread mismatch')
        incoming=params.get('turnId') or params.get('turn',{}).get('id')
        if turn and incoming and incoming!=turn:raise ValueError('Unexpected extra turn')
        if method=='turn/started':
            started+=1
            if started>1:raise ValueError('Unexpected extra turn')
            turn=params['turn']['id'];return
        if method=='thread/tokenUsage/updated':
            value=params['tokenUsage']['last']
            names=dict(input_tokens='inputTokens',cached_input_tokens='cachedInputTokens',output_tokens='outputTokens',reasoning_output_tokens='reasoningOutputTokens')
            usage={k:value.get(v) for k,v in names.items()}
            if any(type(v) is not int or v<0 for v in usage.values()):raise ValueError('Unknown app-server usage')
            save(directory/'usage-metadata.json',dict(provider='Codex app-server',last={k:v for k,v in value.items() if type(v) is int and v>=0}))
            return
        if method=='item/agentMessage/delta':
            identity=params['itemId'];delta=params['delta']
            if not isinstance(delta,str):raise ValueError('Invalid agent delta')
            texts[identity]=texts.get(identity,'')+delta
        if method in ('item/started','item/completed'):
            item=params['item'];kind=item.get('type')
            if kind not in ('agentMessage','reasoning','userMessage'):raise ValueError('Unexpected app-server tool item')
            if kind=='agentMessage' and method=='item/completed':
                texts[item['id']]=item['text']
                if item.get('phase') in (None,'final_answer'):answers[item['id']]=item['text']
        if method=='turn/completed':
            if completed or params['turn'].get('status')!='completed':raise ValueError('App-server turn did not complete')
            completed=True;settle=monotonic()+1
        if sum(len(t.encode()) for t in texts.values())>131072:raise ValueError('App-server output limit')
        public('completed_unvalidated' if completed else 'streaming')
    public('pending')
    try:
        send(dict(id=0,method='initialize',params=dict(clientInfo=dict(name='card_condition_review',title='Card condition review',version='1'),capabilities=dict(experimentalApi=True))))
        buffers={process.stdout:b'',process.stderr:b''}
        with selectors.DefaultSelector() as selector:
            for stream in buffers:selector.register(stream,selectors.EVENT_READ)
            while selector.get_map():
                if completed and usage is not None:break
                remaining=min(deadline,settle if settle is not None else deadline)-monotonic()
                if remaining<=0:
                    if completed:break
                    raise TimeoutError('App-server turn timeout')
                ready=selector.select(remaining)
                if not ready:
                    if completed:break
                    raise TimeoutError('App-server turn timeout')
                for key,_ in ready:
                    stream=key.fileobj;chunk=stream.read1(65536)
                    if not chunk:selector.unregister(stream);continue
                    if stream is process.stderr:
                        errors.append(diagnostic_text(chunk.decode('utf-8',errors='replace')));errors[:]=errors[-8:];continue
                    buffers[stream]+=chunk
                    if len(buffers[stream])>262144:raise ValueError('App-server event limit')
                    while b'\n' in buffers[stream]:
                        line,buffers[stream]=buffers[stream].split(b'\n',1)
                        if line.strip():event(json.loads(line))
        if not completed or usage is None:raise ValueError('Incomplete app-server response or unknown usage; no retry')
        if not answers:raise ValueError('Missing completed final answer')
        value=json.loads(list(answers.values())[-1])
        if not isinstance(value,dict):raise ValueError('Invalid structured response')
        save(directory/'answer.json',value);public('completed_unvalidated')
        return value,usage,session
    except (ValueError,TypeError,KeyError,OSError,TimeoutError) as exc:
        blocked=type(exc).__name__;errors.append(diagnostic_text(str(exc)));public('error')
        return None,usage,session
    except BaseException:
        blocked='interrupted';public('interrupted');raise
    finally:
        if process.poll() is None:
            os.killpg(process.pid,15)
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(process.pid,9);process.wait()
        process.stdin.close();process.stdout.close();process.stderr.close()
        save(directory/'diagnostics.json',dict(transport='app-server',blocked=blocked,errors=errors[-8:],return_code=process.returncode,shutdown_after_completed=completed and blocked is None))
        save(directory/'execution.json',dict(transport='app-server',prompt_bytes=len(prompt.encode()),turn_requests=requests,
            turn_completions=int(completed),blocked=blocked,usage_known=usage is not None,usage=usage))
