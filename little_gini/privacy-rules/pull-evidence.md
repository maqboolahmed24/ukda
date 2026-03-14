# privacy-rules pull evidence

Generated: 2026-03-13 23:47:16 UTC

## Container image

- Pulled base reference:
  `python:3.11-slim@sha256:d64a1009c676551d50bdd2a0f9a4a5f63423a5f070d9284e00e4cba788953f4b`
- Verified platform: `linux/arm64`
- Runtime image built from base: `ukda/privacy-rules:arm64`
- Built runtime image id: `sha256:56b7f2b112e3b311d3bde0d9b4a50ea2ad22aac8ef57650c4f23bbc306a195a4`

## Runtime dependency source

- spaCy model wheel:
  [en_core_web_sm-3.8.0-py3-none-any.whl](https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl)

## Downloaded runtime assets

| File | Absolute path | Size (bytes) | SHA-256 |
| --- | --- | ---: | --- |
| `en_core_web_sm-3.8.0-py3-none-any.whl` | `/Users/test/Library/Application Support/UKDataExtraction/models/presidio/default/en_core_web_sm-3.8.0-py3-none-any.whl` | `12806118` | `1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85` |
| `en_core_web_sm/en_core_web_sm-3.8.0/config.cfg` | `/Users/test/Library/Application Support/UKDataExtraction/models/presidio/default/en_core_web_sm/en_core_web_sm-3.8.0/config.cfg` | `5527` | `65c545ca2da5bd4b87b22d4917318605360b37dee6ed6b18516a036f87319f79` |
| `en_core_web_sm/en_core_web_sm-3.8.0/meta.json` | `/Users/test/Library/Application Support/UKDataExtraction/models/presidio/default/en_core_web_sm/en_core_web_sm-3.8.0/meta.json` | `10106` | `7456349002fa8cf31111051bd37fdbea67a1b7f7a0a60ce235466f98a6758125` |
| `en_core_web_sm/en_core_web_sm-3.8.0/tokenizer` | `/Users/test/Library/Application Support/UKDataExtraction/models/presidio/default/en_core_web_sm/en_core_web_sm-3.8.0/tokenizer` | `77066` | `b014e8bba4958b120af2d0c1c63eabb7c00379f2bacaf10df7c5325efd2ea467` |
| `en_core_web_sm/en_core_web_sm-3.8.0/vocab/strings.json` | `/Users/test/Library/Application Support/UKDataExtraction/models/presidio/default/en_core_web_sm/en_core_web_sm-3.8.0/vocab/strings.json` | `1103983` | `b1966d1f07a05b68576df07f43f40203b4e11124ad82cc839e8312ad8d7fdae7` |
| `en_core_web_sm/en_core_web_sm-3.8.0/vocab/lookups.bin` | `/Users/test/Library/Application Support/UKDataExtraction/models/presidio/default/en_core_web_sm/en_core_web_sm-3.8.0/vocab/lookups.bin` | `70040` | `fce9c883c56165f29573cc938c2a1c9d417ac61bd8f56b671dd5f7996de70682` |

## Notes

- Runtime assets are persisted under `MODEL_ARTIFACT_ROOT/presidio/default`.
- The service loads spaCy directly from this persistent model directory at startup.
- Analyzer path is local-only and does not require external API calls.
