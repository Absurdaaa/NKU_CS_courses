"""Model registry entrypoints."""

from .registry import AVAILABLE_MODELS, build_model
# 明确告诉外部"这个包只对外暴露这两个东西"
__all__ = ["AVAILABLE_MODELS", "build_model"]
