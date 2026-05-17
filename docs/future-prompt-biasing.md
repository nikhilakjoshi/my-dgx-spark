# Future: per-request prompt biasing (vocab + recent context)

Parked. Cheaper alternative to LLM post-processing — fixes the "whisper misspelled as wisper / whispr" class of error without adding a second model.

## Why this exists separately from the LLM doc

[`future-llm-postprocess.md`](future-llm-postprocess.md) covers LLM-style transforms: markdown formatting, filler cleanup, polish. That's expensive in latency and complexity.

This doc covers a much narrower problem: whisper occasionally mishears domain terms (names, products, jargon). Solvable by biasing the decoder via whisper.cpp's `--prompt` mechanism. No second model, no architecture change, zero added latency.

## How whisper prompt biasing works

whisper.cpp accepts a `prompt` field per `/transcribe` request (multipart form). Its tokens are prepended to the decoder context. The model is more likely to emit terms it's already "seen" in that prompt.

Typical content:
- Domain glossary: "Names and terms: Whisper, DGX Spark, GitHub, Claude, FastAPI, Anthropic, Zscaler..."
- Recent transcripts: last N completed dictations, joined.

Prompt budget is small (a few hundred tokens at most), so the content has to be tight.

## Architecture (no server changes needed)

```
Mac dictate.py
  - glossary.txt (curated by user, committed in repo or gitignored — TBD)
  - in-memory deque(maxlen=N) of recent transcripts
  - on POST: prompt = glossary + " " + "  ".join(deque)
  - sends as form field `prompt`
Spark whisper-server
  - already accepts `prompt` field, no change
```

## Implementation sketch (v1)

- Add `glossary.txt` in `whisper-dictate/client/`. One topic per line, free form.
- In `dictate.py`:
  - Load glossary at startup (graceful if missing).
  - Maintain `recent = collections.deque(maxlen=8)`.
  - Build prompt = `glossary + "\n" + " ".join(recent)`, trim to last ~500 chars.
  - Post `prompt` alongside `file` in multipart.
  - On success, push the cleaned transcript onto `recent`.

Roughly 20 lines.

## Limits of this approach (when LLM post-process is still needed)

- Can only bias generation. Cannot correct after the fact.
- Does not reformat (markdown mode still wants LLM).
- Does not fix grammar, fillers, or rambling.
- Sliding-window context is lossy — only last few transcripts.

## Open questions

- Glossary committed to repo or gitignored? Probably committed — it's not sensitive and rebuild value is high.
- Recent-context deque size — 5? 10? Trade off prompt budget vs context value.
- Cap prompt length at how many tokens?
- Add a "no prompt" hotkey for noisy / off-topic dictation?
- Auto-extract glossary terms from past transcripts (frequency-based), or curate by hand?

## Related

- [`future-llm-postprocess.md`](future-llm-postprocess.md) — heavier path; orthogonal but composable. If we ever add the LLM step, biasing still helps before that step runs.
