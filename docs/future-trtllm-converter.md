# Future: TRT-LLM converter for PersonaPlex

**Status:** parked. 5-9 days custom work, uncertain real-time outcome on Spark.

## Why parked

- Demo needs real-time; timeline doesn't justify uncertain-outcome project
- Better short-term options: rent H100 cloud GPU, build cascade pipeline (Whisper -> small LLM -> fast TTS), or pivot model
- Re-evaluate when production HW finalized (NVFP4/Blackwell, FP8/Hopper, INT8/Ampere)

## Problem

- PersonaPlex (NVIDIA 7B Moshi-based full-duplex S2S) runs but choppy on DGX Spark
- 14 GB FP16 weights/step exceed Spark's 273 GB/s bandwidth budget for real-time S2S
- NVIDIA CES 2026 showed 2.5x speedups via NVFP4 + Eagle3 spec decoding in TRT-LLM, but no Moshi recipe

## Investigation findings

- TRT-LLM supported-models registry: no Moshi/PersonaPlex/Kyutai. Full-duplex S2S not a supported category
- NVIDIA's personaplex Dockerfile: stock PyTorch, no optimization
- No NIM for PersonaPlex on build.nvidia.com
- `dgx-spark-playbooks` has NVFP4 + Spec Decoding playbooks but text-only (DeepSeek example)
- Conclusion: converter is custom work, not a recipe

## LM primitives (Mimi audio codec stays on PyTorch)

| # | Primitive | Source | TRT-LLM backend | Effort |
|---|-----------|--------|-----------------|--------|
| 1 | RMSNorm | modules/transformer.py | Built-in (rms_norm.py) | none |
| 2 | LayerNormF32 | modules/transformer.py | LayerNorm exists, F32 wrapper needed | trivial |
| 3 | LayerScale | modules/transformer.py | Not built-in (self.scale * x) | trivial |
| 4 | Rotary Embedding | modules/rope.py | Built-in (rotary_embedding.py) | none, verify scaling/base |
| 5 | apply_rope custom application | modules/rope.py | TRT-LLM RoPE may differ | low — verify equivalence |
| 6 | StreamingMultiheadAttention | modules/transformer.py | Has base Attention | low — wrap |
| 7 | RingKVCache (circular buffer) | modules/transformer.py | TRT-LLM uses grow-only paged KV | medium — adapt or write |
| 8 | ActivationGating (SwiGLU-style) | modules/gating.py | Likely built-in | low — confirm |
| 9 | ScaledEmbedding | models/lm.py | Trivial extension of Embedding | trivial |
| 10 | Depth Transformer | models/lm.py | NOT in TRT-LLM | HIGH — architectural novelty |
| 11 | Multi-codebook output head (N parallel projections) | models/lm.py | Standard LM has single head | medium — custom head |
| 12 | Delayed prediction pattern | models/lm.py | Inference-loop concern | medium — runtime orchestration |
| 13 | StreamingTransformerLayer | modules/transformer.py | Has DecoderLayer base | low — wrap |
| 14 | Causal attention w/ custom context window | models/lm.py | Sliding window supported | low |

Summary: 6 built-in, 5 trivial-to-low, 3 are the real work — Depth Transformer, RingKVCache, multi-codebook output + delayed prediction.

## Mimi codec (stays on PyTorch, out of TRT-LLM scope)

- SEANetEncoder / SEANetDecoder (modules/seanet.py)
- StreamingConv1d / StreamingConvTranspose1d (modules/conv.py)
- NormConv1d / NormConvTranspose1d (modules/conv.py)
- TransposedLayerNorm (modules/conv.py)
- Residual VQ quantizer (quantization/vq.py)

## Phase breakdown (if revived)

| Phase | Days |
|-------|------|
| Architecture reverse-engineering | 1 |
| Model definition in TRT-LLM PyTorch backend | 2-3 |
| Weight conversion (safetensors -> TRT-LLM layout) | 0.5 |
| NVFP4 calibration with audio+text streams | 1 |
| Engine build (trtllm-build for sm_121a) | 0.5 |
| Streaming runtime (replace moshi/server.py inference loop) | 1-2 |
| Debug + benchmark | 1-2 |
| **Total** | **5-9** |

## Risks (hard-flagged)

- Depth Transformer may lack TRT-LLM primitives -> PyTorch fallback per step kills perf
- NVFP4 calibration may degrade audio quality (no plain-text pattern works for audio)
- Streaming KV cache w/ TRT-LLM finicky; concurrent listen+speak doubles state complexity
- **Bandwidth ceiling:** Spark 273 GB/s; PersonaPlex tested on H100/H200 class (3,350 GB/s). NVFP4 ~4x effective -> ~1,100 GB/s. Still ~3x below H100 native. Real-time on Spark not guaranteed even after all the work.

## When to revisit

- NVIDIA publishes Moshi/PersonaPlex TRT-LLM recipe in dgx-spark-playbooks
- Final production HW confirmed and is Blackwell-class w/ enough bandwidth headroom
- Use case shifts to non-realtime (work becomes "nice to have" not "must have")
