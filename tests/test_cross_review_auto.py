import contextlib
import copy
import io
import json
import os
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from card_condition import cross_review_auto as auto
from card_condition.cross_review import execute, FIELDS, KOREAN_VERSION
from card_condition.cross_review_evidence import latest_packet
from card_condition.experiment_record import read, save, sha, records


class AutoReviewTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=self.root/'card_condition/model.py'; self.source.parent.mkdir()
        self.original='def score(x):\n    return x\n'; self.source.write_text(self.original)
        reference=self.root/'artifacts/reference-20261019'; reference.mkdir(parents=True)
        rows=[dict(id=str(i),target=t,group=str(i),image_sha256=str(i),box=[0,0,1,1]) for i,t in enumerate([1,0,0])]
        save(reference/'result.json',dict(rows=rows,before_scores=[.9,.8,.9],scores=[.9,.8,.9],independent=False))
        save(reference/'plan.json',dict(hypothesis='old',tracked_sha256={str(self.source):sha(self.source)}))
        self.packet=latest_packet(self.root)
        self.config=read(Path('examples/cross-review/config.json'))
        self.config.update(prompt_version=KOREAN_VERSION,max_calls=3,input_budget=72000,output_budget=12288,total_budget=84288,seconds=600)
        self.folder=self.root/'artifacts/manual-cross-review/test'; self.folder.mkdir(parents=True)
        save(self.folder/'packet.json',self.packet);save(self.folder/'config.json',self.config)
        self.gemini_calls=0; self.codex_calls=[]
        self.response=dict.fromkeys(FIELDS,''); self.response.update(hypothesis_id='new-cause',cause='독립 검토 가설',evidence='latest_result')
        self.response.update(proposal_status='propose',new_evidence_ids=['latest_result'],compared_failed_hypotheses=list(self.packet['failed_hypotheses']),difference_from_failed='기존 실패 조건과 다른 집계 변수를 새 결과로 대조')
        self.verdict=dict(action='select',rationale='실패 이력과 실제 코드로 대조한 실험',evidence_ids=['latest_result','related_code'],
            new_question='',failed_hypotheses_checked=list(self.packet['failed_hypotheses']),
            code_checks=[dict(path='card_condition/model.py',sha256=sha(self.source),quote=self.original,conclusion='원본 코드의 집계를 확인')],
            implementation_files=['card_condition/model.py'],
            experiment=dict(hypothesis_id='new-cause',cause='코드 근거로 구체화한 원인',smallest_experiment='집계 변수 하나만 바꾸고 고정 기준과 비교',
                            success_criterion='FP 1 이하, FN0, 새 오답 없음',failure_criterion='하나라도 미충족'),
            acceptance=dict(max_fp=1,max_fn=0,no_new_errors=True,require_actual_point_guard=False),
            experiment_parameter=dict(name='normal_loss_scale',baseline=1.,value=.5,scope='training normal bags only'))
        self.verdict['review_claims']=dict(completed_diagnostic_ids=[],missing_evidence_ids=[],gemini_required_for_select=False)
        self.worker="""import json,os
from pathlib import Path
r=json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'],'observations.json').write_text(json.dumps(dict(rows=r['rows'],scores=r['before_scores'])))
"""
        self.implementation=dict(edits=[dict(path='card_condition/model.py',before_sha256=sha(self.source),old='return x',new='return x + 1')],worker=self.worker)
        self.usage=dict(input_tokens=100,cached_input_tokens=20,output_tokens=10,reasoning_output_tokens=None)
        real_popen=subprocess.Popen
        def local_process_only(args,*pos,**kwargs):
            if Path(args[0]).name=='codex':
                raise AssertionError('Real Codex process prohibited in tests')
            return real_popen(args,*pos,**kwargs)
        child_guard=patch('subprocess.Popen',side_effect=local_process_only)
        child_guard.start();self.addCleanup(child_guard.stop)
        guard=patch('httpx.Client.send',side_effect=AssertionError('No live provider calls'))
        guard.start();self.addCleanup(guard.stop)

    def gemini(self,prompt,timeout):
        self.gemini_calls+=1
        response=dict(self.response,cause='독립 가설 '+str(self.gemini_calls))
        return json.dumps(response),dict(prompt_token_count=20,candidates_token_count=10,total_token_count=30)

    def start(self):
        result=execute(self.packet,self.config,self.folder/'state.sqlite',caller=self.gemini)
        save(self.folder/'result.json',{k:v for k,v in result.items() if k!='__interrupt__'})
        return result

    def backend(self,root,phase,prompt,directory,thread_id):
        self.codex_calls.append((phase,thread_id))
        return copy.deepcopy(self.verdict if phase in ('verify','correct') else self.implementation),dict(self.usage),'test-thread'

    def run_auto(self,result,**kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return auto.run_auto(self.root,self.folder,result,backend=self.backend,gemini_caller=self.gemini,**kwargs)





    def test_unauthenticated_worker_metrics_cannot_prove_gain(self):
        from card_condition.regression_audit import compare_predictions
        same=compare_predictions([1,0,0],[.9,.1,.8],[.9,.1,.8])
        better=compare_predictions([1,0],[.3,.8],[.9,.1])
        result=dict(acceptance_passed=True,comparison=same,required_cohorts=[dict(comparison=better)])
        self.assertFalse(auto.measured_gain(result))
        result['required_cohorts'][0]['comparison']=compare_predictions([1,0],[.9,.8],[.1,.1])
        self.assertFalse(auto.measured_gain(result))


    def test_select_rejects_unspecified_nonfinite_or_unchanged_parameter(self):
        for value in (None,float('nan'),True,1.):
            verdict=copy.deepcopy(self.verdict)
            if value is None:verdict.pop('experiment_parameter')
            else:verdict['experiment_parameter']['value']=value
            with self.subTest(value=value),self.assertRaises(ValueError):
                auto.validate_verdict(self.root,self.start(),verdict,require_parameter=True)

    def test_select_cannot_relax_recorded_numeric_acceptance(self):
        plan_path=self.root/Path(self.packet['latest_result']).parent/'plan.json'
        plan=read(plan_path);plan['acceptance']=copy.deepcopy(self.verdict['acceptance']);save(plan_path,plan)
        self.packet=latest_packet(self.root);save(self.folder/'packet.json',self.packet)
        result=self.start()
        verdict=copy.deepcopy(self.verdict);verdict['acceptance']['max_fp']=2
        with self.assertRaises(ValueError):auto.validate_verdict(self.root,result,verdict,require_parameter=True)

    def test_auto_resolves_plan_linked_fitter_and_complete_imported_loss(self):
        reference=self.root/Path(self.packet['latest_result']).parent
        fitter=reference/'fitter.py'
        fitter.write_text('from card_condition.model import score\ndef fit(x):\n    return score(x)\n')
        worker=reference/'worker.py'
        worker.write_text('from fitter import fit\nprint(fit(1))\n')
        plan=read(reference/'plan.json')
        plan.update(code_changes=[dict(path=str(worker.relative_to(self.root)),baseline=None)],
                    input_sha256={str(fitter.relative_to(self.root)):sha(fitter)},feature_sources=['features.pt'])
        save(reference/'plan.json',plan)
        self.packet=latest_packet(self.root)
        save(self.folder/'packet.json',self.packet)
        context=auto.source_context(self.root,self.packet)
        sources={s['path']:s for s in context['sources']}
        self.assertIn('artifacts/reference-20261019/fitter.py',sources)
        self.assertIn('def fit(x):',sources['artifacts/reference-20261019/fitter.py']['excerpt'])
        self.assertIn('return score(x)',sources['artifacts/reference-20261019/fitter.py']['excerpt'])
        self.assertTrue(all(not s['truncated'] for s in sources.values()))
        context=auto.review_context(self.root,self.folder,'implement',{'allowed_files':['card_condition/model.py']})
        self.assertEqual(context['execution_inputs']['feature_sources'],['features.pt'])









    def test_stop_claims_cannot_omit_completed_or_invent_missing_supplied_evidence(self):
        self.packet['completed_diagnostics']={'audit-v1':['diag']}
        self.packet['evidence']['diag']={'status':'completed'}
        save(self.folder/'packet.json',self.packet)
        result=self.start()
        for change in ({'completed_diagnostic_ids':[]},{'missing_evidence_ids':['diag']},{'gemini_required_for_select':True}):
            verdict=copy.deepcopy(self.verdict);verdict['action']='stop'
            verdict['review_claims']['completed_diagnostic_ids']=['audit-v1']
            verdict['review_claims'].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):
                auto.validate_verdict(self.root,result,verdict,require_parameter=True)








    def test_missing_history_or_wrong_code_quote_cannot_select(self):
        for bad in ('history','quote'):
            with self.subTest(bad=bad):
                verdict=copy.deepcopy(self.verdict)
                if bad=='history': verdict['failed_hypotheses_checked']=[]
                else: verdict['code_checks'][0]['quote']='not actual source code'
                with self.assertRaises(ValueError): auto.validate_verdict(self.root,dict(packet=self.packet),verdict)





    def fake_cli(self, output, stderr=""):
        reader,writer=os.pipe();os.write(writer,output.encode());os.close(writer)
        child=MagicMock(returncode=0,pid=999999)
        child.stdin=io.BytesIO();child.stdout=os.fdopen(reader,'rb')
        error_reader,error_writer=os.pipe();os.write(error_writer,stderr.encode());os.close(error_writer)
        child.stderr=os.fdopen(error_reader,'rb')
        child.poll.return_value=0
        return child


    def test_implementation_receives_only_explicit_linked_execution_sources(self):
        source=self.root/'artifacts/reference-20261019/fitter.py'
        source.write_text('def fit(x):\n    return x\n')
        self.packet['implementation_sources']=[str(source.relative_to(self.root))]
        self.packet['execution_inputs']={'feature_sources':['frozen-features.pt']}
        save(self.folder/'packet.json',self.packet)
        context=auto.review_context(self.root,self.folder,'implement',{'allowed_files':['card_condition/model.py']})
        self.assertEqual(context['execution_inputs'],self.packet['execution_inputs'])
        sources={s['path']:s for s in context['source_context']['sources']}
        self.assertIn('artifacts/reference-20261019/fitter.py',sources)
        self.assertFalse(sources['artifacts/reference-20261019/fitter.py']['editable'])

    def test_readonly_source_citation_needs_exact_quote_and_cannot_be_edited(self):
        fitter=self.root/'artifacts/reference-20261019/fitter.py'
        fitter.write_text('def fit(x):\n    return x + 1\n')
        self.packet['verification_sources']=[str(fitter.relative_to(self.root))]
        result=self.start();result['packet']=self.packet
        verdict=copy.deepcopy(self.verdict)
        verdict['code_checks'].append(dict(path=str(fitter.relative_to(self.root)),sha256=sha(fitter),quote=fitter.read_text(),conclusion='actual fitter'))
        auto.validate_verdict(self.root,result,verdict)
        verdict['code_checks'][-1]['quote']='def fit(x): ... return x'
        with self.assertRaises(ValueError):auto.validate_verdict(self.root,result,verdict)
        verdict['code_checks'][-1]['quote']=fitter.read_text()
        verdict['implementation_files'].append(str(fitter.relative_to(self.root)))
        with self.assertRaises(ValueError):auto.validate_verdict(self.root,result,verdict)




    def test_unexpected_tool_stops_cli_and_does_not_invent_usage(self):
        directory=self.folder/'cli-tool';directory.mkdir()
        output=json.dumps(dict(type='item.started',item=dict(type='command_execution',command='rg artifacts')))+'\n'
        with patch('subprocess.Popen',return_value=self.fake_cli(output)),patch('os.killpg') as kill:
            data,usage,_=auto.cli_backend(self.root,'verify','bounded prompt',directory)
        self.assertIsNone(data);self.assertIsNone(usage['input_tokens']);kill.assert_called_once_with(999999,15)
        self.assertEqual(read(directory/'execution.json')['blocked'],'unexpected_tool')

    def test_experimental_feature_warning_does_not_kill_a_valid_response(self):
        directory=self.folder/'cli-warning';directory.mkdir();save(directory/'answer.json',self.verdict)
        warning='Under-development features enabled: skip_host_skill_discovery. To suppress this warning, set suppress_unstable_features_warning = true.'
        output='\n'.join(json.dumps(e) for e in [dict(type='item.completed',item=dict(type='error',message=warning)),dict(type='turn.completed',usage=self.usage)])
        with patch('subprocess.Popen',return_value=self.fake_cli(output)),patch('os.killpg') as kill:
            data,usage,_=auto.cli_backend(self.root,'verify','bounded prompt',directory)
        self.assertEqual(data,self.verdict);self.assertEqual(usage,self.usage);kill.assert_not_called()
        diagnostics=read(directory/'diagnostics.json')
        self.assertEqual(diagnostics['errors'],[]);self.assertEqual(len(diagnostics['warnings']),1)
        self.assertIn('skip_host_skill_discovery',diagnostics['warnings'][0])

    def test_credentials_are_removed_from_persisted_diagnostics(self):
        directory=self.folder/'cli-secret';directory.mkdir()
        secret='offline-not-real-key-012345678901234567890'
        output=json.dumps(dict(type='item.completed',item=dict(type='error',message='API key='+secret)))+'\n'
        with patch('subprocess.Popen',return_value=self.fake_cli(output,'fatal configuration error, bearer '+secret+'\n')),patch('os.killpg'),patch.dict(os.environ,{'TEST_SECRET':secret}):
            auto.cli_backend(self.root,'verify','bounded prompt',directory)
        saved=(directory/'diagnostics.json').read_text()
        self.assertNotIn(secret,saved);self.assertIn('[REDACTED]',saved)
        self.assertIn('fatal configuration error',saved)
        self.assertEqual(read(directory/'diagnostics.json')['return_code'],0)

    def test_stderr_only_failure_is_preserved(self):
        directory=self.folder/'cli-stderr';directory.mkdir()
        child=self.fake_cli('','Error: invalid transport in mcp_servers.example\n');child.returncode=1
        with patch('subprocess.Popen',return_value=child):
            data,usage,_=auto.cli_backend(self.root,'verify','bounded prompt',directory)
        self.assertIsNone(data);self.assertIsNone(usage['input_tokens'])
        self.assertIn('invalid transport',read(directory/'diagnostics.json')['stderr'])

    def test_cli_error_is_not_misreported_as_tool_use(self):
        directory=self.folder/'cli-error';directory.mkdir()
        output=json.dumps(dict(type='item.completed',item=dict(type='error',message='startup error')))+'\n'
        with patch('subprocess.Popen',return_value=self.fake_cli(output)),patch('os.killpg'):
            data,usage,_=auto.cli_backend(self.root,'verify','bounded prompt',directory)
        self.assertIsNone(data);self.assertIsNone(usage['input_tokens'])
        self.assertEqual(read(directory/'execution.json')['blocked'],'cli_error')
        self.assertIn('startup error',str(read(directory/'diagnostics.json')['errors']))

    def test_extra_turn_is_recorded_and_never_accepted(self):
        directory=self.folder/'cli-extra';directory.mkdir();save(directory/'answer.json',self.verdict)
        output='\n'.join([json.dumps(dict(type='turn.completed',usage=self.usage))]*2)+'\n'
        with patch('subprocess.Popen',return_value=self.fake_cli(output)),patch('os.killpg'):
            data,usage,_=auto.cli_backend(self.root,'verify','bounded prompt',directory)
        self.assertIsNone(data);self.assertEqual(usage['input_tokens'],200)
        self.assertEqual(read(directory/'execution.json')['blocked'],'unexpected_extra_turn')

    def test_cli_timeout_retains_unknown_usage_and_no_retry(self):
        directory=self.folder/'cli-timeout';directory.mkdir()
        with patch('subprocess.Popen',return_value=self.fake_cli('')),patch('os.killpg'),patch('card_condition.cross_review_auto.monotonic',side_effect=[0,auto.CODEX_TIMEOUT+1]):
            data,usage,_=auto.cli_backend(self.root,'verify','bounded prompt',directory)
        self.assertIsNone(data);self.assertIsNone(usage['output_tokens'])
        self.assertEqual(read(directory/'execution.json')['blocked'],'time_budget')

    def test_source_context_follows_only_linked_imports_and_marks_truncation(self):
        helper=self.root/'card_condition/helper.py';helper.write_text('def helper(x):\n    return x\n'+'# padding\n'*1000)
        self.source.write_text('from card_condition.helper import helper\n'+self.original)
        context=auto.source_context(self.root,self.packet)
        self.assertEqual([s['path'] for s in context['sources']],['card_condition/model.py','card_condition/helper.py'])
        self.assertFalse(context['sources'][1]['truncated'])
        self.assertIn('return x',context['sources'][1]['excerpt'])
        self.assertNotIn('# padding',context['sources'][1]['excerpt'])
        self.assertNotIn('cross_review_auto.py',str(context))

    def test_diagnostic_omits_measurement_worker_but_retains_model_source(self):
        plan_path=self.root/Path(self.packet['latest_result']).parent/'plan.json'
        plan=read(plan_path)
        worker=plan_path.parent/'audit.py';worker.write_text('# measurement only\n'+'# x\n'*2000)
        plan.update(experiment_kind='diagnostic',code_changes=[dict(path=str(worker.relative_to(self.root)),baseline=None)])
        save(plan_path,plan)
        context=auto.source_context(self.root,self.packet)
        self.assertIn(str(worker.relative_to(self.root)),[s['path'] for s in context['sources']])
        self.assertIn('card_condition/model.py',[s['path'] for s in context['sources']])

    def test_cli_configuration_and_usage_events_are_captured_without_network(self):
        directory=self.folder/'cli'; directory.mkdir()
        save(directory/'answer.json',self.verdict)
        output='\n'.join(json.dumps(e) for e in [dict(type='thread.started',thread_id='specific-thread'),dict(type='turn.completed',usage=self.usage)])
        local_config=self.root/'.codex/config.toml';local_config.parent.mkdir()
        local_config.write_text('[mcp_servers.test_server]\ncommand="example"\n')
        child=self.fake_cli(output)
        with patch('subprocess.Popen',return_value=child) as process:
            data,usage,thread=auto.cli_backend(self.root,'verify','bounded prompt',directory,thread_id='old-heavy-session')
        self.assertEqual(data,self.verdict);self.assertEqual(thread,'specific-thread')
        args=process.call_args.args[0]
        self.assertIn('read-only',args);self.assertIn('--output-schema',args)
        self.assertNotIn('resume',args);self.assertNotIn('old-heavy-session',args)
        self.assertIn('project_doc_max_bytes=0',args);self.assertIn('memories.use_memories=false',args)
        self.assertIn('shell_tool',args);self.assertIn('code_mode',args)
        disabled=[args[i+1] for i,v in enumerate(args[:-1]) if v=='--disable']
        enabled=[args[i+1] for i,v in enumerate(args[:-1]) if v=='--enable']
        self.assertNotIn('code_mode_host',disabled);self.assertIn('code_mode_host',enabled)
        self.assertIn('mcp_servers.test_server.enabled=false',args)
        self.assertEqual(process.call_args.kwargs['cwd'],directory)
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox',args)
        self.assertEqual(usage['input_tokens'],100)


if __name__=='__main__': unittest.main()
