"""Opt-in MPS allocation sampling, not a true device or process peak profiler."""
from contextlib import contextmanager

import torch


@contextmanager
def profile_mps_memory(backbone, device):
    if device.type != 'mps':
        raise ValueError('Memory profiling currently supports MPS only')
    stats = dict(device='mps', scope='region_backbone_leaf_module_boundaries', samples=0,
        start_tensor_bytes=torch.mps.current_allocated_memory(),
        start_driver_bytes=torch.mps.driver_allocated_memory(),
        max_sampled_tensor_bytes=0, max_sampled_driver_bytes=0,
        true_peak_measured=False,
        limitations=['Driver allocation includes cached pools and MPS framework allocations.',
            'Leaf-module boundary samples can miss transient peaks and asynchronous allocations.',
            'Region backbone only: excludes observation-model inference, CPU/RSS and concurrent load.',
            'Profiling adds overhead; elapsed time is not the uninstrumented benchmark.'])
    handles = []

    def sample(*unused):
        stats['samples'] += 1
        stats['max_sampled_tensor_bytes'] = max(stats['max_sampled_tensor_bytes'],
            torch.mps.current_allocated_memory())
        stats['max_sampled_driver_bytes'] = max(stats['max_sampled_driver_bytes'],
            torch.mps.driver_allocated_memory())

    try:
        sample()
        for module in backbone.modules():
            if not list(module.children()):
                handles.append(module.register_forward_hook(sample))
        yield stats
        sample()
    finally:
        for handle in handles:
            handle.remove()
