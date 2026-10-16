# Local English and Polish transcription: model research

Research date: 2026-10-16. Status: recommendation for an implementation spike; no models were downloaded and no inference was benchmarked. Hardware target, taken from the user's screenshot: Apple M5 Pro, 64 GB unified memory, macOS Tahoe 26.6.2. These are user-provided specifications, not an independently inspected runtime.

## Recommendation

Use **Whisper large-v3-turbo through `mlx-whisper`** for the first ASR implementation, with **`pyannote/speaker-diarization-community-1` on CPU** for speaker diarization. Offer **Whisper large-v3** as a quality profile after the initial comparison on the user's recordings. Keep LM Studio outside the transcription dependency chain. This is an engineering recommendation based on documented platform support and integration complexity, not a claim that this pair wins every Polish benchmark.

Provide transcription and diarization as separate adapters. Run them sequentially in one worker initially. Preserve word timestamps and both regular and exclusive diarization turns; combine them into editable speaker-labelled transcript segments. Speaker labels identify recurring voices within one recording; they do not identify real people or link identities across files.

## LM Studio: verified constraint

LM Studio's documentation describes llama.cpp and MLX **LLM** runtimes. Its documented OpenAI-compatible endpoints cover responses, chat, completions, embeddings, decisions, and model listing; `/v1/audio/transcriptions` is absent. Its dedicated Transcribe page currently advertises a forthcoming product and notification list. Therefore there is no documented production ASR integration on which this MVP should rely. This is a conclusion from published documentation, not a probe of the installed application's private capabilities. [LM Studio app documentation](https://lmstudio.ai/docs/app), [supported endpoints](https://lmstudio.ai/docs/developer/openai-compat), [Transcribe announcement](https://lmstudio.ai/transcribe).

The generic “Local Apps: LM Studio” entry on a Hugging Face MLX model page is not evidence that LM Studio's inference runtime understands that audio architecture. Model format compatibility alone does not establish ASR support. The application should download and load audio models through its own setup flow. A later optional LM Studio integration could summarize completed transcripts, but is outside the first iteration.

## Runtime comparison

| Runtime | Relevant documented capability | MVP decision |
| --- | --- | --- |
| `mlx-whisper` | Python API, local model directories or Hugging Face repositories, word timestamps, FFmpeg dependency. [Project documentation](https://github.com/ml-explore/mlx-examples/blob/main/whisper/README.md) | Default: smallest Python integration seam for this Mac. |
| `whisper.cpp` | Native C/C++; Apple Silicon support through Metal, Accelerate and optional Core ML; CPU mode and quantized models. [Project documentation](https://github.com/ggml-org/whisper.cpp) | Preferred alternative if MLX compatibility or quality fails the spike. A CLI subprocess also gives a straightforward cancellation boundary. |
| `faster-whisper` / CTranslate2 | CPU inference and NVIDIA CUDA GPU inference; CTranslate2 documents ARM64 CPU support and NVIDIA GPU support. Its published speed comparisons use NVIDIA/Intel hardware. [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [hardware support](https://opennmt.net/CTranslate2/hardware_support.html) | Not the default Apple GPU engine. Do not pass `device="mps"` expecting Metal acceleration. CPU compatibility fallback only if required. |
| WhisperX | Adds forced alignment and diarization around faster-whisper; needs language-specific alignment models and explicitly documents overlap/alignment limitations. [Project documentation](https://github.com/m-bain/whisperX) | Defer the complete pipeline; avoid adding its dependencies merely to obtain speaker labels. |

MLX itself is an Apple machine-learning framework with unified memory and CPU/GPU devices. This supports choosing it for Apple Silicon; it does not establish M5-specific throughput. [MLX project](https://github.com/ml-explore/mlx/blob/main/README.md).

## Exact models, availability and license metadata

All linked model cards were accessible during research. Access to a public card does not prove that gated weight downloads have been authorized.

| Purpose | Exact identifier / artifact | License shown by the linked source | Download notes |
| --- | --- | --- | --- |
| ASR default, upstream | [`openai/whisper-large-v3-turbo`](https://huggingface.co/openai/whisper-large-v3-turbo) | MIT | Multilingual, 809M parameters; prunes decoder depth from 32 to 4, trading some accuracy for speed. |
| ASR default, MLX conversion | [`mlx-community/whisper-large-v3-turbo`](https://huggingface.co/mlx-community/whisper-large-v3-turbo) | **No license field on current card**; upstream turbo card says MIT | Existing pre-converted `mlx-whisper` candidate; file listing reports approximately 1.61 GB. Record upstream provenance rather than inventing conversion license metadata. |
| ASR quality, upstream | [`openai/whisper-large-v3`](https://huggingface.co/openai/whisper-large-v3) | Apache-2.0 on current card | Multilingual full-size checkpoint. |
| ASR quality, MLX conversion | [`mlx-community/whisper-large-v3-mlx`](https://huggingface.co/mlx-community/whisper-large-v3-mlx) | MIT on current conversion card | Card explicitly provides `mlx_whisper.transcribe` usage. Preserve conversion and upstream notices; do not silently flatten differing metadata. |
| Diarization | [`pyannote/speaker-diarization-community-1`](https://huggingface.co/pyannote/speaker-diarization-community-1) | CC-BY-4.0 | Gated: Hugging Face account, acceptance of conditions including contact-information sharing, and access token for initial download. |
| Native ASR alternative | [`ggerganov/whisper.cpp`](https://huggingface.co/ggerganov/whisper.cpp): `ggml-large-v3-turbo.bin` or `ggml-large-v3.bin` | MIT on conversion repository card | Use the whisper.cpp download helper and an explicit model file. These are whisper.cpp GGML artifacts, not an arbitrary llama.cpp GGUF model. |
| Optional Polish alignment | [`jonatasgrosman/wav2vec2-large-xlsr-53-polish`](https://huggingface.co/jonatasgrosman/wav2vec2-large-xlsr-53-polish) | Apache-2.0 | Additional model needed only if adopting WhisperX-style forced alignment. |

The MLX turbo listing and converter are separate evidence: [actual files](https://huggingface.co/mlx-community/whisper-large-v3-turbo/tree/main), [maintained conversion script](https://github.com/ml-explore/mlx-examples/blob/main/whisper/convert.py). If reproducible provenance is preferable to the existing conversion, convert the official turbo checkpoint with the maintained script and keep its license notice alongside the resulting local model. This is an available fallback path, not a conversion already tested here.

Whisper's tokenizer explicitly includes English (`en`) and Polish (`pl`). Use multilingual checkpoints; an `.en` checkpoint would exclude the Polish requirement. [Tokenizer source](https://github.com/openai/whisper/blob/main/whisper/tokenizer.py).

## Diarization and timestamp decisions

Community-1 defaults to CPU, supports an optional known speaker count or bounds, and returns exclusive diarization for easier reconciliation with ASR timestamps. Its card documents 16 kHz mono processing and local-directory loading for offline inference. The documented GPU example uses CUDA; Apple MPS acceleration must be treated as an experiment, not a setup promise. [Community-1 card](https://huggingface.co/pyannote/speaker-diarization-community-1).

Whisper.cpp's experimental tinydiarize example uses `small.en-tdrz` and marks speaker changes. Those change markers do not provide recurring speaker identities and the illustrated model is English-only; it does not satisfy the PL/EN multi-speaker requirement. [whisper.cpp speaker segmentation](https://github.com/ggml-org/whisper.cpp#speaker-segmentation-via-tinydiarize-experimental).

WhisperX's current alignment source maps Polish to `jonatasgrosman/wav2vec2-large-xlsr-53-polish` and English to torchaudio `WAV2VEC2_ASR_BASE_960H`. Mixed-language alignment therefore needs an explicit policy and potentially multiple loaded aligners. [Alignment source](https://github.com/m-bain/whisperX/blob/main/whisperx/alignment.py).

Proposed MVP merge policy: assign each word to the exclusive speaker interval with maximum temporal overlap; group consecutive words by speaker; retain missing timestamps and uncertain attribution explicitly rather than dropping text. Keep raw overlapping turns separately because a single exclusive label cannot faithfully describe simultaneous speech. This is application design, not a documented library guarantee.

Whisper can generate unspoken text and repetitions, especially on unsuitable input. Neither a larger model nor diarization removes that limitation. [Turbo limitations](https://huggingface.co/openai/whisper-large-v3-turbo#performance-and-limitations). Silence, background music, cross-talk and short interjections must be in the acceptance fixtures. No automatic cleanup LLM should rewrite the transcript in this iteration.

## Newer alternatives worth retaining in the benchmark backlog

- [`nvidia/parakeet-tdt-0.6b-v3`](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3): 600M parameters, 25 European languages including PL/EN, word/segment timestamps, CC-BY-4.0. A credible challenger. The card's long-audio capacity examples and hardware guidance are not M5 measurements. Verify a Mac runtime separately before proposing replacement.
- [`Qwen/Qwen3-ASR-1.7B`](https://huggingface.co/Qwen/Qwen3-ASR-1.7B): Apache-2.0, includes Polish and English. The accompanying Qwen3 forced aligner's listed languages exclude Polish, so ASR language coverage does not establish Polish alignment support. Its first-party examples do not establish a tested M5 deployment for this project.

Neither model alone establishes speaker diarization for this UI. Switching ASR should preserve the diarization adapter and normalized transcript contract.

## Setup and offline preflight

These are proposed implementation requirements, not commands executed during research.

1. Use a native arm64 Python environment, initially Python 3.11 as an implementation baseline. Resolve and lock a mutually compatible MLX/PyTorch/torchaudio/torchcodec set. Current pyannote development metadata requires Python >=3.10 and PyTorch/torchaudio >=2.8; released package versions still need verification during the spike. [Dependency metadata](https://github.com/pyannote/pyannote-audio/blob/develop/pyproject.toml).
2. Check `ffmpeg` and `ffprobe`, model directory readability, available disk space, and short real inference before displaying “ready.” Pyannote documents FFmpeg for torchcodec; do not assume successful Python imports prove audio decoding works. [pyannote setup](https://github.com/pyannote/pyannote-audio#community-1-open-source-speaker-diarization).
3. Separate online setup from offline processing. Explicitly download pinned model snapshots and every dependent artifact. Create a manifest containing repository ID, resolved revision, filename hashes, runtime version, and license/provenance links. Never commit weights, credentials, or user recordings.
4. Have the user personally accept the gated model's conditions and supply a narrowly scoped download token. Keep it in a local environment/credential store and redact it from diagnostics. Do not claim setup can be entirely unattended before those account steps.
5. Load ASR and diarization from local paths. Set `HF_HUB_OFFLINE=1` and `HF_HUB_DISABLE_TELEMETRY=1` before library imports. Hugging Face documents that cached loading without offline mode can still check the network. [Hub environment variables](https://huggingface.co/docs/huggingface_hub/en/package_reference/environment_variables).
6. Set `PYANNOTE_METRICS_ENABLED=0` explicitly; optional pyannote telemetry otherwise depends on configuration. [Telemetry documentation](https://github.com/pyannote/pyannote-audio#telemetry). Verify a full job with networking disabled, including process startup and export; environment flags alone do not prove all transitive components remain offline.
7. Preserve original audio and derive a 16 kHz mono working file, keeping the original timeline. When later adding VAD or chunking, map every timestamp back to original time. Keep channels available for future separated-channel handling.

Budget approximately 15 GB of free setup space as a conservative project allowance for both ASR profiles, diarization, cache duplication and runtime dependencies; this is not a measured package size. Budget user media separately: a one-hour 16 kHz mono PCM16 working file is about 115 MB. Avoid loading every model/profile simultaneously.

## Benchmark and release gate

Run this on the target Mac before claiming performance or fixing the final default:

| Fixture | Purpose |
| --- | --- |
| 5–10 minutes of clear Polish speech with manually checked text | Polish diacritics, names, inflection, timestamps. |
| 5–10 minutes of clear English speech | Accents, specialist vocabulary, names. |
| 10–20 minutes of conversation with 2–4 annotated speakers | Recurring labels, count estimation, short turns, overlap. |
| Mixed Polish/English recording | Compare auto language and explicit-language behavior; no promise of per-word language detection. |
| Silence, music, low volume and noise | Hallucinations, false speech, graceful empty result. |
| One 60-minute recording | Memory, cancellation, restart recovery, sustained processing time. |

Compare MLX turbo and MLX large-v3 on identical normalized input and decoding settings where possible. Test whisper.cpp turbo if the MLX path fails or timing/quality is inadequate; avoid building a multi-runtime selection UI before there is evidence it is needed.

Record cold-start and warm inference separately, ASR time, diarization time, total wall time, real-time factor (`processing_seconds / audio_seconds`), peak resident memory and model revisions. Report Polish and English WER/CER separately with disclosed normalization; inspect proper names and punctuation manually. Report diarization error against a reference with overlap/scoring policy and inspect label stability. Measure timestamp errors on manually marked turns; do not infer timing accuracy from WER.

Suggested engineering target: end-to-end real-time factor <=1 on a representative 30–60-minute meeting, no process crash, no network use after setup, and recoverable partial ASR if diarization fails. This is a provisional target, not a measured capability. A diarization failure must remain visible; a transcript without speaker labels is a degraded result and does not satisfy the multi-speaker acceptance gate. Establish quality thresholds from the first annotated fixtures rather than presenting arbitrary percentages as proven product accuracy.

If diarization is too slow on CPU, profile it separately before trying MPS or replacing the model. The 64 GB memory configuration makes full-size Whisper plausible as a local candidate; it does not establish speed, thermal behavior, dependency compatibility or speaker quality on this exact hardware.
