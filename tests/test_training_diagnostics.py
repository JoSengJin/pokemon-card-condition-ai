import json
import tempfile
from pathlib import Path
import unittest
from card_condition import training_diagnostics as diagnostics
from card_condition.experiment_record import read,save
import test_isolated_execution as isolated


class CollectorTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.fold=Path(self.temp.name);(self.fold/'output').mkdir()
        self.path=self.fold/'output/training-diagnostics.json'

    def test_absent_file_is_unknown_not_zero(self):
        result=diagnostics.collect(self.fold)
        self.assertEqual(result['status'],'unavailable');self.assertIsNone(result['optimizers'])
        self.assertFalse(result['independently_verified'])

    def test_nonfinite_and_malformed_reports_are_invalid(self):
        for text in ('[]','{}','{"version":1,"worker_completed":true,"optimizers":[{}]}'):
            self.path.write_text(text)
            self.assertEqual(diagnostics.collect(self.fold)['status'],'invalid')

    def test_symlink_is_not_read(self):
        secret=self.fold/'private.json';secret.write_text('never-readable')
        self.path.symlink_to(secret)
        self.assertEqual(diagnostics.collect(self.fold)['status'],'invalid')


class IsolatedDiagnosticsTest(unittest.TestCase):
    setUp=isolated.IsolatedExecutionTest.setUp
    run_candidate=isolated.IsolatedExecutionTest.run_candidate

    def test_no_optimizer_does_not_fabricate_convergence_or_change_independent_evaluation(self):
        isolated.configure(self)
        self.implementation['worker']=self.implementation['worker'].replace('[3.,-3.,-3.]','[3.,3.,3.]')
        result=self.run_candidate();folder=Path(result['experiment_folder'])
        value=read(folder/'training-diagnostics.json')['folds'][0]
        self.assertEqual(value['status'],'unavailable');self.assertEqual(value['optimizers'],[])
        self.assertFalse(value['independently_verified'])
        self.assertEqual(result['outcome'],'candidate_discarded')
        self.assertIn('training-diagnostics.json',read(folder/'record.json')['files'])
        self.assertEqual(self.run_candidate(),result)

    def test_failed_optimizer_preserves_actual_iterations_and_final_gradient(self):
        isolated.configure(self)
        self.implementation['worker']="""import torch
w=torch.tensor([0.],requires_grad=True)
optimizer=torch.optim.LBFGS([w],lr=.01,max_iter=1,line_search_fn=None)
def closure():
    optimizer.zero_grad();loss=(w-10).square().sum();loss.backward();return loss
optimizer.step(closure)
closure()
raise ValueError('Deliberate nonconvergence')
"""
        result=self.run_candidate();folder=Path(result['experiment_folder'])
        value=read(folder/'training-diagnostics.json')['folds'][0]
        self.assertEqual(value['status'],'recorded');self.assertFalse(value['worker_completed'])
        fit=value['optimizers'][0]
        self.assertEqual(fit['iterations'],1)
        self.assertEqual(fit['function_evaluations'],1)
        self.assertGreater(fit['max_gradient'],1e-5);self.assertFalse(fit['converged'])
        self.assertEqual(result['experiment_status'],'failed');self.assertFalse(result['code_applied'])
        self.assertIsNone(result['performance_improved_on_same_cohort'])
        self.assertEqual(self.run_candidate(),result)

    def test_interrupted_worker_records_unknown_and_does_not_retrain(self):
        isolated.configure(self)
        policy=read(self.root/'trusted-experiment.json');policy['fold_timeout_seconds']=1;save(self.root/'trusted-experiment.json',policy)
        self.implementation['worker']='while True: pass'
        result=self.run_candidate();folder=Path(result['experiment_folder'])
        value=read(folder/'training-diagnostics.json')['folds'][0]
        self.assertEqual(value['status'],'unavailable');self.assertIsNone(value['optimizers'])
        self.assertEqual(self.run_candidate(),result)
        self.assertFalse(result['code_applied'])

    def test_successful_fitter_is_observed_without_extra_closure_calls(self):
        isolated.configure(self)
        self.implementation['worker']="""import os,json,torch
from pathlib import Path
w=torch.tensor([0.],requires_grad=True)
optimizer=torch.optim.LBFGS([w],max_iter=10)
count=0
def closure():
    global count
    count+=1;optimizer.zero_grad();loss=(w-1).square().sum();loss.backward();return loss
optimizer.step(closure)
assert count==optimizer.state[w]['func_evals']
Path(os.environ['CARD_CONDITION_MODEL_OUTPUT']).write_text(json.dumps({'coef':[3.,-3.,-3.],'bias':0.}))
"""
        result=self.run_candidate();folder=Path(result['experiment_folder'])
        fit=read(folder/'training-diagnostics.json')['folds'][0]['optimizers'][0]
        self.assertTrue(fit['converged']);self.assertLessEqual(fit['max_gradient'],1e-5)
        self.assertGreater(fit['iterations'],0)
        self.assertTrue(read(folder/'evaluation-attestation.json')['independent_inference'])
        self.assertFalse(read(folder/'training-diagnostics.json')['folds'][0]['independently_verified'])
        self.assertEqual(result['outcome'],'accepted')
