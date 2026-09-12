#!/usr/bin/env bash
# Starts llama.cpp's llama-server against the configured GGUF model.
# See README.md §7 for how to obtain a model and docs/CONTRACTS.md §11 for
# the OpenAI-compatible endpoint contract the backend expects at LLM_BASE_URL.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
[ -f .env ] && set -a && source .env && set +a

: "${LLAMA_MODEL_FILE:=qwen2.5-coder-7b-instruct-q4_k_m.gguf}"
: "${LLAMA_CTX_SIZE:=16384}"
: "${LLAMA_GPU_LAYERS:=99}"
: "${LLAMA_PORT:=8080}"
: "${LLM_MODEL:=decobol-local}"
# Quantized KV cache roughly halves (q8_0) or quarters (q4_0) the VRAM the
# context window costs, so LLAMA_CTX_SIZE can go up without a VRAM overflow.
# Set to "f16" to disable quantization if your build/GPU doesn't like it.
: "${LLAMA_KV_CACHE_TYPE:=q8_0}"
# Flash attention cuts KV-cache memory further and is required by some
# quantized cache types above. Set to 0 to disable if unsupported.
: "${LLAMA_FLASH_ATTN:=1}"

MODEL_PATH="llm/models/${LLAMA_MODEL_FILE}"
if [ ! -f "$MODEL_PATH" ]; then
  echo "error: model file not found: $MODEL_PATH" >&2
  echo "See README.md §7.2 to download one, or set LLAMA_MODEL_FILE." >&2
  exit 1
fi

if ! command -v llama-server >/dev/null 2>&1; then
  echo "error: llama-server not on PATH. Install llama.cpp (README.md §7 prerequisites)." >&2
  exit 1
fi

FLASH_ATTN_FLAG=()
if [ "$LLAMA_FLASH_ATTN" = "1" ]; then
  FLASH_ATTN_FLAG=(-fa)
fi

exec llama-server \
  -m "$MODEL_PATH" \
  --host 127.0.0.1 --port "$LLAMA_PORT" \
  -c "$LLAMA_CTX_SIZE" -ngl "$LLAMA_GPU_LAYERS" \
  --cache-type-k "$LLAMA_KV_CACHE_TYPE" --cache-type-v "$LLAMA_KV_CACHE_TYPE" \
  "${FLASH_ATTN_FLAG[@]}" \
  --alias "$LLM_MODEL" --jinja
