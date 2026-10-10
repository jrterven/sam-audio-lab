"""Shared device policy for the isolated audio and vision runtimes."""
import os


def select_device(torch):
    requested = os.environ.get('SAM_LAB_DEVICE', 'auto').lower()
    available = {'cpu': True, 'cuda': torch.cuda.is_available(), 'mps': torch.backends.mps.is_available()}
    if requested == 'auto':
        return next(d for d in ('cuda', 'mps', 'cpu') if available[d])
    if requested not in available:
        raise ValueError('SAM_LAB_DEVICE must be auto, cuda, mps, or cpu.')
    if not available[requested]:
        raise RuntimeError(f'The {requested} device is not available in this PyTorch environment.')
    return requested


def synchronize(torch, device):
    if device in ('cuda', 'mps'):
        getattr(torch, device).synchronize()


def empty_cache(torch, device):
    if device in ('cuda', 'mps'):
        getattr(torch, device).empty_cache()
