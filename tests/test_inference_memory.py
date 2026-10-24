import unittest
from unittest.mock import patch

import torch

from card_condition.inference_memory import profile_mps_memory


class MemoryProfileTest(unittest.TestCase):
    def test_sampling_does_not_change_output_or_retain_hooks(self):
        model=torch.nn.Sequential(torch.nn.Linear(3,3),torch.nn.ReLU()).eval()
        x=torch.tensor([[1.,2.,3.]])
        expected=model(x)
        with patch('torch.mps.current_allocated_memory',side_effect=[100,110,300,200,120]), patch(
                'torch.mps.driver_allocated_memory',side_effect=[400,410,800,600,420]):
            with profile_mps_memory(model,torch.device('mps')) as stats:
                actual=model(x)
                self.assertEqual(1,len(model[0]._forward_hooks))
        torch.testing.assert_close(actual,expected)
        self.assertEqual(4,stats['samples'])
        self.assertEqual((100,400),(stats['start_tensor_bytes'],stats['start_driver_bytes']))
        self.assertEqual((300,800),(stats['max_sampled_tensor_bytes'],stats['max_sampled_driver_bytes']))
        self.assertFalse(stats['true_peak_measured'])
        self.assertTrue(all(not m._forward_hooks for m in model.modules()))

    def test_error_also_removes_hooks_without_swallowing_it(self):
        model=torch.nn.Sequential(torch.nn.Linear(3,3)).eval()
        with patch('torch.mps.current_allocated_memory',return_value=100), patch(
                'torch.mps.driver_allocated_memory',return_value=400):
            with self.assertRaisesRegex(RuntimeError,'MPS out of memory'):
                with profile_mps_memory(model,torch.device('mps')):
                    self.assertTrue(model[0]._forward_hooks)
                    raise RuntimeError('MPS out of memory: simulated')
        self.assertTrue(all(not m._forward_hooks for m in model.modules()))
        with self.assertRaisesRegex(ValueError,'MPS only'):
            with profile_mps_memory(model,torch.device('cpu')):
                self.fail('CPU must not produce fake MPS memory measurements')

    def test_cli_allocation_failure_requests_fallback_and_exits_nonzero(self):
        from contextlib import redirect_stderr, redirect_stdout
        import io
        import json
        from card_condition.cli import main
        for error in (torch.OutOfMemoryError('simulated allocation failure'),
                      RuntimeError('MPS out of memory: simulated')):
            with self.subTest(error=type(error).__name__):
                stdout,stderr=io.StringIO(),io.StringIO()
                argv=['card-condition','listing-infer','unused.jsonl','unused.pt','unused-output.json',
                      '--batch-views','--profile-memory','--device','mps']
                with patch('sys.argv',argv), patch('card_condition.listing_inference.infer_listings',
                        side_effect=error), redirect_stderr(stderr),redirect_stdout(stdout):
                    with self.assertRaises(SystemExit) as raised:
                        main()
                self.assertEqual(1,raised.exception.code)
                self.assertEqual('',stdout.getvalue())
                self.assertEqual(dict(error=str(error),requires_gemini=True),json.loads(stderr.getvalue()))
