# Future: LLM post-processing for dictation

Idea parked for later. Add an optional LLM step after whisper so dictation can output markdown (for prompting AI tools) or stay plain (for chat). Toggle at speaking time.

> For the narrower problem of "whisper misspells domain terms," see [`future-prompt-biasing.md`](future-prompt-biasing.md) — much cheaper, no second model. Composable with this doc's approach if both are eventually built.

## Why an LLM is needed

Whisper transcribes literally. Saying "bullet one foo bullet two bar" writes exactly that. whisper.cpp's `--prompt` biases vocabulary, not formatting — useless for real markdown structure. Need an instruction-tuned LLM to reformat.

## Architecture change

Current: `audio -> whisper -> text -> typed`
Proposed: `audio -> whisper -> LLM(format) -> text -> typed`

Adds ~0.5-2s latency.

## LLM placement options

- **Local on Spark (Ollama / llama.cpp)** — preferred. Stays on LAN, no per-token cost, 128 GB unified mem fits up to ~70B quantized. Llama 3.1 8B or Qwen 2.5 7B is the fast/quality sweet spot. Latency ~0.3-1s.
- **Anthropic / OpenAI API** — cleaner output, costs money, leaves the network (Zscaler may inspect on corp Mac).
- whisper.cpp `--prompt` alone — does not work for formatting.

## Toggle UX options

- **Two hotkeys** (preferred) — e.g., `Option+Ctrl` = plain, `Option+Cmd` = markdown. Zero friction at use time, intent is explicit.
- Menu bar toggle (tiny Swift/rumps app) — persistent state, more to build.
- Voice trigger ("format markdown") — flaky.
- `.env` flag + restart — crude.

## Additional modes unlocked once LLM step exists

- Filler cleanup — strip "um", "uh", false starts (probably always-on)
- Punctuation/casing improvement
- Email/proofread polish (its own hotkey)
- Translate — whisper has `--translate` built in, no LLM needed

## Open questions

- Local LLM or API for v1?
- Which model? (Llama 3.1 8B / Qwen 2.5 7B / Llama 3.3 70B quantized)
- Hotkey assignments — verify no macOS conflicts
- Plain mode also runs cleanup pass, or stay literal?
- Latency budget — 1s acceptable for markdown mode?

## Pre-reqs to start building

1. Pick LLM + host (Ollama on Spark is fastest path)
2. Add `/format` endpoint to a small wrapper service on Spark, or call Ollama directly from client
3. Update `dictate.py` to support two hotkeys, route audio differently per mode
4. Update `.env.example` and `docs/corporate-mac-setup.md`
