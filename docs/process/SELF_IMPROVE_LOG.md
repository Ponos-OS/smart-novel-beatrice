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
