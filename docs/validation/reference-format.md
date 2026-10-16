# Corrected references and reproducible scoring

Quality remains **unverified** until representative recordings and manually corrected references are available. The scorer and its deterministic tests do not establish transcription or diarization quality.

Keep reference files, recordings, exported transcripts, and individual score outputs outside Git. Use recordings with permission for local processing. Use anonymous speaker IDs such as `ref_1`; do not use a person's name as a reference ID. A reference must describe exactly the same recording and timeline as the transcript's normalized audio, beginning at zero seconds.

## Required reference JSON

```json
{
  "text": "The complete manually corrected original-language speech.",
  "turns": [
    {"start": 0.5, "end": 2.0, "speakerId": "ref_1"},
    {"start": 2.0, "end": 3.5, "speakerId": "ref_2"}
  ]
}
```

`text` is a string without speaker prefixes. `turns` contain finite seconds with `0 <= start < end <= recording duration`. Each turn names an anonymous reference speaker consistently throughout that recording. Annotate speech boundaries manually, including simultaneous speakers as overlapping turns. Do not convert silence to a speaker turn. Merge adjacent turns by the same speaker where no speech boundary needs to be annotated; arbitrary subdivisions introduce unnecessary collar exclusions. Reference text and boundaries must be corrected independently of the predictions being evaluated.

## Run

From the repository, using its installed Python environment:

```sh
.venv/bin/python scripts/score-reference.py "/path/outside/repository/reference.json" "/path/outside/repository/transcript.json" --output "/path/outside/repository/score.json"
```

The transcript input is the application's versioned JSON export. The default WER uses immutable `originalText`, falling back to original `modelSegments` text when that field is absent. It never substitutes saved corrections for model output. The default speaker score uses the delivered display `segments` and their anonymous `speakerId` values. `regularTurns` are also measured for the separate prediction-overlap diagnostics. Null attribution remains unknown and cannot receive correctness credit.

Use `--text-source saved` only to assess the saved edited transcript. Use `--speaker-source exclusive` or `--speaker-source regular` to assess the corresponding diarization-engine turns independently of displayed word attribution. The selected sources appear in the report. These diagnostics must not silently replace the default product-quality measurement.

The output contains aggregate counts, durations, anonymous label mappings, and scoring settings; it contains no reference or hypothesis text. Keep individual outputs outside Git and copy only reviewed, sanitized aggregate results into the release report.

## WER method

Text normalization applies Unicode NFKC, then Unicode case folding. Unicode letters and numbers are retained; punctuation and other non-alphanumeric characters become spaces; whitespace collapses into token boundaries. Polish diacritics remain meaningful. Numbers are not verbalized or converted between written forms: `21` and `twenty one` differ. NFKC itself performs compatibility normalization, such as converting fullwidth digits to ordinary digits. Hyphens and apostrophes become token boundaries. This fixed policy must be identical for all profiles and languages.

WER is `(substitutions + deletions + insertions) / reference words`, using minimum Levenshtein word-edit distance. Equal-cost edit paths prefer substitution, then deletion, then insertion. WER may exceed 1. An empty reference has an undefined WER, reported as JSON `null`; insertion counts still expose hallucinated speech. Do not treat an undefined rate as a passing quality result.

## Speaker method

The default boundary collar excludes **0.25 seconds on each side** of every reference turn start and end, clipped to the recording. The union of collars is excluded once. Reference speech with two or more distinct active speakers is excluded from the main attribution score and reported separately as `excludedReferenceOverlapSeconds`. Duplicate turns from one speaker do not establish overlap.

The remaining single-speaker reference duration is `scoredReferenceSeconds`. The scorer finds the maximum-duration one-to-one mapping between predicted and reference speaker IDs, independent of their spelling or order. `correctFraction = correctSeconds / scoredReferenceSeconds`; the specification's target is at least 0.90. Missing predictions, null speaker labels, unmatched predicted speakers, and simultaneous multiple predicted labels count as incorrect. Unknown and ambiguous predictions cannot earn partial credit. This is a duration attribution score, not a claim to implement every convention of a standard diarization-error-rate benchmark.

`missedSpeechSeconds`, `unknownSpeakerSeconds`, `ambiguousPredictionSeconds`, and `confusedSpeakerSeconds` partition incorrect scored duration. Unmatched labels appear in `unmatchedPredictionLabels`. `falsePositiveSeconds` measures predicted speech during reference silence outside collars and is reported separately; it does not alter the speech-attribution denominator. `predictionOverlapSeconds` measures overlap in regular prediction turns over the complete recording, including excluded reference regions. `predictionOverlapOnScoredReferenceSeconds` restricts that diagnostic to eligible reference speech. Overlap durations are wall-clock durations rather than sums of simultaneous speaker durations.

`excludedReferenceCollarSeconds` counts collared single-speaker reference speech, excluding already excluded overlap. `collarRegionSeconds` includes all collared time, including silence. If no reference speech remains eligible, attribution rates are `null`. Do not count those as passes. Other collars can be selected with `--collar`, but the release gate must use the documented 0.25-second setting and must disclose exclusions and scored duration.

## Release prerequisites and limits

At least one representative 5–10 minute English recording and one Polish recording require corrected text and hand-labelled two-speaker turns. The WER target is at most 0.15 separately for each language. The speaker target requires at least 0.90 correct eligible reference duration. Additional mixed-language, three-speaker, overlap, silence, and music cases expose failures not established by the two clean-speech scores. Silence/music references should contain an empty `text` and no turns when there is no speech; inspect hallucinated insertion counts and false-positive duration explicitly.

Run candidate ASR profiles on identical originals, references, language options, and scoring settings. Record exact model/package revisions, actual local inference evidence, cold/warm timings, peak memory, memory pressure, and any failures. A representative 30-minute recording is additionally required for the total real-time-factor target of at most 1.0. Scoring does not measure performance or establish successful cached-model operation with networking disabled. Those are separate release gates.

The scorer uses only the Python standard library and does not load models, download assets, inspect credentials, or send telemetry. Deterministic fixtures can validate this computation and the UI; they cannot replace representative references or actual local model jobs.
