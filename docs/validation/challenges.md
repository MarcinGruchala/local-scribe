# Practical cached-model challenges — 2026-10-17

Both prepared public inputs ran sequentially using the pinned production Fast MLX profile and CPU Community-1, with external networking denied by `scripts/offline.sb` and an empty HF home. Inputs and raw results remain outside Git. Source licenses, windows and hashes are in [reference provenance](../research/reference-corpora.md). These are practical diagnostics, not independently hand-audited attribution scores.

## Natural three-voice conversation and overlap

The predeclared SBC003 window 540–660 s has 120 s of natural English conversation. Actual inference returns 29 display segments, 257 words, three anonymous speaker IDs, 44 regular turns and 43 exclusive turns. The three IDs recur across 18/7/4 display segments; eight segments are flagged for overlap and none has an unknown speaker. Child total 58.712 s, ASR 2.976 s, diarization 52.929 s, wrapper 59.467 s, peak RSS 5270323200 bytes. All 31 pressure samples are normal; maximum observed gap 2.010 s. `alignment_fallback` is retained.

This verifies processing, recurring IDs and visible overlap metadata on a natural three-voice input. Source intonation-unit timing is not gold speech timing; no correct-label fraction or overlap accuracy is claimed.

## Instrumental music

The prepared 30 s CC0 piano excerpt contains no reference speech. Actual Fast/Auto inference produces two normalized words/10 non-whitespace characters in one 0.420 s segment. Community-1 returns zero regular/exclusive turns and zero speakers. The fixed scorer reports two insertions, zero reference words and undefined WER; the empty-recognition expectation **fails**. Child total 5.380 s, wrapper 6.234 s, peak RSS 1909473280 bytes; all five pressure samples normal. The original failed output is retained.

Added a review warning when enabled, successful diarization finds no turns but ASR produced display text: `no_speaker_turns`. It preserves model text, words, timing and null labels; it does not classify music or suppress quiet speech. Intentional ASR-only operation and speaker-stage failure retain their separate behavior. A fresh actual offline repeat confirms the same two words plus the warning: total 5.162 s, wrapper 5.849 s, RSS 1904295936 bytes, all four pressure samples normal. Recognition quality remains failed; the warning is a transparency improvement.

Tests verify immutable text/words and warning conditions. The final fast suite has 210 passes. Existing exact-zero silence correction and constructed language-switch failures remain in [release evidence](mvp-release.md). The user deferred independent manual boundary auditing to later practical checking; no further reference-corpus acquisition was pursued.
