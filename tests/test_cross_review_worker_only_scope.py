"""978cc047dc49 재현: worker-only 단일 변수 실험이 모델 파일 수정 불가 문구로 토론 전에 탈락하지 않는다."""
import copy
import unittest

from card_condition import cross_review_auto as auto
from card_condition.cross_review_evidence import latest_packet, expand_evidence
from card_condition.experiment_record import save, sha
import test_cross_review_auto as auto_fixture

TRAINER = 'artifacts/trainer-20261021/head.py'
TRAINER_TEXT = 'def fit_detail_head(x, penalty=1.):\n    return x + .5*penalty\n'
WORKER = 'artifacts/penalty-half-20261024/worker.py'


def configure_trainer(case):
    trainer = case.root/TRAINER; trainer.parent.mkdir(parents=True); trainer.write_text(TRAINER_TEXT)
    contract = dict(source='card_condition/model.py', source_sha256=sha(case.source), quote=case.original)
    save(case.root/'trusted-experiment.json', dict(baseline_training_contract=contract,
        editable_sources=['card_condition/model.py'], trainer_sources=[TRAINER]))
    case.packet = latest_packet(case.root); save(case.folder/'packet.json', case.packet)
    if hasattr(case, 'result'):
        case.result['packet'] = case.packet; save(case.folder/'result.json', case.result)
    worker_only = copy.deepcopy(case.verdict)
    worker_only['evidence_ids'].append('baseline_training_contract')
    worker_only['code_checks'] = [dict(path=TRAINER, sha256=sha(trainer), quote='return x + .5*penalty',
                                       conclusion='penalty가 목적함수에 쓰이며 인자로 지정된다. 이 파일은 수정하지 않는다.')]
    worker_only['implementation_files'] = []
    worker_only['experiment_parameter'] = dict(name='penalty', baseline=1., value=.5, scope='기존 학습 호출의 penalty 인자 하나')
    zero = dict(reliability=0, logic=0, response=0, independence=0, evidence_ids=[])
    worker_only['debate_assessment'] = dict(advocate=zero, skeptic=dict(zero),
        unresolved_issues=['정규화 변경 효과는 측정되지 않았다.'], revision_required=False)
    return worker_only


class WorkerOnlyValidationTest(unittest.TestCase):
    setUp = auto_fixture.AutoReviewTest.setUp

    def test_new_worker_listed_as_model_file_gets_actionable_error(self):
        worker_only = configure_trainer(self)
        listed = dict(worker_only, implementation_files=[WORKER])
        errors = auto.verdict_errors(self.root, dict(packet=self.packet), listed, require_parameter=True)
        message = next(e['error'] for e in errors if e['check'] == 'code_sources')
        self.assertIn(WORKER, message)
        self.assertIn('[] is valid', message)
        self.assertIn('worker_importable', message)

    def test_worker_only_select_passes_without_model_edit(self):
        worker_only = configure_trainer(self)
        errors = auto.verdict_errors(self.root, dict(packet=self.packet), worker_only, require_parameter=True)
        self.assertNotIn('code_sources', {e['check'] for e in errors})

    def test_readonly_trainer_is_still_not_editable(self):
        worker_only = configure_trainer(self)
        listed = dict(worker_only, implementation_files=[TRAINER])
        errors = auto.verdict_errors(self.root, dict(packet=self.packet), listed, require_parameter=True)
        self.assertIn('code_sources', {e['check'] for e in errors})

    def test_verify_and_correct_inputs_mark_worker_importable_trainer(self):
        configure_trainer(self)
        for phase in ('verify', 'correct'):
            context = expand_evidence(auto.review_context(self.root, self.folder, phase,
                dict(flow_role='advocate', response=dict(code_checks=[]))))
            sources = {v['path']: v for v in context['source_context']['sources']}
            self.assertFalse(sources[TRAINER]['editable'])
            self.assertTrue(sources[TRAINER]['worker_importable'])
            self.assertNotIn('worker_importable', sources['card_condition/model.py'])


if __name__ == '__main__':
    unittest.main()
