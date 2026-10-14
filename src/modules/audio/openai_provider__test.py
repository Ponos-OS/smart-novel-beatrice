from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from src.modules.audio.exceptions import TtsProviderError
from src.modules.audio.openai_provider import OpenAiSpeechProvider
from src.modules.audio.retry import decide_retry
from src.utils import Tts


def _provider(tmp_path: Path, handler) -> OpenAiSpeechProvider:
    settings = Tts(
        base_url="https://tts.example.com/v1",
        api_key="test-key",
        model="gpt-4o-mini-tts",
        voices="alloy",
        output_dir=tmp_path,
    )
    return OpenAiSpeechProvider(settings, transport=httpx.MockTransport(handler))


def _recording_handler(requests: list[httpx.Request], response: httpx.Response):
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return response

    return handler


async def test_synthesize_posts_openai_speech_request(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []
    provider = _provider(tmp_path, _recording_handler(requests, httpx.Response(200, content=b"a")))

    await provider.synthesize(text="hello", voice="alloy")

    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert str(requests[0].url) == "https://tts.example.com/v1/audio/speech"
    assert requests[0].headers["Authorization"] == "Bearer test-key"
    assert json.loads(requests[0].content) == {
        "model": "gpt-4o-mini-tts",
        "input": "hello",
        "voice": "alloy",
        "response_format": "mp3",
    }


async def test_synthesize_sends_instructions_when_instruct_is_given(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []
    provider = _provider(tmp_path, _recording_handler(requests, httpx.Response(200, content=b"a")))

    await provider.synthesize(text="hello", voice="alloy", instruct="speak in a whisper")

    body = json.loads(requests[0].content)
    assert body["instructions"] == "speak in a whisper"
    assert "instruct" not in body


async def test_synthesize_omits_instructions_when_instruct_is_none(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []
    provider = _provider(tmp_path, _recording_handler(requests, httpx.Response(200, content=b"a")))

    await provider.synthesize(text="hello", voice="alloy")

    assert "instructions" not in json.loads(requests[0].content)


async def test_synthesize_writes_response_body_to_an_mp3_in_output_dir(tmp_path: Path) -> None:
    audio_bytes = b"\x00\x01raw-audio-bytes\xff"
    provider = _provider(tmp_path, _recording_handler([], httpx.Response(200, content=audio_bytes)))

    result = await provider.synthesize(text="hello", voice="alloy")

    assert result.file_path.parent == tmp_path
    assert result.file_path.suffix == ".mp3"
    assert result.file_path.read_bytes() == audio_bytes


async def test_synthesize_raises_provider_error_with_status_code_on_non_2xx(
    tmp_path: Path,
) -> None:
    provider = _provider(
        tmp_path, _recording_handler([], httpx.Response(422, json={"error": "bad voice"}))
    )

    with pytest.raises(TtsProviderError) as exc_info:
        await provider.synthesize(text="hi", voice="nope")

    assert exc_info.value.status_code == 422
    assert list(tmp_path.iterdir()) == []


async def test_synthesize_429_with_retry_after_is_retryable(tmp_path: Path) -> None:
    provider = _provider(
        tmp_path, _recording_handler([], httpx.Response(429, headers={"Retry-After": "7"}))
    )

    with pytest.raises(TtsProviderError) as exc_info:
        await provider.synthesize(text="hi", voice="alloy")
    result = decide_retry(exc_info.value, default_delay_seconds=30.0)

    assert result.should_retry is True


async def test_synthesize_4xx_other_than_408_429_is_not_retryable(tmp_path: Path) -> None:
    provider = _provider(tmp_path, _recording_handler([], httpx.Response(400)))

    with pytest.raises(TtsProviderError) as exc_info:
        await provider.synthesize(text="hi", voice="alloy", instruct="whisper")
    result = decide_retry(exc_info.value, default_delay_seconds=30.0)

    assert result.should_retry is False
