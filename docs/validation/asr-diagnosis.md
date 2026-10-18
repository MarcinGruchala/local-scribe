# Natural Polish ASR diagnosis

Status: **the 15% WER release gate remains failed**. These controlled diagnostic
comparisons do not select an accepted release profile or replace the remaining
English, diarization, performance, and challenge gates.

## Fixed input and feedback loop

All comparisons use the same predeclared, continuous SpokesBiz LUZ window
0–582.59 seconds and the same human-corrected reference, independently prepared
before predictions. The fixed normalization yields 1,929 reference words.
The source window, scoring normalization, acceptance threshold, and sample
classification were not changed after scoring. No reference-derived prompt,
vocabulary hint, transcript repair, or threshold search was used.

Public clip SHA-256:
`4051bdbfe395576df7946b6eed84c52b3903ba723a7cad2ebc5e79e47671d997`.
Reference SHA-256:
`d09a831f8f5f6389066cfe5f5a3404b475edf39194e7806f44033b8ea6cb586b`.
See [source provenance and licensing](../research/reference-corpora.md).

Re-scoring both stored baseline JSON exports twice reproduced exactly 410 and
390 errors. The diagnostic assertion `wordErrorRate <= 0.15` failed with exit 1
both times. This is a fast, deterministic feedback loop over actual inference
outputs. The full fixed sample is retained because minimizing or selecting a
different window would change the release evaluation.

Normalized original model text, concatenated raw model-segment text, and display
text are identical for both baselines. Application assembly did not cause these
word omissions. Baseline deletions occur throughout all ten source-time bins and
affect both speakers. Fast has 118 contiguous deletion runs, maximum 7 words;
Quality has 107, maximum 14. Of 54 reference words in source turns containing at
most three words, Fast deletes 30 and Quality deletes 36. This is evidence of
particular difficulty retaining short conversational turns, not proof of the
cause of each omission. Source times and speaker annotations remain automatically
realigned diagnostics, not hand-audited gold labels.

## Controlled MLX comparisons

Each new trial ran in a fresh child process with cached, integrity-checked local
model snapshots, forced Polish `task=transcribe`, OS external-network denial via
`scripts/offline.sb`, and an empty `HF_HOME`. Diarization was disabled. Processes
exited and MLX caches were released between runs. These are ASR-only measurements;
the new probes did not sample system memory pressure and cannot pass that gate.
Peak RSS includes the process, while the ASR timer surrounds the MLX call.

| Profile / change from baseline | S | D | I | Errors / WER | ASR seconds | Peak RSS bytes |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| Fast baseline | 143 | 255 | 12 | 410 / 21.2545% | 16.543 | 2201632768 |
| Fast: previous-text context enabled only | 134 | 193 | 19 | 346 / 17.9368% | 19.753 | 2165489664 |
| Fast: standard temperature fallback only | 143 | 255 | 12 | 410 / 21.2545% | 16.914 | 2190082048 |
| Fast: word timestamps disabled only, diagnostic | 154 | 223 | 13 | 390 / 20.2177% | 12.829 | 1909915648 |
| Quality baseline | 146 | 224 | 20 | 390 / 20.2177% | 56.427 | 3824828416 |
| Quality: previous-text context enabled only | 264 | 1011 | 8 | 1283 / 66.5111% | 48.985 | 3953950720 |
| Quality: standard context and temperature fallback | 152 | 169 | 39 | 360 / 18.6625% | 64.652 | 3981443072 |

All five new trials captured zero Python warning categories. That does not imply
valid product alignment. Fast context-only produced two empty zero-duration model
segments; Quality context-only produced 141, and Quality standard context/fallback
produced three. Current strict assembly rejects these intervals. Fast fallback
assembles with `alignment_fallback`, preserving original text. The timestamp-free
diagnostic also assembles with that warning, but has zero word timestamps and
cannot establish the required word-alignment behavior.

The baseline explicitly sets `temperature=0.0`,
`condition_on_previous_text=False`, and `word_timestamps=True`. The isolated
context trial changes only the context flag. The fallback trial changes only
temperature to the installed MLX default `(0, 0.2, 0.4, 0.6, 0.8, 1.0)`. The
timestamp-free trial changes only the word-timestamp flag. The final Quality
trial enables standard context plus standard temperature fallback, retaining
word timestamps and setting the sampling seed to zero before inference.
Earlier trials used greedy temperature zero throughout; sampling did not occur.

No saved baseline or Fast context segment crosses the standard compression
ratio 2.4 or average-log-probability -1.0 fallback thresholds. The Fast fallback
trial consequently remains at temperature zero and reproduces baseline text.
A combined Fast context/fallback trial was omitted as redundant: the isolated
context run likewise has no fallback triggers.

