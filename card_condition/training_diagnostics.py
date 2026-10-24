"""Isolated optimizer observations, never independent performance evidence."""
import math
from .experiment_record import read,sha

# Runs in the child before generated worker code. It does not evaluate a closure again.
OBSERVER = r"""
import json,math,torch
_observed=[]
_step=torch.optim.LBFGS.step
def _observe_step(optimizer,*args,**kwargs):
    entry=[optimizer,False]
    _observed.append(entry)
    result=_step(optimizer,*args,**kwargs)
    entry[1]=True
    return result
torch.optim.LBFGS.step=_observe_step
_failed=True
try:
    exec(compile(Path('worker.py').read_text(),'worker.py','exec'),{'__name__':'__main__','__file__':str(Path('worker.py').resolve())})
    _failed=False
finally:
    _records=[]
    for optimizer,finished in _observed:
        parameters=[p for g in optimizer.param_groups for p in g['params']]
        state=optimizer.state.get(parameters[0],{})
        gradients=[float(p.grad.detach().abs().max()) for p in parameters if p.grad is not None]
        gradient=max(gradients) if len(gradients)==len(parameters) and all(math.isfinite(v) for v in gradients) else None
        converged=(False if gradient is not None and gradient>1e-5 else True if gradient is not None and finished and not _failed else None)
        _records.append(dict(optimizer='LBFGS',iterations=state.get('n_iter'),function_evaluations=state.get('func_evals'),
            max_gradient=gradient,converged=converged,gradient_threshold=1e-5,step_completed=finished))
    Path('output/training-diagnostics.json').write_text(json.dumps(dict(version=1,worker_completed=not _failed,optimizers=_records),allow_nan=False))
"""


def collect(fold):
    """Keep child provenance explicit; absent or invalid values remain unknown."""
    path=fold/'output/training-diagnostics.json'
    value=dict(fold=fold.name,status='unavailable',optimizers=None,source_sha256=None,
               provenance='isolated_process_observation',independently_verified=False)
    if not path.exists():return value
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink!=1 or path.stat().st_size>65536:raise ValueError('Unsafe diagnostic file')
        value['source_sha256']=sha(path)
        data=read(path)
        if set(data)!={'version','worker_completed','optimizers'} or type(data['version']) is not int or data['version']!=1 or type(data['worker_completed']) is not bool or not isinstance(data['optimizers'],list):raise ValueError('Invalid diagnostic schema')
        for item in data['optimizers']:
            if set(item)!={'optimizer','iterations','function_evaluations','max_gradient','converged','gradient_threshold','step_completed'} or item['optimizer']!='LBFGS':raise ValueError('Invalid optimizer record')
            for key in ('iterations','function_evaluations'):
                if item[key] is not None and (type(item[key]) is not int or item[key]<0):raise ValueError('Invalid count')
            g=item['max_gradient']
            if g is not None and (type(g) not in (int,float) or not math.isfinite(g) or g<0):raise ValueError('Invalid gradient')
            if item['converged'] is not None and type(item['converged']) is not bool:raise ValueError('Invalid convergence')
            if item['converged'] is True and (g is None or g>1e-5 or not item['step_completed'] or not data['worker_completed']):raise ValueError('Inconsistent convergence')
            if item['gradient_threshold']!=1e-5 or type(item['step_completed']) is not bool:raise ValueError('Invalid convergence policy')
        value.update(status='recorded' if data['optimizers'] else 'unavailable',worker_completed=data['worker_completed'],optimizers=data['optimizers'])
    except (ValueError,TypeError,KeyError,OSError):value.update(status='invalid',optimizers=None)
    return value
