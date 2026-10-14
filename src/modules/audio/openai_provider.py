"""
Client for the OpenAI `POST /audio/speech` contract, served by OpenAI, OpenRouter, or
the local Qwen3-TTS shim alike.
"""

from __future__ import annotations

import uuid

import httpx

from src.modules.audio.exceptions import TtsProviderError
from src.modules.audio.types import SynthesizedAudio
from src.utils import Tts


PROVIDER_NAME = "openai-speech"
_SPEECH_PATH = "audio/speech"


class OpenAiSpeechProvider:
    def __init__(
        self,
        settings: Tts,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._model = settings.model
        self._output_dir = settings.output_dir
        self._client = httpx.AsyncClient(
            base_url=settings.base_url,
            headers={"Authorization": f"Bearer {settings.api_key}"},
            timeout=settings.timeout_ms / 1000,
            transport=transport,
        )

    async def synthesize(
        self, *, text: str, voice: str, instruct: str | None = None
    ) -> SynthesizedAudio:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        file_path = self._output_dir / f"{uuid.uuid4()}.mp3"

        body: dict[str, str] = {
            "model": self._model,
            "input": text,
            "voice": voice,
            "response_format": "mp3",
        }
        if instruct is not None:
            body["instructions"] = instruct

        async with self._client.stream("POST", _SPEECH_PATH, json=body) as response:
            if response.is_error:
                await response.aread()
                raise TtsProviderError(
                    provider=PROVIDER_NAME,
                    message=f"POST {_SPEECH_PATH} -> {response.status_code}",
                    status_code=response.status_code,
                )

            with file_path.open("wb") as fh:
                async for chunk in response.aiter_bytes():
                    fh.write(chunk)

        return SynthesizedAudio(file_path=file_path)

    async def aclose(self) -> None:
        await self._client.aclose()
