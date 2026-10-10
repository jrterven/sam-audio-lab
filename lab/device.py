"""Shared device policy for the isolated audio and vision runtimes."""
import os


def select_device(torch):
    requested = os.environ.get('SAM_LAB_DEVICE', 'auto').lower()
    available = {'cpu': True, 'cuda': torch.cuda.is_available(), 'mps': torch.backends.mps.is_available()}
    if requested == 'auto':
        return next(d for d in ('cuda', 'mps', 'cpu') if available[d])
    if requested not in available:
        raise ValueError('SAM_LAB_DEVICE debe ser auto, cuda, mps o cpu.')
    if not available[requested]:
        raise RuntimeError(f'El dispositivo {requested} no está disponible en este entorno de PyTorch.')
    return requested


def synchronize(torch, device):
    if device in ('cuda', 'mps'):
        getattr(torch, device).synchronize()


def empty_cache(torch, device):
    if device in ('cuda', 'mps'):
        getattr(torch, device).empty_cache()
