# Copyright (c) Meta Platforms, Inc. and affiliates. All Rights Reserved\n

from .model.model import SAMAudio
from .processor import SAMAudioJudgeProcessor, SAMAudioProcessor

__all__ = ["SAMAudio", "SAMAudioProcessor", "SAMAudioJudgeModel", "SAMAudioJudgeProcessor"]


def __getattr__(name):
    if name == "SAMAudioJudgeModel":
        from .model.judge import SAMAudioJudgeModel

        return SAMAudioJudgeModel
    raise AttributeError(name)
