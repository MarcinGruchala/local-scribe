# Public conversation references: feasibility and access

Checked on 2026-10-16 against primary project pages, source annotations, and bounded archive metadata. This is source research, not a passed quality gate. No corpus recording, transcript text, access token, or model asset is tracked in Git.

## Polish: LUNA.PL

The [IPI PAN project page](https://zil.ipipan.waw.pl/LUNA) explicitly offers the human-human LUNA.PL corpus under the **2-clause BSD license**, separately from its Wizard-of-Oz human-computer corpus. Its download and archive listing are publicly accessible without an account or a license-acceptance form. The collection contains real telephone calls to the Warsaw Transport Authority, with manual transcription; the [authors' corpus description](https://aclanthology.org/L08-1512/) reports 500 human-human calls totaling approximately 670 minutes.

- Official archive: `https://zil.ipipan.waw.pl/LUNA?action=AttachFile&do=get&target=LUNA.PL.zip`
- [Browsable archive index](https://zil.ipipan.waw.pl/LUNA?action=AttachFile&do=view&target=LUNA.PL.zip)
- [Official annotation protocol](https://zil.ipipan.waw.pl/LUNA?action=AttachFile&do=get&target=LUNA_annotation.pdf)
- Archive HTTP size: **1,171,789,169 bytes**; server `Last-Modified`: **2014-12-29 13:15:48 GMT**.

The annotation protocol specifies manually segmented, timed speaker turns and human transcription based on listening. The original `.trs` format is Transcriber XML with `Turn` speaker/start/end attributes and `Sync`, `Who`, and `Event` elements. Separate word, turn, and semantic XML files are also present. The protocol transcribes the dominant voice during overlap, replaces nonlexical fillers with event annotations, and annotates pauses longer than one second. This is independent human annotation, but its conventions do not automatically provide complete overlap or fine-grained speech/non-speech ground truth for the release scorer.

### Bounded inspection and result

The server ignores HTTP byte-range requests. Only a **67,108,864-byte prefix** was downloaded and parsed through ZIP local headers, outside Git in `/private/tmp/localscribe-reference-research/`. Its SHA-256 is:

```text
7dafbf407fabf1f0f1ca25b736adcf596db41ca9ac6b5374c63ba53caa4058f7
```

That prefix contains 30 complete human-human annotations and WAV files. Their actual WAV headers show **16,000 Hz, mono, 16-bit PCM**. The complete official ZIP index lists all 500 human-human WAV filenames and byte sizes. Assuming the encoding verified in those first 30 files, only one indexed file reaches five minutes; the other **470 headers were not downloaded or verified**. Byte-size-derived lengths for those files remain inferences, not measured durations.

The longer inspected recording is `LUNA.PL/CZYJEDZIEPRZEZ/DOBRAJAKOSC/F/1_2007-04-13_11_03_56/1_2007-04-13_11_03_56.wav`:

| Property | Verified value |
| --- | --- |
| Actual WAV duration | 368.9769375 seconds |
| WAV size | 11,807,306 bytes |
| WAV SHA-256 | `5b45aed361b4356bb9f271c3231b90d1cd8786f1c2cc1e4bb74669df2a8ed273` |
| TRS SHA-256 | `96e151a7262845343a23beaa52881d786e9721e2ccdc4a3e921af9892a273e5b` |
| Anonymous speaker IDs | `spk1`, `spk2` |
| Annotation limitation | 44.711–364.827 seconds is an otherwise empty turn marked `no annotated` |

The 320.116-second unannotated interval prevents this recording from supplying a complete, representative 5–10 minute reference. Its actual content was not independently listened to or classified; it must not be relabelled as gold silence or music. Other inspected calls are shorter than five minutes. **No verified LUNA.PL candidate satisfies the accepted Polish quality gate.** Do not concatenate unrelated calls, repeat them, or count the unannotated interval as proof of sustained conversational quality. A full archive download is not justified by the candidates established here.

## Polish: SpokesBiz and Spokes

[SpokesBiz's official page](https://docs.pelcra.pl/doku.php?id=spokesbiz) describes conversational recordings with subsequently manually corrected text, speaker IDs, and segment/word timestamps. Its **CC BY-NC-ND** license and required attribution are documented there. Access to the full corpus requires the [author's access form](https://forms.office.com/e/cpn88mcFC6); completing that form or accepting another dataset's conditions is a user action.

The authors separately link a [public sample ZIP](https://drive.google.com/file/d/1n7pgueKAylKwExzecXhdtauTI6rMzFug/view?usp=sharing). Its unauthenticated viewer exposes a download button and reports **761,372,269 bytes**. File ID: `1n7pgueKAylKwExzecXhdtauTI6rMzFug`. The public download endpoint supports HTTP ranges without credentials, cookies, an account, or a corpus-access form. A technical large-file virus-scan warning is separate from license/access acceptance; no account or dataset conditions were accepted during the bounded inspection.

Only the final 65,536 bytes, the 3,477,554-byte compressed CSV entry, and 65,536-byte headers of seven WAV entries were initially fetched. The suffix SHA-256 is `b54ae493af2533857c5e3e82076ba519f4fbd8227a9b1efad3cfdcb75a926a46`. Its central directory lists seven WAV recordings and `spokes_biz_rich_sample.csv`; the decoded 12,299,748-byte CSV contains 3,070 segment rows and has SHA-256 `c5b034dfe5a2345560dfef4a4f128fa27b5528cfe9092856ed839b05c07d1e69`. Raw annotations remain outside Git.

| Public sample recording | Actual WAV-header duration | Encoding | CSV reference content |
| --- | --- | --- | --- |
| CBIZ_LUZ_013 | 1801.3013125 seconds | 16 kHz, mono PCM16 | Informal conversation; 276 segments, 6,073 words, exactly two speaker IDs with 137/139 segments |
| CBIZ_INT_007 | 901.1840136054421 seconds | 44.1 kHz, stereo PCM16 | Formal interview; 82 segments, 2,289 words, exactly two speaker IDs with 42/40 segments |
| CBIZ_BIO_051 | 3752.384 seconds | 16 kHz, mono PCM16 | Informal interview; 275 segments, 7,564 words, exactly two speaker IDs |

The [authors' paper, section 4](https://arxiv.org/html/2312.12364), explicitly distinguishes initial automatic ASR/pyannote diarization, subsequent human text corrections, and automatic realignment of corrected utterances and words. **This supports human-corrected WER references but does not establish independently hand-audited speaker boundaries.** A disclosed contiguous 5–10 minute interval from CBIZ_LUZ_013 or CBIZ_INT_007 is a promising natural Polish candidate; an independent audit of its labels, boundaries, overlaps, and non-speech remains necessary before claiming the hand-labelled attribution gate. There must be no selection based on model-score outcomes. The full CBIZ_LUZ_013 and CBIZ_BIO_051 recordings also provide potential 30/60-minute performance inputs without repetition or concatenation.

### Acquired Polish inputs and reproducible reference

The complete LUZ and BIO WAV entries were separately range-downloaded from the public ZIP, not from the gated full corpus. Decompression lengths, WAV headers, ZIP CRC32, and SHA-256 were verified:

| Asset | SHA-256 | ZIP CRC32 |
| --- | --- | --- |
| CBIZ_LUZ_013.wav | `53009ca3f99bfdc9378cb2af03c96618c14feef2acb0a7c53ac8ab1c2f83e209` | `ff0d2e2b` |
| CBIZ_BIO_051.wav | `ccde9b5dfe8a99921b668ecebccf7d39eeff9f77e72a5e21feb8ee22d12c18bc` | `0d606a2c` |

Before any model predictions, the primary Polish WER window was fixed to **0–582.59 seconds** of LUZ: 100 whole corrected manual segments, 50 turns from each of two anonymous speakers, and 1,933 words according to corpus segment counts. The next source utterance crosses 600 seconds, so the shorter whole-utterance endpoint avoids selecting partial reference text using automatic word times. All 276 LUZ segment texts matched their reconstructed timed-word texts after the scorer's normalization; this consistency check does not independently validate alignment accuracy.

External prepared assets:

- Clip: `pl-luz-000000-582590.wav`, SHA-256 `4051bdbfe395576df7946b6eed84c52b3903ba723a7cad2ebc5e79e47671d997`.
- Reference: `pl-luz-000000-582590-reference.json`, SHA-256 `d09a831f8f5f6389066cfe5f5a3404b475edf39194e7806f44033b8ea6cb586b`.

The reference retains the corrected source segment text without word-time-based text slicing. It converts source milliseconds to seconds, records exact source hashes/segment IDs, and explicitly sets `speakerReferenceStatus` to `automatically_realigned_not_independently_audited` and `speakerAttributionGateEligible` to `false`. Speaker scoring from it is diagnostic only. The predeclared source window and text do not depend on ASR profile outputs.

The repository's explicit preparation script reproduces acquisition and the reference without models, credentials, cookies, or runtime application downloads:

```sh
.venv/bin/python scripts/public-reference.py download --asset csv --root /private/tmp/localscribe-reference-research
.venv/bin/python scripts/public-reference.py download --asset luz --root /private/tmp/localscribe-reference-research
.venv/bin/python scripts/public-reference.py download --asset bio --root /private/tmp/localscribe-reference-research
.venv/bin/python scripts/public-reference.py prepare-pl --root /private/tmp/localscribe-reference-research
```

Downloads use one fixed public file ID, bounded HTTP ranges, a Google download-host allowlist, and recorded immutable asset hashes. A changed public archive or a server ignoring Range causes a failure before a full archive download. The script refuses repository output directories. Corpus content stays outside Git; only this source record, the script, and synthetic conversion tests are tracked.

The [PELCRA BIGOS repository](https://huggingface.co/datasets/pelcra/pl-asr-pelcra-for-bigos) is gated and requests explicit acceptance/contact sharing. Existing Hugging Face model access does not grant acceptance of that separate dataset gate. The older [Spokes documentation](https://docs.pelcra.pl/doku.php?id=spokes_documentation) describes public transcription/API access, but a complete permitted continuous recording with verified reference boundaries has not been established here.

## English: Santa Barbara Corpus

The [UCSB project page](https://www.linguistics.ucsb.edu/research/santa-barbara-corpus-spoken-american-english) explicitly publishes audio, transcription, and intonation-unit timestamps under **CC BY-ND 3.0 US**. The linked source transcripts are accessible without an account:

| Recording | Official description | Direct manual transcript | Last annotated time |
| --- | --- | --- | --- |
| SBC005 | Conversation between a couple | [SBC005.trn](https://www.linguistics.ucsb.edu/sites/default/files/sitefiles/research/SBC/SBC005.trn) | 1228.06 seconds |
| SBC010 | Two-person business conversation | [SBC010.trn](https://www.linguistics.ucsb.edu/sites/default/files/sitefiles/research/SBC/SBC010.trn) | 940.54 seconds |

Official audio links: [SBC005 WAV](https://ucsb.box.com/s/0wadkhacf960exb0kc59pn4lh159pcmb), [SBC010 WAV](https://ucsb.box.com/s/pe8rkk8nmt9g8jvmgikbjk6fwggesf83). UCSB also explicitly links the [TalkBank WAV mirror](https://talkbank.org/media/CABank/SBCSAE/0wave/). These are source locations; the times above were read from annotations, not independently measured from downloaded WAV headers in this investigation.

A disclosed contiguous 5–10 minute excerpt could be a natural two-speaker English test, subject to verified audio access and alignment. TRN uses carried-forward speaker labels, overlap brackets, breaths, laughter, elongation markers, and uncertain words. Conversion must remove annotation syntax rather than score it as spoken vocabulary, and audit pauses/non-speech before treating intonation-unit intervals as reference speech. Keep derived media/references outside Git and observe the source license; publish only sanitized measurements and attribution. SBC003 is described as a three-person conversation; SBC013 is described as containing substantial overlap, making them potential challenge sources rather than evidence already run.

### Prepared English WER source window

The complete SBC005 original WAV was acquired from the official anonymous Box source: 108,320,812 bytes, SHA-256 `cc65cf2abb89036fcbd57da0691ded3c1a062721c99bc4bda538cd1cba55a7fb`. Its independently published TRN has SHA-256 `3c537a69be481e8e96add188437211c4c6a767ddb9f8de106ae5503a689f5e51`.

The predeclared English reference uses **374.19–675.08 seconds**, a continuous **300.89-second** source window selected before model predictions. It contains 191 intonation units from two speakers (106/85 units), 721 normalized words, two source-author uncertain-hearing spans, and 16 partial-word tokens. The uncertain spans have dedicated 0.64-second and 4.16-second audit clips. An earlier 300.44-second preparation was abandoned before inference; it is not the evaluated window.

External clip: `sbc005-en-300.89s.wav`, SHA-256 `c02296391d76e22d35bac766eb29f36b14d61feea8568fcbcde1ab764b829ff6`. Matching reference: `sbc005-en-300.89s-reference.json`. Its text conversion preserves words inside scoped transcription markers and removes annotation syntax; it does not replace manual words with model predictions. The reference deliberately has `turns: []`, because intonation-unit intervals include pauses and are not independently audited speech-activity labels. This supports a disclosed manual-transcription WER assessment, not a passed hand-labelled speaker-attribution gate. Both source uncertainty and partial-word conventions must remain visible in the quality report.

The verified [SBC005 preparation CLI](../../scripts/prepare-sbc-reference.py) checks the original WAV/TRN SHA-256, reconstructs the fixed source window, and produces the clip, reference, uncertainty-audit clips, and provenance. It requires FFmpeg, performs no downloads or inference, and refuses a nonempty output directory:

```sh
.venv/bin/python scripts/prepare-sbc-reference.py --audio /path/outside/repository/SBC005.original.wav --transcript /path/outside/repository/SBC005.trn --output-root /path/outside/repository/prepared-sbc005
```

The CLI was verified against the original public assets: the reconstructed WAV has the recorded `c0229639…` hash and the complete normalized reference text matches the predeclared 721-word candidate. Source-label and scoped-marker context is carried through the complete transcript before selecting the window. Fourteen deterministic parser regression tests cover the conversion using synthetic fixtures, without corpus text, model assets, or credentials in Git.

### Acquired natural three-speaker challenge

The exact public [SBC003 WAV source](https://ucsb.app.box.com/s/gpwue7abbd502r4hrqqa6rbum3p5s6o1) was acquired without credentials or cookies through the anonymous Box download route. Box file ID: `965531658796`. It is 138,213,444 bytes, 1567.045351473923 seconds, stereo 22,050 Hz PCM16, SHA-256 `a7341ea55f91395742a696e1e24d12663324b7c9c53424e0c3ae70d62bd25bbb`. The independently published [SBC003.trn](https://www.linguistics.ucsb.edu/sites/default/files/sitefiles/research/SBC/SBC003.trn) is 71,650 bytes, SHA-256 `b6416ae4c700ecfe6d70ab20d6cf5c3833ae40eb4cb471f7140292aebbee74a7`.

Before model predictions, a continuous **540–660 second** window was selected using only source annotation. The 120-second clip preserves the original channels/rate/sample width and contains three independently annotated speakers with **41, 26, and 22 intonation-unit rows**. Twenty source rows mark overlap around lexical material. The union of intersecting intonation-unit intervals is 5.96 seconds; this is an annotation diagnostic, not a measurement of exact overlapping speech, because those intervals include pauses.

- External clip: `en-sbc003-0540000-0660000-three-speaker.wav`, SHA-256 `d754192dfad981a432c922f81e8a88cf522d8a3467e88bdb11214c8943bc0842`.
- External reference: `en-sbc003-0540000-0660000-three-speaker-reference.json`, SHA-256 `488c6ce8201dff78258e091ad1ed49cbfc66b1ed96db2e56058c623957a2aca3`.

One source row is partly unintelligible and two cross crop boundaries. The known reference text omits boundary-crossing units and transcription markup; timestamps use clipped intonation-unit intervals. Both `wordErrorRateGateEligible` and `speakerAttributionGateEligible` are explicitly `false`. This is genuine continuous multiparty audio for observing recognition, recurring labels, and overlap behavior; it does not supply a clean, complete quality-gate reference. No voices were synthesized, concatenated, relabelled from two speakers, or repeated. Raw and derived corpus content remains outside Git, with local transformation only and no adapted redistribution under CC BY-ND 3.0 US.

## English: AMI for performance and multiparty challenges

[AMI's official download page](https://groups.inf.ed.ac.uk/ami/download/) publishes audio and manual **NXT XML** annotations under **CC BY 4.0**. Manual annotations v1.6.2 are explicitly separate from automatic annotations. The [signal metadata](https://groups.inf.ed.ac.uk/ami/corpus/signals.shtml) gives continuous meeting durations, for example ES2002b at 2,281 seconds, suitable in principle for a representative 30-minute performance input after source/audio checks.

The [official data-problems page](https://groups.inf.ed.ac.uk/ami/corpus/dataproblems.shtml) identifies EN2001a/e, EN2005a, and **EN2009d** as meetings longer than one hour. It states that their audio contains the full meeting even though video tapes end earlier; that entry does not report an audio dropout for EN2009d. Some AMI sessions are elicited role-play with four participants; disclose the chosen session and its conditions. Do not present a multiparty meeting as a two-speaker quality reference.

The complete public `EN2009d.Mix-Headset.wav` has now been acquired outside Git: **170,379,992 bytes**, actual WAV-header duration **5324.373375 seconds**, mono 16 kHz PCM16, SHA-256 `eeb4a5ff47cadba8c75bdf32213b9264805027faa943c7f55eec0423c6ea4312`. Acquisition took 884.338 seconds. These are verified file/download measurements, not inference timings or a completed performance gate; the public source manifest is stored externally as `ami-source.json`.

## Remaining evidence

No quality threshold is established by this research. Acquired English challenge and Polish reference audio still require actual sequential inference and appropriately audited reference semantics; acquisition alone does not pass a gate. The public SpokesBiz sample provides permitted natural Polish audio and human-corrected text; its automatic alignment and initial diarization require an independent boundary/label audit before the attribution gate can pass. Marcin's own corrected recording or personally completed corpus access remain alternatives, not prerequisites to using the public sample. The performance, mixed-language, overlap, silence/music, and offline gates remain separate measurements.
