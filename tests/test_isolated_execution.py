import contextlib
import copy
import io
import json
import math
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import torch
import test_cross_review_high_fixes as flow_fixture
from card_condition import cross_review_auto as auto
from card_condition import cross_review_execution as execution
from card_condition.experiment_record import read,save,sha,records


def configure(test):
    root=test.root;rows=read(root/test.packet['latest_result'])['rows']
    training=copy.deepcopy(rows)+[dict(id='train-positive',target=1,group='train-p',image_sha256='train-p'),dict(id='train-normal',target=0,group='train-n',image_sha256='train-n')]
    metadata=root/'metadata.json';save(metadata,dict(training_rows=training,folds=[dict(fold=0,train=[3,4],held=[0,1,2])]))
    source=root/'features.pt';torch.save(dict(ids=[r['id'] for r in training],features=torch.tensor([[[1.,0,0]],[[0,1.,0]],[[0,0,1.]],[[1.,0,0]],[[0,1.,1.]]]),masks=torch.ones(5,1,dtype=torch.bool)),source)
    baseline=root/'baseline.pt';torch.save(dict(coef=torch.tensor([math.log(.9/.1),math.log(.8/.2),math.log(.9/.1)]),bias=torch.tensor(0.)),baseline)
    policy=dict(adapter=execution.VERSION,training_metadata='metadata.json',feature_sources=['features.pt'],baseline_models=['baseline.pt'],required_features=[],trainer_sources=[],editable_sources=['card_condition/model.py'],point_tokens=[-1]*5,decoded_image_sha256={r['id']:r['image_sha256'] for r in training},fold_timeout_seconds=15)
    policy['input_sha256']={str(p.relative_to(root)):sha(p) for p in [metadata,source,baseline]};save(root/'trusted-experiment.json',policy)
    test.implementation['worker']="""import os,json,torch
from pathlib import Path
x=torch.load(os.environ['CARD_CONDITION_TRAIN_INPUT'],weights_only=True)
assert x['ids']==['train-positive','train-normal']
assert 'CARD_CONDITION_EXPERIMENT_REFERENCE' not in os.environ
assert not any('KEY' in k or 'TOKEN' in k or 'SECRET' in k for k in os.environ)
Path(os.environ['CARD_CONDITION_MODEL_OUTPUT']).write_text(json.dumps({'coef':[3.,-3.,-3.],'bias':0.}))
"""


