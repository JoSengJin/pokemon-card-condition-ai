import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from card_condition import cross_review_app_server as transport,review_chat as chat,cross_review_auto as auto
from card_condition.experiment_record import read,save
import test_review_chat as chat_fixture


FAKE_SERVER = r"""
import json,sys,os,time
mode=os.environ.get('MOCK_MODE','ok')
def emit(method,params):print(json.dumps(dict(method=method,params=params)),flush=True)
for line in sys.stdin:
 r=json.loads(line)
 if r.get('method')=='initialize':print(json.dumps(dict(id=r['id'],result={})),flush=True)
 if r.get('method')=='thread/start':
  assert r['params']['sandbox']=='read-only' and r['params']['ephemeral'] is True
  print(json.dumps(dict(id=r['id'],result={'thread':{'id':'mock-thread'}})),flush=True)
 if r.get('method')=='turn/start':
  assert r['params']['outputSchema']['type']=='object'
  print(json.dumps(dict(id=r['id'],result={'turn':{'id':'mock-turn'}})),flush=True)
  emit('turn/started',dict(threadId='mock-thread',turn={'id':'mock-turn','status':'inProgress'}))
  if mode=='tool':
   emit('item/started',dict(threadId='mock-thread',turnId='mock-turn',item={'id':'tool','type':'commandExecution'}));continue
  if mode=='timeout':time.sleep(10);continue
  emit('item/reasoning/textDelta',dict(threadId='mock-thread',turnId='mock-turn',itemId='private',delta='private chain of thought'))
  emit('item/completed',dict(threadId='mock-thread',turnId='mock-turn',item={'id':'comment','type':'agentMessage','phase':'commentary','text':'모의 진행 안내'}))
  text=json.dumps({'rationale':'모의 연결 시험. 실제 AI 호출 없음','action':'stop'})
  emit('item/agentMessage/delta',dict(threadId='mock-thread',turnId='mock-turn',itemId='answer',delta=text[:18]))
  time.sleep(.03)
  emit('item/agentMessage/delta',dict(threadId='mock-thread',turnId='mock-turn',itemId='answer',delta=text[18:]))
  if mode=='malformed':text='invalid-json'
  emit('item/completed',dict(threadId='mock-thread',turnId='mock-turn',item={'id':'answer','type':'agentMessage','phase':'final_answer','text':text}))
  if mode!='unknown-usage':emit('thread/tokenUsage/updated',dict(threadId='mock-thread',turnId='mock-turn',tokenUsage={'last':{'inputTokens':10,'cachedInputTokens':0,'outputTokens':5,'reasoningOutputTokens':0},'total':{}}))
  emit('turn/completed',dict(threadId='mock-thread',turn={'id':'mock-turn','status':'completed'}))
"""


class AppServerTest(unittest.TestCase):
    setUp=chat_fixture.ChatTest.setUp

    def run_backend(self,mode='ok',snapshots=None):
        original=subprocess.Popen;real_save=save
        def spawn(args,**kwargs):
            self.launch=args
            self.assertNotIn('OPENAI_API_KEY',kwargs['env'])
            self.assertNotIn('NVIDIA_API_KEY',kwargs['env'])
            kwargs['env']=dict(kwargs['env'],MOCK_MODE=mode)
            return original([sys.executable,'-u','-c',FAKE_SERVER],**kwargs)
        def record(path,value):
            real_save(path,value)
            if snapshots is not None and path.name=='stream.json':snapshots.append(chat.snapshot(self.root,self.folder.name))
        with patch.object(transport.subprocess,'Popen',side_effect=spawn),patch.object(transport,'save',side_effect=record):
            return transport.app_server_backend(self.root,'correct','mock prompt',self.call.parent)

    def test_public_deltas_visible_before_completion_and_usage_preserved(self):
        snapshots=[];value,usage,thread=self.run_backend(snapshots=snapshots)
        self.assertEqual(value['action'],'stop');self.assertEqual(thread,'mock-thread')
        self.assertEqual(usage['input_tokens'],10);self.assertEqual(usage['output_tokens'],5)
        live=[s['events'][0] for s in snapshots if s['events'][0].get('stream_status')=='streaming']
        self.assertTrue(any(v.get('stream_text') for v in live));self.assertTrue(all(v['stream_validated'] is False for v in live))
        self.assertNotIn('private chain of thought',json.dumps(snapshots))
        self.assertEqual(self.launch[:4],['codex','app-server','--listen','stdio://'])
        self.assertEqual(read(self.call.parent/'execution.json')['turn_requests'],1)

    def test_tools_are_blocked_and_missing_usage_is_unknown(self):
        for mode in ('tool','unknown-usage','malformed'):
            with self.subTest(mode=mode):
                value,usage,thread=self.run_backend(mode)
                self.assertIsNone(value)
                self.assertIsNotNone(read(self.call.parent/'execution.json')['blocked'])
                if mode!='malformed':self.assertIsNone(usage)

    def test_timeout_terminates_child_without_retry_or_fake_usage(self):
        with patch.object(auto,'CODEX_TIMEOUT',.2):value,usage,_=self.run_backend('timeout')
        self.assertIsNone(value);self.assertIsNone(usage)
        self.assertEqual(read(self.call.parent/'execution.json')['turn_requests'],1)
        self.assertEqual(read(self.call.parent/'stream.json')['status'],'error')

    def test_fragmented_key_prefix_is_redacted_in_stream(self):
        for text in ('sk-short','prefix nvapi-ab','Bearer example'):
            self.assertIn('[비밀값 숨김]',transport.stream_redact(text))
            self.assertNotIn(text,transport.stream_redact(text))


