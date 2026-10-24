import copy
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from unittest.mock import patch

from card_condition import review_chat as chat
from card_condition.experiment_record import save,read


class ChatTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.folder=self.root/'artifacts/manual-cross-review/abc123';self.folder.mkdir(parents=True)
        save(self.folder/'result.json',dict(status='proposal_pending',packet=dict(latest_result='artifacts/current/result.json',failed_hypotheses={'rejected':{}},evidence={})))
        self.state=dict(flow_version='codex-first-v1',status='verifying',events=[])
        save(self.folder/'automation.json',self.state)
        save(self.folder.parent/'active.json',dict(directory=str(self.folder)))
        self.call=self.folder/'codex/correct-one/call.json';self.call.parent.mkdir(parents=True)
        save(self.call.parent/'input.json',dict(private_prompt='never expose prompt'))
        save(self.call,dict(status='pending',phase='correct',usage=None))

    def test_new_pending_and_complete_journals_are_visible_without_flow_event(self):
        before=chat.snapshot(self.root,'abc123')
        self.assertEqual(before['events'][0]['status'],'pending')
        save(self.call,dict(status='complete',phase='correct',data=dict(action='select',rationale='저장된 반론에 답변합니다.',worker='private worker',chain_of_thought='private thought'),usage={'input_tokens':11,'output_tokens':7}))
        after=chat.snapshot(self.root,'abc123')
        self.assertEqual(after['events'][0]['message']['rationale'],'저장된 반론에 답변합니다.')
        self.assertEqual(after['stages'][2]['status'],'complete')
        encoded=json.dumps(after)
        for secret in ('never expose prompt','private worker','private thought'):self.assertNotIn(secret,encoded)

    def test_first_turn_stream_visible_before_automation_state_exists(self):
        (self.folder/'automation.json').unlink()
        save(self.call.parent/'stream.json',dict(status='streaming',text='첫 공개 응답 생성 중',validated=False))
        value=chat.snapshot(self.root,'abc123')
        self.assertEqual(value['events'][0]['stream_text'],'첫 공개 응답 생성 중')
        self.assertFalse(value['events'][0]['stream_validated'])

    def test_does_not_duplicate_events_or_modify_any_journal(self):
        self.state['events']=[dict(id='correct',agent='Codex',phase='반론 답변',round=1,status='complete',message={'rationale':'old'})]
        save(self.folder/'automation.json',self.state)
        save(self.call,dict(status='complete',phase='correct',data={'rationale':'current'},usage={}))
        before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}
        value=chat.snapshot(self.root,'abc123');chat.reviews(self.root)
        self.assertEqual(len(value['events']),1)
        self.assertEqual(value['events'][0]['message']['rationale'],'current')
        self.assertEqual(before,{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()})

    def test_blocked_history_shows_program_reason_and_unrun_judge(self):
        self.state.update(status='validation_or_execution_error',reason='Failure history mismatch; unexpected=x')
        save(self.folder/'automation.json',self.state)
        save(self.call,dict(status='complete',phase='correct',data={'failed_hypotheses_checked':['rejected','execution-only']}))
        value=chat.snapshot(self.root,'abc123')
        self.assertEqual(value['issue']['ids'],['execution-only'])
        self.assertEqual(value['stages'][3]['status'],'not_started')
        self.assertIsNone(value['performance_improved'])

    def test_gemini_pending_sqlite_is_observed_without_calling_models(self):
        import sqlite3
        with sqlite3.connect(self.folder/'state.sqlite') as db:
            db.execute('CREATE TABLE calls (status TEXT,result TEXT,usage TEXT)')
            db.execute('INSERT INTO calls VALUES (?,?,?)',('pending',None,None))
        value=chat.snapshot(self.root,'abc123')
        self.assertEqual(next(e for e in value['events'] if e['agent']=='Gemini')['status'],'pending')

    def test_redacts_credential_patterns_and_keeps_hypothesis_ids(self):
        value=chat.redact({'rationale':'AIza'+'x'*35+' nvapi-'+'y'*24+' Bearer hidden-token','id':'fixed67-normal-gradient-conflict-audit-20261021-v1'})
        self.assertNotIn('hidden-token',value['rationale']);self.assertNotIn('xxxxx',value['rationale'])
        self.assertEqual(value['id'],'fixed67-normal-gradient-conflict-audit-20261021-v1')

    def test_path_and_symlink_cannot_read_outside_review(self):
        for name in ('../abc123','abc123/../../data','/data','..','abc123%2fsecret'):
            with self.assertRaises(FileNotFoundError):chat.review_folder(self.root,name)
        (self.folder.parent/'linked').symlink_to(self.folder)
        with self.assertRaises(FileNotFoundError):chat.review_folder(self.root,'linked')

    def server(self):
        server=chat.ChatServer(self.root,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(lambda:(server.shutdown(),server.server_close(),thread.join(timeout=2)))
        return server

    def test_http_live_changes_security_and_read_only(self):
        server=self.server()
        def get(path,headers=None):
            with urlopen(Request(server.origin+path,headers=headers or {})) as response:return response.status,response.read(),response.headers
        code,body,headers=get('/')
        self.assertEqual(code,200);self.assertIn('에이전트 대화'.encode(),body);self.assertEqual(headers['Cache-Control'],'no-store')
        self.assertEqual(json.loads(get('/api/reviews')[1])['active'],'abc123')
        self.assertEqual(json.loads(get('/api/reviews/abc123')[1])['events'][0]['status'],'pending')
        save(self.call,dict(status='complete',phase='correct',data={'rationale':'새 응답'}))
        self.assertEqual(json.loads(get('/api/reviews/abc123')[1])['events'][0]['message']['rationale'],'새 응답')
        for path,expected in [('/data/cross-review-key.json',404),('/api/reviews/..%2F..%2Fdata',404)]:
            with self.assertRaises(HTTPError) as error:get(path)
            self.assertEqual(error.exception.code,expected)
        with self.assertRaises(HTTPError) as error:get('/api/reviews',{'Host':'malicious.test'})
        self.assertEqual(error.exception.code,403)
        with self.assertRaises(HTTPError) as error:get('/api/reviews',{'Origin':'https://malicious.test'})
        self.assertEqual(error.exception.code,403)
        with self.assertRaises(HTTPError) as error:urlopen(Request(server.origin+'/api/run',data=b'{}',method='POST'))
        self.assertEqual(error.exception.code,501)

    def test_partial_json_is_transient_not_fake_success(self):
        server=self.server();self.call.write_text('{')
        with self.assertRaises(HTTPError) as error:urlopen(server.origin+'/api/reviews/abc123')
        self.assertEqual(error.exception.code,503)

    def test_web_cli_does_not_take_development_lock_or_start_review(self):
        from card_condition import cross_review_manual as manual
        with patch.object(chat,'serve') as serve,patch.object(manual,'review',side_effect=AssertionError('no AI')),patch('card_condition.workspace_lock.workspace_lock',side_effect=AssertionError('no writer lock')):
            self.assertEqual(manual.main(['--web']),0)
        serve.assert_called_once_with(manual.ROOT)

    def test_web_cannot_start_inside_bounded_codex_child(self):
        from card_condition import cross_review_manual as manual
        with patch.dict('os.environ',{'CARD_CONDITION_AUTO_CHILD':'1'}),patch.object(chat,'serve') as serve:
            self.assertEqual(manual.main(['--web']),1)
        serve.assert_not_called()
