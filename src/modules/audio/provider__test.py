from __future__ import annotations

from src.modules.audio.openai_provider import OpenAiSpeechProvider
from src.modules.audio.provider import build_provider
from src.utils import get_settings


def test_build_provider_returns_the_openai_speech_provider() -> None:
    result = build_provider(get_settings())

    assert isinstance(result, OpenAiSpeechProvider)
