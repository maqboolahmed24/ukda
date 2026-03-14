# internal-ner pull evidence

Generated: 2026-03-13 23:41:10 UTC

## Container image

- Pulled base reference:
  `python:3.11-slim@sha256:d64a1009c676551d50bdd2a0f9a4a5f63423a5f070d9284e00e4cba788953f4b`
- Verified platform: `linux/arm64`
- Runtime image built from base: `ukda/internal-ner:arm64`
- Built runtime image id: `sha256:30a8847187e71c1ec7a9a2c8128ab2219632cba090b5197429ec74189ed09fb8`

## Artifact source

- GLiNER repo: [urchade/gliner_small-v2.1](https://huggingface.co/urchade/gliner_small-v2.1)
- DeBERTa tokenizer/config repo: [microsoft/deberta-v3-small](https://huggingface.co/microsoft/deberta-v3-small)

## Downloaded files

| File | Absolute path | Size (bytes) | SHA-256 |
| --- | --- | ---: | --- |
| `README.md` | `/Users/test/Library/Application Support/UKDataExtraction/models/gliner/gliner-small-v2.1/README.md` | `4756` | `5f665c0a6a0e7431ecf0ff59555a418e27601c4c3e8bc1616087a25490294a30` |
| `gliner_config.json` | `/Users/test/Library/Application Support/UKDataExtraction/models/gliner/gliner-small-v2.1/gliner_config.json` | `477` | `eb963bd7182a1eaed4d170a87348ab62de6fc4eb30cfa7130c80846fee43d0ac` |
| `pytorch_model.bin` | `/Users/test/Library/Application Support/UKDataExtraction/models/gliner/gliner-small-v2.1/pytorch_model.bin` | `610652234` | `1d4e83e4e4ae4ae0a4fbc81a32ee6de480fb341650d73e808088bb2800312de4` |
| `config.json` | `/Users/test/Library/Application Support/UKDataExtraction/models/gliner/gliner-small-v2.1/config.json` | `578` | `b0bb1caf90a50aa67d1085130508dfbf8646ac5a11928305e280b07a36e100ae` |
| `tokenizer_config.json` | `/Users/test/Library/Application Support/UKDataExtraction/models/gliner/gliner-small-v2.1/tokenizer_config.json` | `52` | `3f3978e0c036f2c2588cac34a6047cbb0af0b0dc1814254e291028529805496d` |
| `spm.model` | `/Users/test/Library/Application Support/UKDataExtraction/models/gliner/gliner-small-v2.1/spm.model` | `2464616` | `c679fbf93643d19aab7ee10c0b99e460bdbc02fedf34b92b05af343b4af586fd` |
| `encoder/config.json` | `/Users/test/Library/Application Support/UKDataExtraction/models/gliner/gliner-small-v2.1/encoder/config.json` | `578` | `b0bb1caf90a50aa67d1085130508dfbf8646ac5a11928305e280b07a36e100ae` |

## Notes

- Files were downloaded with `curl -fL -C - --retry 3`.
- Directory used: `/Users/test/Library/Application Support/UKDataExtraction/models/gliner/gliner-small-v2.1`.
- Runtime loads GLiNER locally and rewrites runtime config in-memory to point `model_name` at local `encoder/config.json`, preventing external fetches.
