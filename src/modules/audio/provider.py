"""
Interface the resolver and worker depend on, regardless of which OpenAI-compatible
speech endpoint is configured.
"""

from __future__ import annotations

from typing import Protocol

from src.modules.audio.openai_provider import OpenAiSpeechProvider
from src.modules.audio.types import SynthesizedAudio
from src.utils import Settings


class TtsProvider(Protocol):
    async def synthesize(
        self, *, text: str, voice: str, instruct: str | None = None
    ) -> SynthesizedAudio:
        """
        Generate speech audio for `text` using `voice`, and store it to disk.

        :param instruct: Natural-language style/tone/emotion guidance, sent as
            `instructions`. Whether the configured model honors it is up to the endpoint.
        """
        ...

    async def aclose(self) -> None:
        """Release the underlying HTTP client."""
        ...


def build_provider(settings: Settings) -> TtsProvider:
    return OpenAiSpeechProvider(settings.tts)
