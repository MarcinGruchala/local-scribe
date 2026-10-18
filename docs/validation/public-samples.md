# Public human-speech compatibility samples

Date: 2026-10-16. These short samples support actual English/Polish inference compatibility checks. They do **not** satisfy the representative 5–10 minute, two-speaker, mixed-language, overlap, or 30-minute performance release gates.

## Source and permission

The samples come from Google's [FLEURS dataset](https://huggingface.co/datasets/google/fleurs), licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), at repository revision `70bb2e84b976b7e960aa89f1c648e09c59f894dd`. Attribution: *FLEURS: Few-shot Learning Evaluation of Universal Representations of Speech*, Google.

Each sample is an unmodified WAV from that revision's language-specific test archive. The reference files preserve the dataset-provided original and normalized text, archive/manifest source URLs, revision, sample ID, license, attribution, and SHA-256 hashes. Their speaker-turn arrays are empty because these samples have no manually checked speaker boundaries. Dataset text is useful for a short ASR comparison; it must not be presented as a corrected long-form release reference.

## Reproduction

```sh
.venv/bin/python scripts/fetch-fleurs-samples.py --output /private/tmp/localscribe-validation
```

The script downloads only fixed, public FLEURS URLs. It performs no authentication, token lookup, or gated-conditions acceptance. It restricts redirects to explicitly approved Hugging Face/CDN hosts, bounds manifest/audio/archive reads, and forbids an output directory inside the repository. It streams each official archive only until its first WAV matching the test manifest, then closes the connection instead of downloading the complete hundreds-of-megabytes archive. Files are written with private permissions. Logs contain aggregate metadata and hashes, without reference text or signed redirect URLs.

The dataset viewer `/rows` returned HTTP 500 and `/first-rows` returned HTTP 501 during this run. The official pinned TSV manifests and audio archives remained available, so the script uses them directly. FLEURS manifests contain literal quotation marks in text and are parsed as literal tab-separated fields.

## Recorded download evidence

| Language | Config | Sample ID | Original filename | Duration | Audio bytes | Reference characters |
| --- | --- | --- | --- | --- | --- | --- |
| Polish | `pl_pl` | `1829` | `10003602174340488201.wav` | 12.12 s | 775,738 | 162 |
| English | `en_us` | `1904` | `1003119935936341070.wav` | 10.56 s | 675,898 | 102 |

Actual FFprobe checks confirmed both files are mono, 16 kHz, `pcm_f32le` WAV. Their measured durations match the manifest sample counts divided by 16,000. The English archive transfer was 491,520 bytes, rather than the full 289,851,356-byte archive.

| File | SHA-256 |
| --- | --- |
| `fleurs-pl.wav` | `c63af76a5badf2dbce622732e6ca8b92a38591a7e2e8cc4e6ce6035aae299702` |
| `fleurs-en.wav` | `33aca50159ec2e3cbcc894eb26faa916d6badb1b49fb75994973561540a7f012` |
| `fleurs-pl.reference.json` | `0bb0cad54d181a13d4de8224d4255ae7e4f94f3fcd48156f8d593f65fb245ba0` |
| `fleurs-en.reference.json` | `74fca4817fbc90f3b73fd72888fe3a9d7504ef3ee9360d0fc6a2070831e79d4b` |

All four files remain outside Git at `/private/tmp/localscribe-validation/`. This record contains no transcript or reference text. Download and decode checks establish input availability; model inference results are recorded separately by the coordinator, with heavyweight jobs run sequentially.
