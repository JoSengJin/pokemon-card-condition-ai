"""Fixed experiment parameter and acceptance checks."""
import math
from pathlib import Path
from .cross_review_auto_contract import PARAMETER
from .experiment_record import read
from .experiment_record import project_file


def check_acceptance(root,result,verdict,require_parameter,allowed):
        if verdict['action']=='select':
            from .experiment_record import acceptance_rules
            acceptance_rules(verdict['acceptance'])


def check_actual_point_guard(root,result,verdict,require_parameter,allowed):
        if verdict['action']=='select':
            from .experiment_record import point_reference
            from .cross_review_evidence import experiment
            baseline=experiment(project_file(root,result['packet']['latest_result']))
            _,points=point_reference(baseline['result'],baseline['rows'])
            if bool(points)!=verdict['acceptance']['require_actual_point_guard']:
                raise ValueError('Actual point guard must match existing human evidence; expected='+str(bool(points))+'; received='+str(verdict['acceptance']['require_actual_point_guard'])+'; inherited cohort guards remain mandatory')


def check_experiment_parameter(root,result,verdict,require_parameter,allowed):
        if verdict['action']=='select':
            parameter=verdict.get('experiment_parameter')
            if require_parameter or parameter is not None:
                if (not isinstance(parameter,dict) or set(parameter)!=set(PARAMETER['properties'])
                        or not all(isinstance(parameter.get(k),str) and parameter[k].strip() for k in ('name','scope'))
                        or any(type(parameter.get(k)) not in (int,float) or not math.isfinite(parameter[k]) for k in ('baseline','value'))
                        or parameter['baseline']==parameter['value']):
                    raise ValueError('Select requires one fixed finite experimental parameter')


def check_numeric_acceptance(root,result,verdict,require_parameter,allowed):
        if verdict['action']=='select':
            prior=read(project_file(root,str(Path(result['packet']['latest_result']).parent/'plan.json'))).get('acceptance',{})
            rules=verdict['acceptance']
            if (any(rules[k]>prior[k] for k in ('max_fp','max_fn') if k in prior)
                    or prior.get('no_new_errors') and not rules['no_new_errors']):
                raise ValueError('Cannot relax the previous numeric acceptance')


def check_second_question(root,result,verdict,require_parameter,allowed):
        if verdict['action']=='second' and not verdict['new_question'].strip():raise ValueError('A new falsification question is required')
