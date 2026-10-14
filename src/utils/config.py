"""
Application configuration — every knob comes from an environment variable.
"""

from __future__ import annotations

import socket
import tempfile
import tomllib
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LoggingMode(StrEnum):
    JSON = "JSON"
    PLAIN_TEXT = "PLAIN_TEXT"


class LogLevel(StrEnum):
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"


class Logging(BaseSettings):
    mode: LoggingMode = Field(
        default=LoggingMode.JSON,
        description="Structured JSON logs (prod) or plain-text logs (dev).",
    )
    level: LogLevel = Field(default=LogLevel.INFO)


class Llm(BaseSettings):
    """OpenAI-compatible Model backend"""

    base_url: str = Field(description="OpenAI-compatible endpoint (Ollama, vLLM, OpenAI, …).")
    api_key: str = Field(
        description="Ollama accepts any non-empty string; real providers need a real key.",
    )
    model: str = Field(description="Default model name for all endpoints unless overridden.")
    timeout_ms: int = Field(
        default=30_000,
        ge=1_000,
        description="Timeout for individual LLM calls, in milliseconds.",
    )


class EndpointOverride(BaseSettings):
    """Optional per-endpoint LLM overrides. Leave unset to fall back to :class:`Llm`"""

    model: str | None = Field(default=None)
    temperature: float | None = Field(default=None)


class NormalizeTtsOverride(EndpointOverride):
    """
    Adds the safety threshold used to decide when to reject an LLM output that strayed too far from the input length.
    """

    max_length_deviation: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
    )


class Tts(BaseSettings):
    """OpenAI-compatible `POST {base_url}/audio/speech` backend (OpenAI, OpenRouter, local shim)."""

    base_url: str = Field(description="OpenAI-compatible endpoint, e.g. https://api.openai.com/v1.")
    api_key: str = Field(description="Sent as the Bearer token.")
    model: str = Field(description="Model name sent in every speech request.")
    voices: str = Field(
        description="Comma-separated static voice names (the contract has no voice-listing endpoint).",
    )
    timeout_ms: int = Field(
        default=30_000,
        ge=1_000,
        description="Timeout for individual TTS calls, in milliseconds.",
    )
    output_dir: Path = Field(default_factory=lambda: Path(tempfile.gettempdir()) / "beatrice-audio")

    @property
    def voices_list(self) -> list[str]:
        return [voice.strip() for voice in self.voices.split(",") if voice.strip()]


class CallbackSettings(BaseSettings):
    """
    Outbound calls to `genUploadUrl`/`statusCallbackUrl` — hosts the client controls.

    ``allowed_hosts`` is a plain (comma-separated) string, not ``list[str]``: pydantic-settings
    JSON-decodes any list-typed field read from an env var before field validators run, so a
    human-friendly comma-separated env var isn't achievable with a list field here.
    """

    allowed_hosts: str = Field(
        default="",
        description=(
            "Comma-separated allow-listed hosts for outbound genUploadUrl/statusCallbackUrl "
            "calls. Beatrice makes an HTTP call to a URL it didn't choose, so any host not "
            "listed here is rejected."
        ),
    )

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]


class GenerateAudio(BaseSettings):
    """`generateAudio` mutation configuration."""

    max_text_length: int = Field(default=4000, ge=1)
    callback: CallbackSettings = Field(default_factory=CallbackSettings)


class RabbitMq(BaseSettings):
    connection_string: str = Field()
    queue_name: str = Field(default="beatrice.generate_audio")
    dlq_name: str = Field(
        default="beatrice.generate_audio.dlq",
        description="Where a job lands once it's not retryable, or delivery_limit is exhausted.",
    )
    prefetch_count: int = Field(
        default=5,
        ge=1,
        description="QoS for the worker consumer (steps 4-6) — not used on the publish side.",
    )
    delivery_limit: int = Field(
        default=3,
        ge=1,
        description="Max attempts (tracked via the x-attempt message header) before a job is routed to the DLQ instead of retried again.",
    )
    retry_delay_seconds: float = Field(
        default=30.0,
        ge=0,
        description="Backoff before retrying a failed job, unless a Retry-After response header says otherwise.",
    )
    worker_enabled: bool = Field(
        default=True,
        description=(
            "Whether this process also consumes `generateAudio` jobs, alongside serving "
            "the GraphQL API, via a background task started in the FastAPI lifespan. "
            "Disabled in tests that need to publish a job and inspect the queue directly."
        ),
    )


class Otel(BaseSettings):
    """OpenTelemetry configuration"""

    enabled: bool = Field()
    exporter_otlp_endpoint: str = Field()
    traces_sampler: str = Field(default="parentbased_always_on")


class Settings(BaseSettings):
    """Runtime configuration surface"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__",
        extra="ignore",
    )

    port: int = Field(default=3000, description="HTTP port to bind.")
    service_name: str = Field(
        default="beatrice",
        description="Reported to OTel and used as a general service identifier.",
    )
    instance_id: str = Field(
        default_factory=socket.gethostname,
        description=(
            "Identifies this replica in logs (Beatrice runs replicated). Override via "
            "INSTANCE_ID — e.g. the pod name in Kubernetes — when the hostname isn't useful."
        ),
    )

    @property
    def app_name(self) -> str:
        """Read ``[project].name`` from pyproject.toml at runtime."""

        pyproject = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))

        return data["project"]["name"]

    # pyright can't see that these are populated from LLM__*/
    # RABBITMQ__*/OTEL__*/TTS__* env vars, not by literally calling Llm()/RabbitMq()/Otel()/
    # Tts() with no arguments.
    logging: Logging = Field(default_factory=Logging)
    llm: Llm = Field(default_factory=Llm)  # pyright: ignore[reportArgumentType]
    explain_word: EndpointOverride = Field(default_factory=EndpointOverride)
    normalize_tts: NormalizeTtsOverride = Field(default_factory=NormalizeTtsOverride)
    tts: Tts = Field(default_factory=Tts)  # pyright: ignore[reportArgumentType]
    generate_audio: GenerateAudio = Field(default_factory=GenerateAudio)
    rabbitmq: RabbitMq = Field(default_factory=RabbitMq)  # pyright: ignore[reportArgumentType]
    otel: Otel = Field(default_factory=Otel)  # pyright: ignore[reportArgumentType]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide :class:`Settings` singleton"""

    return Settings()
