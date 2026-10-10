"""Portability policy tests; these do not claim GPU/OS inference coverage."""
from types import SimpleNamespace
from pathlib import Path
import pytest

from lab.config import runtime_paths
from lab.device import select_device, synchronize


def test_runtime_paths_follow_active_conda_and_keep_ffmpeg_pair(tmp_path, monkeypatch):
    from lab import config
    for name in ('SAM_LAB_AUDIO_PYTHON', 'SAM_LAB_VISION_PYTHON', 'SAM_LAB_FFMPEG', 'SAM_LAB_FFPROBE'):
        monkeypatch.delenv(name, raising=False)
    bin_dir = tmp_path / 'miniforge/envs/sam3/bin'
    bin_dir.mkdir(parents=True)
    for name in ('python', 'ffmpeg', 'ffprobe'):
        (bin_dir / name).touch()
    monkeypatch.setattr(config.sys, 'executable', str(bin_dir / 'python'))
    audio, vision, ffmpeg, ffprobe = runtime_paths()
    assert audio == str(bin_dir / 'python')
    assert vision == str(bin_dir.parent.parent / 'sam3-vision/bin/python')
    assert Path(ffmpeg).parent == Path(ffprobe).parent == bin_dir
    monkeypatch.setenv('SAM_LAB_VISION_PYTHON', str(tmp_path / 'custom-vision/bin/python'))
    monkeypatch.setenv('SAM_LAB_FFPROBE', str(tmp_path / 'custom-ffprobe'))
    assert runtime_paths()[1] == str(tmp_path / 'custom-vision/bin/python')
    assert runtime_paths()[3] == str(tmp_path / 'custom-ffprobe')


@pytest.mark.parametrize('cuda,mps,expected', [(True, False, 'cuda'), (False, True, 'mps'), (False, False, 'cpu')])
def test_device_auto_and_override(cuda, mps, expected, monkeypatch):
    torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: cuda),
                            backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: mps)))
    monkeypatch.delenv('SAM_LAB_DEVICE', raising=False)
    assert select_device(torch) == expected
    monkeypatch.setenv('SAM_LAB_DEVICE', 'cpu')
    assert select_device(torch) == 'cpu'
    monkeypatch.setenv('SAM_LAB_DEVICE', 'bad-device')
    with pytest.raises(ValueError):
        select_device(torch)
    monkeypatch.setenv('SAM_LAB_DEVICE', 'cuda' if not cuda else 'mps')
    with pytest.raises(RuntimeError, match='no está disponible'):
        select_device(torch)


def test_gpu_timings_wait_for_completion():
    calls = []
    torch = SimpleNamespace(cuda=SimpleNamespace(synchronize=lambda: calls.append('cuda')),
                            mps=SimpleNamespace(synchronize=lambda: calls.append('mps')))
    for device in ('cpu', 'cuda', 'mps'):
        synchronize(torch, device)
    assert calls == ['cuda', 'mps']
