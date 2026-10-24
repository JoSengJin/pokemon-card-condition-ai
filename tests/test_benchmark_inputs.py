import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import torch
from card_condition import benchmark, point_benchmark
from card_condition.point_probe import digest


class BenchmarkInputsTest(unittest.TestCase):
    def test_changed_inputs_do_not_save_timing(self):
        for kind in ('point','side'):
            for target in ('photo','manifest','checkpoint',None):
                with self.subTest(kind=kind,target=target), tempfile.TemporaryDirectory() as folder:
                    root=Path(folder)
                    paths={key:root/(key+'.bin') for key in ('photo','manifest','checkpoint')}
                    for key,path in paths.items():path.write_bytes(key.encode())
                    row=dict(image=str(paths['photo']),box=[0,0,1,1],group='one',split='val')
                    output=root/'timing.json'
                    head=torch.nn.Linear(2,3).eval()
                    with torch.no_grad():head.weight.zero_();head.bias.zero_()
                    def prediction(*args,**kwargs):
                        if target:
                            path=paths[target];path.write_bytes(path.read_bytes()+b'changed')
                        return torch.zeros(1,2)
                    if kind=='point':
                        loader=patch.object(point_benchmark,'load_probe_model',return_value=(dict(architecture='fixture'),torch.nn.Identity(),head,False))
                        dataset=patch.object(point_benchmark,'point_rows',return_value=([row],{}))
                        inference=patch.object(point_benchmark,'patch_features',side_effect=prediction)
                        run=point_benchmark.benchmark_points
                    else:
                        analyzer=SimpleNamespace(predict=Mock(side_effect=prediction),device=torch.device('cpu'),
                            meta={},model_sha256=digest(paths['checkpoint']))
                        loader=patch.object(benchmark,'SideAnalyzer',return_value=analyzer)
                        dataset=patch.object(benchmark,'side_rows',return_value=([row],None,None))
                        inference=patch.object(benchmark.time,'perf_counter',side_effect=range(30))
                        run=benchmark.benchmark_validation
                    with loader,dataset,inference:
                        if target:
                            with self.assertRaisesRegex(ValueError,'inputs changed'):
                                run(paths['manifest'],paths['checkpoint'],output,'cpu')
                            self.assertFalse(output.exists())
                        else:
                            result=run(paths['manifest'],paths['checkpoint'],output,'cpu')
                            self.assertEqual(3,result['samples'])
                            self.assertEqual(3,result['repeats'])
                            self.assertEqual(result,json.loads(output.read_text()))
                            self.assertFalse(result['production_ready'])
