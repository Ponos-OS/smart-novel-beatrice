# Self-improvement log

## OpenAI-compatible TTS - step 1 (2026-10-14)

- Changed: added PROCESS.md item 10 (check venv/`.env` health before the first test run); SELF_IMPROVE.md now asks about environmental blockers.
- Why: the unit suite couldn't start (stale `.venv`, rebuilt) and then failed on a stale local `.env` (old `TTS__QWEN__*`, updated). Neither was a code problem. Step 1 also had to fold in more than "minimal" fixes (Qwen provider takes the flat `Tts`, Gemini provider deleted, voices cache dropped) because the old providers consumed the removed settings classes; REQUIREMENTS.md's step 2/3 scope overlaps with that.
- Not committed: REQUIREMENTS.md says to leave changes uncommitted for review.
