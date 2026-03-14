# kraken pull evidence

Generated: 2026-03-14 00:04:12 UTC

## Container image

- Pulled base reference:
  `python:3.11-slim@sha256:d64a1009c676551d50bdd2a0f9a4a5f63423a5f070d9284e00e4cba788953f4b`
- Verified platform: `linux/arm64`
- Runtime image built from base: `ukda/kraken:arm64`
- Built runtime image id: `sha256:a070fa8f1fbaa45e467cbc347adb3fa4d31d35b24f8a06333a9de86e1e6917e9`

## Artifact source

- OCR model DOI record:
  [10.5281/zenodo.10592716](https://zenodo.org/records/10592716)
- Segmentation model DOI record:
  [10.5281/zenodo.14602569](https://zenodo.org/records/14602569)
- Download URLs:
  - [catmus-print-fondue-large.mlmodel](https://zenodo.org/records/10592716/files/catmus-print-fondue-large.mlmodel?download=1)
  - [blla.mlmodel](https://zenodo.org/records/14602569/files/blla.mlmodel?download=1)

## Downloaded files

| File | Absolute path | Size (bytes) | SHA-256 |
| --- | --- | ---: | --- |
| `catmus-print-fondue-large.mlmodel` | `/Users/test/Library/Application Support/UKDataExtraction/models/kraken/default/catmus-print-fondue-large.mlmodel` | `22874456` | `1ed39e732b26ccdd0f14b9abd3edc66c4b04a02e3d827d7f9e96a7fe7b585b64` |
| `blla.mlmodel` | `/Users/test/Library/Application Support/UKDataExtraction/models/kraken/default/blla.mlmodel` | `5047020` | `77a638a83c9e535620827a09e410ed36391e9e8e8126d5796a0f15b978186056` |

## Notes

- Files were downloaded with `curl -fL -C - --retry 3`.
- Directory used: `/Users/test/Library/Application Support/UKDataExtraction/models/kraken/default`.
- Pipeline used by API: `segment -bl -i blla.mlmodel` + `ocr -m catmus-print-fondue-large.mlmodel`.
