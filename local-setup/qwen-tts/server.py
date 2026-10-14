"""
OpenAI-compatible TTS server backed by Qwen3-TTS, matching the `POST /audio/speech`
contract `OpenAiSpeechProvider` (`src/modules/audio/openai_provider.py`) expects:

- `POST /v1/audio/speech`
  -> {"model", "input", "voice", "instructions"?, "response_format"?}
  -> raw audio bytes (MP3 only), with a matching `Content-Type`.

`_VOICES` maps the fixed voice names this server exposes to one of Qwen3-TTS's built-in
preset speakers, synthesized via `generate_custom_voice`. This (rather than
`generate_voice_clone`) is what lets `instructions` (natural-language tone/style/emotion
guidance) combine with a consistent named voice in one call.
"""

import os
from io import BytesIO

import soundfile as sf
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from qwen_tts import Qwen3TTSModel


MODEL_ID = os.environ.get("QWEN_TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice")
DEVICE = os.environ.get("QWEN_TTS_DEVICE", "cpu")
PORT = int(os.environ.get("QWEN_TTS_PORT", "8001"))

_VOICES = {"default": "Ryan"}
_LANGUAGE = "English"

app = FastAPI()
model: Qwen3TTSModel | None = None


class SpeechRequest(BaseModel):
    model: str
    input: str
    voice: str
    instructions: str | None = None
    response_format: str = "mp3"


@app.on_event("startup")
def load_model() -> None:
    global model
    model = Qwen3TTSModel.from_pretrained(
        MODEL_ID,
        device_map=DEVICE,
        dtype=torch.bfloat16 if DEVICE != "cpu" else torch.float32,
    )


@app.get("/health")
def health() -> dict[str, bool]:
    return {"loaded": model is not None}


@app.post("/v1/audio/speech")
def speech(request: SpeechRequest) -> Response:
    speaker = _VOICES.get(request.voice)
    if speaker is None:
        raise HTTPException(status_code=422, detail=f"Unknown voice: {request.voice}")

    if request.response_format != "mp3":
        raise HTTPException(
            status_code=422, detail=f"Unsupported response_format: {request.response_format}"
        )

    wavs, sample_rate = model.generate_custom_voice(
        text=request.input,
        language=_LANGUAGE,
        speaker=speaker,
        instruct=request.instructions,
    )

    buffer = BytesIO()
    sf.write(buffer, wavs[0], sample_rate, format="MP3")

    return Response(content=buffer.getvalue(), media_type="audio/mpeg")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
