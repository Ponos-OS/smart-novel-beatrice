# Single OpenAI-compatible TTS API

DO NOT COMMIT THE CHANGES, I WANNA REVIEW THEM FIRST.

## Goal

Replace the per-provider TTS code and settings (`TTS__QWEN__*`, `TTS__GEMINI__*`, `TTS__DEFAULT_PROVIDER`) with one client speaking the OpenAI `POST {base_url}/audio/speech` contract, configured by one flat set of `TTS__*` env vars. Pointing Beatrice at OpenAI, OpenRouter (which serves Qwen3-TTS and Gemini-TTS through the same route), or the local Qwen3-TTS shim becomes a config change.

Env vars then differ only by modality, mirroring the existing `LLM__*` block:

| Text (existing)   | Audio (new)                                        |
| ----------------- | -------------------------------------------------- |
| `LLM__BASE_URL`   | `TTS__BASE_URL`                                    |
| `LLM__API_KEY`    | `TTS__API_KEY`                                     |
| `LLM__MODEL`      | `TTS__MODEL`                                       |
| `LLM__TIMEOUT_MS` | `TTS__TIMEOUT_MS`                                  |
| -                 | `TTS__VOICES` (comma-separated), `TTS__OUTPUT_DIR` |

## Decisions

- **Wire contract**: OpenAI `POST /audio/speech` with body `{model, input, voice, instructions?, response_format: "mp3"}`; response is raw audio bytes. Max `input` is 4096 chars, above the default `GENERATE_AUDIO__MAX_TEXT_LENGTH=4000`. Full reference for the request/response shape: [openai-speech.md](./openai-speech.md) (read it before steps 2 and 4).
- **Drop the native DashScope and Google Cloud TTS adapters.** Neither is OpenAI-compatible (DashScope returns a URL to fetch, Cloud TTS returns base64 JSON). Both models stay reachable through OpenRouter, so no capability is lost.
- **Voices are static config** (`TTS__VOICES`). OpenAI has no voice-listing endpoint, and the other two never needed one with this contract. `audioVoices` no longer calls the provider, so the provider call, the process-wide cache, and its lock go away.
- **`instruct` is passed through as `instructions` for every provider.** Support now depends on the configured model (OpenAI rejects it for `tts-1*`), not on a provider enum. The upstream 4xx surfaces as `TTS_PROVIDER_ERROR` (non-retryable). `INSTRUCT_NOT_SUPPORTED` and the `language` filter are removed.
- **Keep the `TtsProvider` Protocol** as the seam resolvers/worker depend on, now with one implementation and only `synthesize` + `aclose`.
- **Plain `httpx`** (not the `openai` SDK): keeps the existing `TtsProviderError`/`decide_retry` status-code handling, no hidden SDK retries, and follows the `httpx-async-transport` skill.
- **Breaking change** (env var renames, removed GraphQL error code and argument wording): commit as `feat!` so semantic-release cuts a major.

## Steps

### Step 1 - Flat `Tts` settings

Replace `GeminiTtsSettings`, `QwenTtsSettings`, `TtsProviderName`, and the nested `Tts.qwen`/`Tts.gemini`/`default_provider` with a flat `Tts` in `src/utils/config.py`:

- Required: `base_url`, `api_key`, `model`, `voices` (comma-separated string + `voices_list` property, per the `settings-list-env-field` skill).
- Defaults: `timeout_ms=30_000` (`ge=1_000`), `output_dir` as today.
- Delete the `model_validator` (nothing is conditionally required anymore).
- Update `src/utils/__init__.py` exports, `.env.example`, `conftest.py` (root and `tests/conftest.py` env vars), and the `.github/README.md` env table.
- Fold the minimal fixes into `resolver.py`/`worker.py`/`provider.py` so the pre-commit unit run stays green (they still reference `default_provider`); real rewrites happen in steps 2-3.

AC:

- App fails fast at startup naming the missing var when any of `TTS__BASE_URL`, `TTS__API_KEY`, `TTS__MODEL`, `TTS__VOICES` is unset.
- `voices_list` trims whitespace and drops empties.
- No reference to `TTS__QWEN__`, `TTS__GEMINI__`, `TTS__DEFAULT_PROVIDER` remains outside `local-setup/notebooks/`.

Test: unit (`config__test.py`: required fields, `voices_list` parsing, timeout bound). No GraphQL surface; skip graphql-api-tester.

### Step 2 - Single provider implementation

Add `src/modules/audio/openai_provider.py` (`OpenAiSpeechProvider`, accepting an optional `transport` per the `httpx-async-transport` skill) and shrink the Protocol in `provider.py` to `synthesize` and `aclose`.