class AppServerJournalTest(unittest.TestCase):
    from test_cross_review_auto import AutoReviewTest
    setUp=AutoReviewTest.setUp

    def test_default_transport_and_completed_cache_do_not_repeat_turn(self):
        usage=dict(input_tokens=10,output_tokens=5,cached_input_tokens=0,reasoning_output_tokens=0)
        with patch.object(transport,'app_server_backend',return_value=(self.verdict,usage,'mock')) as backend:
            first=auto.codex_task(self.root,self.folder,'verify',dict(flow_role='advocate'))
            self.assertEqual(auto.codex_task(self.root,self.folder,'verify',dict(flow_role='advocate')),first)
            backend.assert_called_once()
            prompt=backend.call_args.args[2]
            self.assertLessEqual(len(prompt.encode()),32000)
            from card_condition.cross_review_evidence import expand_evidence
            context=expand_evidence(read(backend.call_args.args[3]/'input.json'))
            self.assertEqual(context['evidence']['same_evaluation_metrics'],self.packet['same_evaluation_metrics'])

    def test_failed_or_uncertain_request_cannot_be_reissued(self):
        with patch.object(transport,'app_server_backend',return_value=(None,None,None)) as backend:
            with self.assertRaises(ValueError):auto.codex_task(self.root,self.folder,'verify',dict(flow_role='advocate'))
            with self.assertRaises(ValueError):auto.codex_task(self.root,self.folder,'verify',dict(flow_role='advocate'))
            backend.assert_called_once()


    def test_all_phases_reject_oversize_before_transport(self):
        self.assertEqual(auto.CODEX_PROMPT_BYTES,dict(verify=32000,correct=32000,implement=32000))
        for phase in auto.CODEX_PROMPT_BYTES:
            with self.subTest(phase=phase),patch.object(auto,'review_context',return_value={'large':'가'*11000}),patch.object(transport,'app_server_backend') as backend:
                with self.assertRaisesRegex(ValueError,'input_size'):auto.codex_task(self.root,self.folder,phase,{'phase':phase})
                backend.assert_not_called()
                self.assertFalse(list((self.folder/'codex').glob(phase+'-*/call.json')))

    def test_metrics_and_failure_gates_survive_compact_context(self):
        from card_condition.cross_review_evidence import expand_evidence
        summary=dict(success_criterion='같은 평가에서 누락<=1/4, 오탐<=0/22',failure_criterion='새 누락 또는 정답 변경 시 기각',acceptance={'max_fn':1,'max_fp':0},
            required_cohorts=[dict(id='guard',reference_result='artifacts/reference/result.json',acceptance={'max_fn':0,'no_new_errors':True})])
        self.packet['evidence']['latest_plan']={'summary':summary}
        save(self.folder/'packet.json',self.packet)
        context=expand_evidence(auto.review_context(self.root,self.folder,'verify',{'flow_role':'advocate'}))
        self.assertEqual(context['evidence']['same_evaluation_metrics'],self.packet['same_evaluation_metrics'])
        kept=context['evidence']['evidence']['latest_plan']['summary']
        for key in ('success_criterion','failure_criterion','acceptance'):self.assertEqual(kept[key],summary[key])
        self.assertEqual(kept['required_cohorts'],[{'id':'guard','acceptance':{'max_fn':0,'no_new_errors':True}}])


    def test_shared_value_pool_roundtrip_keeps_long_criteria_and_ids(self):
        from card_condition.cross_review_evidence import compact_evidence,expand_evidence
        document={'context_reference_root':'document','criteria':'누락 보호와 실패 조건을 그대로 보존'*30,
            'a':[{'id':'inherited-guard-'*10,'max_fn':2,'max_fp':3}]*12}
        document['b']=copy.deepcopy(document['a']);document['criteria_copy']=document['criteria']
        bounded=compact_evidence(document,document=True)
        self.assertEqual(expand_evidence(bounded),document)
        self.assertLess(len(json.dumps(bounded,ensure_ascii=False).encode()),len(json.dumps(document,ensure_ascii=False).encode()))
