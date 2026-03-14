# internal-vlm pull evidence

Generated: 2026-03-13 22:45:11 UTC

## Container image

- Reference:
  `ghcr.io/ggml-org/llama.cpp@sha256:93b95b367a10b6e417abc1974f2e1f376df3ff6fc8723f90080daa160f60d9a5`
- Verified platform: `linux/arm64`

## Artifact source

- Model repo: [Mungert/Qwen2.5-VL-3B-Instruct-GGUF](https://huggingface.co/Mungert/Qwen2.5-VL-3B-Instruct-GGUF)
- Download URLs:
  - [Qwen2.5-VL-3B-Instruct-q4_k_m.gguf](https://huggingface.co/Mungert/Qwen2.5-VL-3B-Instruct-GGUF/resolve/main/Qwen2.5-VL-3B-Instruct-q4_k_m.gguf)
  - [Qwen2.5-VL-3B-Instruct-mmproj-f16.gguf](https://huggingface.co/Mungert/Qwen2.5-VL-3B-Instruct-GGUF/resolve/main/Qwen2.5-VL-3B-Instruct-mmproj-f16.gguf)

## Downloaded files

| File | Absolute path | Size (bytes) | SHA-256 |
| --- | --- | ---: | --- |
| `Qwen2.5-VL-3B-Instruct-q4_k_m.gguf` | `/Users/test/Library/Application Support/UKDataExtraction/models/qwen/qwen2.5-vl-3b-instruct/Qwen2.5-VL-3B-Instruct-q4_k_m.gguf` | `1929902656` | `1c25a45390fe6e5e15365ec57ffb115d27edc2360eb8fe6da8069b000055ed3e` |
| `Qwen2.5-VL-3B-Instruct-mmproj-f16.gguf` | `/Users/test/Library/Application Support/UKDataExtraction/models/qwen/qwen2.5-vl-3b-instruct/Qwen2.5-VL-3B-Instruct-mmproj-f16.gguf` | `1338428640` | `bfe23b6f49e1c5da0692000e81f7cf704e712c57b643b7ea694dfb27998cfa41` |

## Notes

- Files were downloaded with `curl -fL -C - --retry 3` (resume + retries).
- Directory used: `/Users/test/Library/Application Support/UKDataExtraction/models/qwen/qwen2.5-vl-3b-instruct`
- These filenames are now the defaults in `.env.internal-vlm.example`.
- Runtime image selection was switched to `ggml-org/llama.cpp` because older `llama-cpp-python` image builds failed with `unknown model architecture: 'qwen2vl'`.
