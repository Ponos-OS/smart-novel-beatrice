from __future__ import annotations

from src.modules.audio.provider import build_provider
from src.modules.audio.qwen_provider import Qwen3TtsProvider
from src.utils import get_settings


def test_build_provider_returns_the_configured_provider() -> None:
    result = build_provider(get_settings())

    assert isinstance(result, Qwen3TtsProvider)