- `POST /audio/speech` with `Authorization: Bearer <api_key>`; send `instructions` only when `instruct` is set; stream the response body to `<output_dir>/<uuid>.mp3`.
- Non-2xx raises `TtsProviderError` with `status_code` (unchanged contract for `retry.py`). Read the body before raising on a streamed response.
- `build_provider(settings)` returns the one implementation (no name argument).
- Delete `qwen_provider.py`, `gemini_provider.py`, and their tests; delete `InstructNotSupportedError`.
- Remove `Voice` and `get_voices` from `types.py`/`provider.py` if nothing else uses them.

AC:

- Request body and headers match the contract above; `instructions` absent when `instruct` is `None`.
- Bytes written to disk equal the response body; a 429 with `Retry-After` still produces a retryable error through `decide_retry`.

Test: unit with `httpx.MockTransport` (assert in the Assert block, not inside the handler, per CONTRIBUTING AAA note). Skip graphql-api-tester.

### Step 3 - Resolver and worker

- `resolve_audio_voices` returns `settings.tts.voices_list`; delete `_voices_cache` and its lock.
- `generateAudio`: validate voice against `voices_list`; stop rejecting `instruct` by provider; update the `instruct` argument description (drop "Qwen3-TTS-only", "Rejected when...", "English-only"). Update the `audioVoices` description if it mentions providers.
- `worker.py`: use `build_provider(settings)`; log field `model` becomes `settings.tts.model`.
- Update `tests/test_generate_audio_graphql.py` stubs from the DashScope route/URL-fetch flow to `POST /audio/speech` returning bytes; the `instruct` pipeline test asserts on `instructions` in that request. Delete the unit test that rejects `instruct` for non-Qwen providers.
- Run `make schema`; commit the regenerated `docs/schema.graphql`.

AC:

- `audioVoices` makes no outbound call.
- `generateAudio` with `instruct` is accepted regardless of model; the value reaches the provider request as `instructions`.
- Unknown voice still yields `INVALID_VOICE`.

Test: unit (resolver, worker, retry paths via the Protocol double); integration updates as above (one happy path per operation, no new fixtures). Run graphql-api-tester on `audioVoices` and `generateAudio`.

### Step 4 - Local Qwen3-TTS shim speaks the OpenAI contract

Rewrite `local-setup/qwen-tts/server.py` to expose `POST /v1/audio/speech` (`model`, `input`, `voice`, `instructions`, `response_format`) returning audio bytes with the right `Content-Type`; remove the `/files/{filename}` indirection and `language_type`. Keep `_VOICES` mapping and `generate_custom_voice`. Update its docstring (it references `Qwen3TtsProvider`) and the compose/`.env.example` values: `TTS__BASE_URL=http://qwen-tts:8001/v1`, `TTS__MODEL=qwen3-tts-instruct-flash`, `TTS__VOICES=default`, generous `TTS__TIMEOUT_MS` as today.

AC:

- `docker compose up --build -d` then a `generateAudio` against the local stack produces an MP3 uploaded through the presign server.
- Unknown voice returns 4xx. A `response_format` other than `mp3` also returns 4xx.
- Verified: the image's libsndfile (1.2.2) writes MP3 natively, so no extra encoder is needed.

Test: manual (no pytest tier; dev-only infra). Verify `response_format=mp3` actually works in the shim's environment: libsndfile's MP3 write support is version-dependent, and if it is missing, encode via another route or document the format limit here. Use `run_in_background` for the cold compose build. Skip graphql-api-tester.

### Step 5 - Docs cleanup

- `.github/README.md`: single TTS env table, one paragraph listing OpenAI, OpenRouter, and the local shim as example targets.
- `.github/CONTRIBUTING.md`: update any mention of provider-specific settings or fixtures (`TTS__QWEN__*` in the `wiremock` notes).
- Remove the now-obsolete "Qwen3-TTS only" wording anywhere else (`grep -ri 'qwen3-tts\|gemini'` under `src/`, `docs/schema.graphql`).
- Leave `local-setup/notebooks/` and archived `docs/v*/` untouched.

AC: grep from the first step's AC is clean; README stays short.

Test: none beyond `make test` and `make lint_check`. Skip graphql-api-tester.

## Out of scope

- Changing the `AGENTS.md` discriminated-`BaseSettings` rule (still valid guidance, just unused by TTS now).
- Per-voice language metadata, non-English support, custom OpenAI voice objects, `speed`, or output formats other than MP3.
- Merging `LLM__*` and `TTS__*`: they target different endpoints and keys.
