# Copyright (c) Meta Platforms, Inc. and affiliates. All Rights Reserved\n

from .model import *  # noqa


def __getattr__(name):
    if name in ("SAMAudioJudgeModel", "SAMAudioJudgeOutput"):
        from . import judge

        return getattr(judge, name)
    raise AttributeError(name)
