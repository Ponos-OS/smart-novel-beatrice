# Self-improvement log

## OpenAI-compatible TTS - step 1 (2026-10-14)

- Changed: added PROCESS.md item 10 (check venv/`.env` health before the first test run); SELF_IMPROVE.md now asks about environmental blockers.
- Why: the unit suite couldn't start (stale `.venv`, rebuilt) and then failed on a stale local `.env` (old `TTS__QWEN__*`, updated). Neither was a code problem. Step 1 also had to fold in more than "minimal" fixes (Qwen provider takes the flat `Tts`, Gemini provider deleted, voices cache dropped) because the old providers consumed the removed settings classes; REQUIREMENTS.md's step 2/3 scope overlaps with that.
- Not committed: REQUIREMENTS.md says to leave changes uncommitted for review.

## OpenAI-compatible TTS - step 2 (2026-10-14)

- Changed: no process-doc edit; one data point only.
- Why: `git commit` failed silently-ish because `pre-commit` wasn't on PATH (fresh `.venv`); `export PATH="$PWD/.venv/bin:$PATH"` fixed it. Same class as step 1's environmental blockers (PROCESS.md item 10), so not generalized further yet.
- `TtsProviderError` doesn't carry response headers, so a 429's `Retry-After` is not honored (delay falls back to the default); the AC only requires "retryable", which holds.
- Not committed: awaiting the user's review.

## OpenAI-compatible TTS - step 3 (2026-10-14)

- Changed: no process-doc edit; one data point only.
- Why: the `wire-contract-coverage` pre-commit hook fired on step 2 for a `types.py` edit that only removed an unused model (no wire change) and also failed `make schema`'s embedded `pre-commit run`; used the hook's documented `SKIP=wire-contract-coverage` for that commit. If it recurs on another non-wire edit, add a note to PROCESS.md.
- `tests/conftest.py` fixtures needed no changes beyond docstrings; the integration stubs shrank (one `POST /audio/speech` stub replaces the two-hop DashScope flow).
- Not committed: awaiting the user's review.

## OpenAI-compatible TTS - step 4 (2026-10-14)

- Changed: no process-doc edit; one data point only.
- Why: the manual check surfaced two facts no review would: the dev-only presign server still named uploads `.wav` (fixed to `.mp3`), and the gitignored local `.env` had a stale `GENERATE_AUDIO__CALLBACK__ALLOWED_HOSTS` (missing `presign-server`), which made the in-container callbacks fail until aligned with `.env.example`. MP3 via libsndfile 1.2.2 worked, so the REQUIREMENTS caveat did not apply.
- Not committed: awaiting the user's review.

## OpenAI-compatible TTS - step 5 (2026-10-14)

- Changed: no process-doc edit.
- Why: earlier steps had already removed most provider wording as they went (schema descriptions in 3, `.env.example`/README table in 1), so the cleanup reduced to a README paragraph plus two stale strings (an exception docstring, test fixtures naming `qwen3-tts`). Running the AC grep before editing showed that, and kept the step small.
- Not committed: awaiting the user's review. This is the last step: `REQUIREMENTS.md` and this log are to be archived and removed per AGENTS.md.