Quality context-only instead enters a repetition failure: 301 nonempty segments
contain only 60 distinct texts, with one identical segment repeated 240 times.
Its maximum compression ratio is 9.3125, and 379 segments carry compression-based
fallback triggers despite acceptable average log probability. Standard fallback
uses temperatures 0 and 0.2 and breaks that failure loop, but still misses the
15% target. Context alone is therefore not a justified production change.
Upstream documents the context/repetition tradeoff and default fallback in
[MLX transcribe](https://github.com/ml-explore/mlx-examples/blob/main/whisper/mlx_whisper/transcribe.py).

Installed `mlx-whisper` is 0.4.3. Its decoder explicitly raises
`NotImplementedError` for `beam_size`; `best_of` provides sampling trajectories
only at positive temperature and is incompatible with greedy temperature zero.
The same restrictions remain visible in the current primary
[MLX decoder source](https://github.com/ml-explore/mlx-examples/blob/main/whisper/mlx_whisper/decoding.py).
Installed file SHA-256 values are
`fae5828b2d80760e6dbcd5a51d7704769dca67cad5d559085d0a08d40964e616`
for `decoding.py` and
`21f015e0d56c5e6194d07d86d772730940fff52d8f06d55838ae92ebccc24fbb`
for `transcribe.py`.

## whisper.cpp comparison

The accepted first alternative is whisper.cpp with Metal. The official current
[release v1.9.5](https://github.com/ggml-org/whisper.cpp/releases/tag/v1.9.5)
pins commit `d1be6fde11ac6e0407606b4e42fe72d34add8037`. Its
[build configuration](https://github.com/ggml-org/whisper.cpp/blob/v1.9.5/ggml/CMakeLists.txt)
enables Metal by default on Apple platforms. The diagnostic requested Metal
explicitly and recorded the backend actually initialized.

The official downloader uses `ggerganov/whisper.cpp`. Public repository revision
`5359861c739e955e79d9a303bcbc70fb988958b1` is ungated. Bounded reads of the two
immutable LFS pointer files, without credentials or redirects, establish:

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `ggml-large-v3-turbo.bin` | 1624555275 | `1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69` |
| `ggml-large-v3.bin` | 3095033483 | `64d182b440b98d5203c4f9bd541544d84c605196c4f7b845dfa11fb23594d1e2` |

Primary pointer sources:
[Turbo](https://huggingface.co/ggerganov/whisper.cpp/raw/5359861c739e955e79d9a303bcbc70fb988958b1/ggml-large-v3-turbo.bin),
[large-v3](https://huggingface.co/ggerganov/whisper.cpp/raw/5359861c739e955e79d9a303bcbc70fb988958b1/ggml-large-v3.bin).
MLX snapshots cannot be supplied directly to whisper.cpp; the separate GGML files
must be explicitly provisioned and verified outside Git.

The completed trial uses unquantized Turbo, the identical complete Polish
clip, forced Polish, beam size 5, default decoder thresholds and fallback, no
prompt, and full JSON token output. Following the user's later request to focus
on practical use, this comparison is limited to Turbo; no additional large-v3
download or broader decoder search will follow automatically. The trial used
OS network denial, a fresh process, an empty `HF_HOME`, and the existing
pressure-sampling protocol.

The pinned source archive has 9,631,456 bytes and SHA-256
`645445da884df6dbd52b30f82d7be7c01d1767c938714e477e786b88d529e9f4`.
Compilation completed with external networking denied, Metal and embedded Metal
libraries enabled, static libraries, Release mode, and the upstream
`WHISPER_BUILD_IS_DEV=OFF` release flag. The resulting CLI reports version 1.9.5;
binary SHA-256 is
`2b2faafebfaa9c103ddc6de2f41707c35ff5220377b1e290bf89ff4fdc821922`.
Model acquisition completed in 592.970 seconds; exact size and SHA-256 match the
immutable LFS pointer. Runtime logs verify `MTL0 (Apple M5 Pro)`, GPU backend
initialization, and embedded Metal. No large-v3 weights were downloaded.

| Trial | S | D | I | Errors / WER | CLI process wall | Peak CLI RSS |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| Turbo / Metal / beam size 5 | 136 | 241 | 17 | 394 / 20.4251% | 21.268 s | 2137702400 bytes |

**This comparison also fails the unchanged 15% WER target.** The process timer
includes model loading, transcription, token timestamps, and JSON output. It
does not include model acquisition or compilation, and it does not measure the
full diarization pipeline. All 13 pressure observations were normal (raw value
1), with no unknown/unavailable observations, a maximum sampling gap of 2.010
seconds, and no sampled warning/critical interval. This short run cannot pass
the representative 30/60-minute performance or stability gates.

The CLI completed successfully and wrote 483 segments and 3,611 token rows.
Native JSON SHA-256:
`a393dd3505095357dbd98a58406492a5fd60353bccc2ed7d32e0106027089e6c`.
One nonempty segment containing one normalized word has an instantaneous
64.540–64.540 second interval. Strict application assembly would reject it;
the comparison does not establish production timestamp compatibility. No word
alignment, diarization, or production integration pass is claimed.

The diagnostic Python reporter initially searched for a `METAL` system-info
label, whereas this build reports `MTL`. That post-inference check failed after
the successful CLI call, parsing, scoring, and raw result persistence. Its
original helper exit code 1 and original failed wrapper report remain intact.
A separate corrected report records the actual successful inference, verified
MTL initialization evidence, measured score, and the reporter correction. No
inference was repeated and no native transcript/token output was edited. The
helper predicate was corrected for reproducibility; this is a reporting fix,
not a decoder or application change.

The [CLI](https://github.com/ggml-org/whisper.cpp/blob/v1.9.5/examples/cli/cli.cpp)
implements beam search and full JSON token timestamps (`-bs 5`, `-ojf`). Tokens
are not necessarily words; UTF-8 fragments and punctuation need faithful
assembly. `-ml 1`/`-sow` offer experimental word-sized segments, requiring
independent timestamp/text checks. DTW presets include `large.v3` and
`large.v3.turbo`. The
[runtime source](https://github.com/ggml-org/whisper.cpp/blob/v1.9.5/src/whisper.cpp)
disables DTW when flash attention is enabled, so a later DTW trial must explicitly
use `-nfa`. No alignment claim follows merely from the presence of token times.

Raw outputs, exact command metadata, acquisition manifests, and aggregate metrics
are retained in the external local validation archive. No corpus text, weights,
credentials, or private recording metadata is committed with this report.