class IsolatedExecutionTest(unittest.TestCase):
    setUp=flow_fixture.HighFixTest.setUp
    backend=flow_fixture.HighFixTest.backend
    gemini=flow_fixture.HighFixTest.gemini
    judge=flow_fixture.HighFixTest.judge
    run_flow=flow_fixture.HighFixTest.run_flow

    def ready(self):configure(self)

    def run_candidate(self):
        if not (self.folder/'implementation-proposal.json').exists():
            auto.stage_implementation(self.root,self.folder,self.verdict,{k:self.implementation[k] for k in ('edits','worker')})
        from card_condition.workspace_lock import workspace_lock
        from card_condition.development_review import review_scope
        with workspace_lock(self.root,'test trusted execution'),review_scope(),contextlib.redirect_stdout(io.StringIO()):
            return execution.execute_candidate(self.root,self.folder,self.verdict)

    def test_actual_isolation_independent_inference_accept_and_no_repeat(self):
        self.ready();result=self.run_candidate()
        self.assertEqual(result['outcome'],'accepted');self.assertTrue(result['code_applied'])
        self.assertIn('return x + 1',self.source.read_text())
        experiment=Path(result['experiment_folder']);actual=read(experiment/'result.json')
        self.assertEqual(actual['comparison']['after']['fp'],0)
        self.assertTrue(read(experiment/'evaluation-attestation.json')['independent_inference'])
        self.assertEqual(self.run_candidate(),result)
        self.assertEqual(len(records(self.root)),1)
        self.assertTrue((experiment/'comparison.html').exists())

    def test_perfect_forged_observations_are_ignored_and_no_gain_discards_candidate(self):
        self.ready();self.implementation['worker']=self.implementation['worker'].replace("[3.,-3.,-3.]","[3.,3.,3.]")+"\ntry:Path(os.environ['CARD_CONDITION_MODEL_OUTPUT']).with_name('observations.json').write_text(json.dumps({'scores':[1,0,0]}))\nexcept PermissionError:pass\n"
        result=self.run_candidate();self.assertEqual(result['outcome'],'candidate_discarded')
        self.assertEqual(self.source.read_text(),self.original)
        self.assertEqual(read(Path(result['experiment_folder'])/'result.json')['comparison']['after']['fp'],2)
        self.assertFalse(result['code_applied'])

    def test_score_only_output_is_rejected_without_source_change_or_retry(self):
        self.ready();self.implementation['worker']="import os,json\nfrom pathlib import Path\nPath(os.environ['CARD_CONDITION_MODEL_OUTPUT']).write_text(json.dumps({'scores':[1,0,0]}))"
        result=self.run_candidate();self.assertEqual(result['experiment_status'],'failed')
        self.assertIsNone(result['performance_improved_on_same_cohort']);self.assertEqual(self.source.read_text(),self.original)
        self.assertEqual(self.run_candidate(),result);self.assertEqual(len(records(self.root)),1)

    def test_private_reference_live_source_and_network_are_denied(self):
        self.ready();secret=self.root/'private-evaluation-secret.json';secret.write_text('never-readable')
        self.implementation['worker']=f"""import os,socket
from pathlib import Path
for p in [{str(secret)!r},{str(self.source)!r}]:
 try:Path(p).read_text();raise AssertionError('private file readable')
 except PermissionError:pass
try:Path({str(self.source)!r}).write_text('corrupt');raise AssertionError('live write allowed')
except PermissionError:pass
try:socket.create_connection(('127.0.0.1',9),timeout=.2);raise AssertionError('network allowed')
except PermissionError:pass
"""+self.implementation['worker']
        self.assertEqual(self.run_candidate()['outcome'],'accepted');self.assertEqual(secret.read_text(),'never-readable')

    def test_train_eval_group_photo_overlap_blocks_before_worker(self):
        self.ready();metadata=self.root/'metadata.json';value=read(metadata);value['training_rows'][3]['group']='0';save(metadata,value)
        policy=read(self.root/'trusted-experiment.json');policy['input_sha256']['metadata.json']=sha(metadata);save(self.root/'trusted-experiment.json',policy)
        result=self.run_candidate();self.assertEqual(result['experiment_status'],'failed')
        self.assertFalse(list((self.folder/'isolated').glob('fold-*')))

    def test_changed_pinned_input_is_blocked_before_training(self):
        self.ready();(self.root/'metadata.json').write_text('{}')
        with self.assertRaises(ValueError):self.run_candidate()
        self.assertFalse((self.folder/'execution.json').exists())

    def test_symlink_model_output_rejected(self):
        self.ready();self.implementation['worker']="import os\nfrom pathlib import Path\nPath(os.environ['CARD_CONDITION_MODEL_OUTPUT']).symlink_to('/etc/passwd')"
        result=self.run_candidate();self.assertEqual(result['experiment_status'],'failed')
        self.assertEqual(self.source.read_text(),self.original)

    def test_timeout_is_recorded_and_never_retried(self):
        self.ready();p=read(self.root/'trusted-experiment.json');p['fold_timeout_seconds']=1;save(self.root/'trusted-experiment.json',p)
        self.implementation['worker']='while True: pass'
        result=self.run_candidate();self.assertEqual(result['experiment_status'],'failed')
        self.assertEqual(self.run_candidate(),result);self.assertEqual(len(records(self.root)),1)

    def test_pending_journal_cannot_retrain(self):
        self.ready();save(self.folder/'execution.json',dict(status='running'))
        with self.assertRaises(ValueError):self.run_candidate()
        self.assertFalse((self.root/'artifacts/experiments').exists())

    def test_final_codex_stop_prevents_execution_and_no_extra_calls(self):
        self.ready();self.implementation.update(final_decision='stop',final_rationale='추가 근거가 필요해 실행하지 않습니다.')
        self.assertEqual(self.run_flow(),0)
        self.assertFalse((self.folder/'execution.json').exists());self.assertEqual(len(self.codex_calls),3)

    def test_full_auto_uses_three_codex_one_each_critic_then_common_runner(self):
        self.ready();self.assertEqual(self.run_flow(call_ceiling=1),0)
        state=read(self.folder/'automation.json');self.assertEqual(state['status'],'completed')
        self.assertEqual(state['codex_final_decision']['decision'],'proceed')
        self.assertEqual(read(self.folder/'result.json')['status'],'experiment_evaluated')
        self.assertEqual(len(self.codex_calls),3);self.assertEqual(self.gemini_calls,1);self.assertEqual(self.n_calls,1)
        self.assertTrue(state['performance_improved_on_same_cohort'])
        self.assertEqual(self.run_flow(call_ceiling=1),0)
        self.assertEqual(len(records(self.root)),1)

    def test_cpu_optimizer_runs_inside_sandbox(self):
        import shutil
        from card_condition import point_patch_head
        shutil.copy2(Path(point_patch_head.__file__),self.root/'card_condition/point_patch_head.py')
        self.ready();policy=read(self.root/'trusted-experiment.json');policy['point_tokens'][3]=0;save(self.root/'trusted-experiment.json',policy)
        self.implementation['worker']="""import os,json,torch
from pathlib import Path
from card_condition.point_patch_head import fit_point_bag_head
x=torch.load(os.environ['CARD_CONDITION_TRAIN_INPUT'],weights_only=True)
w,b,_=fit_point_bag_head(x['features'],x['masks'],x['targets'],x['point_tokens'],x['weights'],normal_reduction='max_bound')
Path(os.environ['CARD_CONDITION_MODEL_OUTPUT']).write_text(json.dumps({'coef':w.tolist(),'bias':float(b)}))
"""
        result=self.run_candidate();self.assertEqual(result['experiment_status'],'completed')
        self.assertTrue((Path(result['experiment_folder'])/'evaluation-attestation.json').exists())

    def test_live_source_conflict_never_overwrites_user_edit(self):
        self.ready();original=execution.run
        def changed(*args,**kwargs):
            code=original(*args,**kwargs);self.source.write_text('def score(x):\n    return 999\n');return code
        with patch.object(execution,'run',side_effect=changed):result=self.run_candidate()
        self.assertEqual(result['outcome'],'source_conflict');self.assertIn('999',self.source.read_text())

    def test_apply_failure_after_replace_restores_snapshot(self):
        self.ready();original=execution.atomic_write;calls=[]
        def failed(path,content):
            original(path,content);calls.append(path)
            if len(calls)==1:raise OSError('simulated post-replace failure')
        with patch.object(execution,'atomic_write',side_effect=failed),self.assertRaises(OSError):self.run_candidate()
        self.assertEqual(self.source.read_text(),self.original)
        self.assertEqual(read(self.folder/'execution.json')['outcome'],'apply_failed_rolled_back')

    def test_auto_recovers_completed_experiment_without_revalidating_old_source_or_calling_models(self):
        self.ready();self.assertEqual(self.run_flow(call_ceiling=1),0)
        state=read(self.folder/'automation.json');state['status']='verifying';save(self.folder/'automation.json',state)
        before=(len(self.codex_calls),self.gemini_calls,self.n_calls)
        self.assertEqual(self.run_flow(call_ceiling=1),0)
        self.assertEqual((len(self.codex_calls),self.gemini_calls,self.n_calls),before)
        self.assertEqual(len(records(self.root)),1)

    def test_evidence_aliases_roundtrip_without_losing_diagnostic(self):
        from card_condition.cross_review_evidence import compact_evidence,expand_evidence
        value={'a':{'summary':{'measurements':{'values':list(range(100))}}},'b':{'summary':{'measurements':{'values':list(range(100))}}}}
        compact=compact_evidence(value)
        self.assertIn('$ref',compact['b']['summary']['measurements'])
        self.assertEqual(expand_evidence(compact),value)


if __name__=='__main__':unittest.main()


class ProvidedCitationTest(unittest.TestCase):
    def test_baseline_contract_exposes_only_its_exact_frozen_quote(self):
        context=dict(source_context=dict(sources=[dict(path='model.py',sha256='a',excerpt='def f(): pass')]),
            baseline_training_contract=dict(source='worker.py',source_sha256='b',quote='fit(normal_reduction="max_bound")'))
        provided={s['path']:s for s in auto.provided_code_sources(context)}
        self.assertEqual(provided['worker.py']['sha256'],'b')
        self.assertIn('normal_reduction="max_bound"',provided['worker.py']['excerpt'])
        self.assertNotIn('secret_other_function()',provided['worker.py']['excerpt'])
        self.assertEqual(context['source_context']['sources'],[dict(path='model.py',sha256='a',excerpt='def f(): pass')])
        context['baseline_training_contract'].pop('source_sha256')
        self.assertNotIn('worker.py',{s['path'] for s in auto.provided_code_sources(context)})
