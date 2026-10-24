from datetime import datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,MagicMock
from urllib.request import urlopen
import threading
from card_condition import cross_review as g,cross_review_nemotron as n
from card_condition.experiment_record import read,save,sha
from card_condition.nvidia_dashboard import metrics
from card_condition.review_chat import ChatServer

class FreeOnlyTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        now=datetime.now(timezone.utc)
        self.proof=dict(tier='Free',project_id='dedicated',model='gemini-3.5-flash-lite',billing_disabled=True,evidence='test fixture only',verified_at=now.isoformat(),expires_at=(now+timedelta(hours=1)).isoformat(),key_sha256=hashlib.sha256(b'test-key').hexdigest())
        self.config=dict(model=self.proof['model'],max_output_tokens=64,thinking_level='MINIMAL',free_tier_verification=self.proof)
        for scope in [patch.dict('os.environ',{'POKEMON_CARD_CONDITION_GEMINI_API_KEY':'test-key'}),patch.object(g,'PAID_BLOCK_FILE',self.root/'blocked.json')]:
            scope.start();self.addCleanup(scope.stop)

    def test_gemini_paid_unverified_expired_or_model_changed_never_reaches_sdk(self):
        for update in ({'tier':'Paid'},{'billing_disabled':False},{'model':'other-model'},{'expires_at':self.proof['verified_at']}):
            with self.subTest(update=update),patch('google.genai.Client') as client:
                config=dict(self.config,free_tier_verification=dict(self.proof,**update))
                with self.assertRaises(ValueError):g.Gemini(config)('prompt',1)
                client.assert_not_called()
        with patch('google.genai.Client') as client:
            with self.assertRaises(ValueError):g.Gemini(dict(self.config,model='paid-model'))('prompt',1)
            client.assert_not_called()

    def test_gemini_402_persists_circuit_and_prevents_next_call(self):
        class PaymentError(Exception):code=402
        client=MagicMock();client.__enter__.return_value.models.generate_content.side_effect=PaymentError()
        with patch('google.genai.Client',return_value=client) as factory:
            with self.assertRaises(PaymentError):g.Gemini(self.config)('prompt',1)
            self.assertTrue(read(self.root/'blocked.json')['disabled'])
            with self.assertRaises(ValueError):g.Gemini(self.config)('prompt',1)
            self.assertEqual(factory.call_count,1)

    def native_config(self):
        proof={k:v for k,v in self.proof.items() if k in ('billing_disabled','verified_at','expires_at','evidence','key_sha256')}
        return dict(model=n.MODEL,allow_project_evidence=True,free_endpoint_status='available',free_verification=proof)

    def test_nvidia_paid_transition_unknown_model_or_endpoint_never_posts(self):
        with patch.dict('os.environ',{'POKEMON_CARD_CONDITION_NVIDIA_API_KEY':'test-key'}),patch.object(n,'policy',return_value=self.native_config()),patch.object(n,'official_status',return_value='deprecated'),patch('httpx.post') as post:
            with self.assertRaises(ValueError):n.http_call({'model':n.MODEL},1,self.root)
            post.assert_not_called()
        with patch.object(n,'eligible',return_value=None),patch('httpx.post') as post:
            with self.assertRaises(ValueError):n.http_call({'model':'paid/other'},1,self.root)
            with patch.object(n,'ENDPOINT','https://paid.example/api'):
                with self.assertRaises(ValueError):n.http_call({'model':n.MODEL},1,self.root)
            post.assert_not_called()

    def test_nvidia_unknown_free_status_blocks_before_request(self):
        with patch.dict('os.environ',{'POKEMON_CARD_CONDITION_NVIDIA_API_KEY':'test-key'}),patch.object(n,'policy',return_value=self.native_config()),patch.object(n,'official_status',return_value='unknown'),patch('httpx.post') as post:
            with self.assertRaises(ValueError):n.http_call({'model':n.MODEL},1,self.root)
            post.assert_not_called()

class DashboardTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        (self.root/'artifacts/nemotron-cache/a').mkdir(parents=True);(self.root/'artifacts/nemotron-cache/b').mkdir()
        save(self.root/'artifacts/nemotron-cache/a/call.json',dict(model=n.MODEL,role='judge',status='error',attempted=True,usage=None,elapsed_seconds=2.))
        save(self.root/'artifacts/nemotron-cache/b/call.json',dict(model=n.MODEL,role='skeptic',status='complete',attempted=True,usage={'prompt_tokens':10,'completion_tokens':5,'total_tokens':15},elapsed_seconds=4.))
        save(self.root/'nemotron-review.json',dict(model=n.MODEL))

    def test_only_canonical_attempts_count_unknown_usage_stays_unknown_accuracy_unmeasured(self):
        (self.root/'artifacts/manual-cross-review/copy/nemotron').mkdir(parents=True)
        save(self.root/'artifacts/manual-cross-review/copy/nemotron/dup.json',read(self.root/'artifacts/nemotron-cache/b/call.json'))
        data=metrics(self.root)
        self.assertEqual(data['calls'],2);self.assertEqual(data['schema_passed'],1);self.assertIsNone(data['usage']['total_tokens']);self.assertIsNone(data['accuracy']);self.assertEqual(data['latency']['mean_seconds'],3.)
        self.assertEqual(data['controlled_benchmark_samples'],0);self.assertEqual(data['cost']['codex']['scope'],'unchanged')

    def test_audit_annotations_require_exact_journal_hash(self):
        (self.root/'artifacts/nvidia-quality').mkdir()
        save(self.root/'artifacts/nvidia-quality/annotations.json',{'a':{'source_sha256':'wrong','note':'must not show'}})
        self.assertIsNone(next(e for e in metrics(self.root)['entries'] if e['id']=='a')['audit'])

    def test_read_only_dashboard_http_routes_no_model_calls(self):
        server=ChatServer(self.root,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with patch('httpx.post',side_effect=AssertionError('no models')),patch('google.genai.Client',side_effect=AssertionError('no models')):
                with urlopen(server.origin+'/nvidia') as r:self.assertIn('NVIDIA'.encode(),r.read())
                with urlopen(server.origin+'/api/nvidia') as r:self.assertEqual(json.load(r)['calls'],2)
        finally:server.shutdown();server.server_close();thread.join(timeout=2)
