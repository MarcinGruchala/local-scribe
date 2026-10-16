"""Reproducible reference scoring without model, network, or third-party dependencies."""

import math
import unicodedata
from itertools import pairwise


def normalize_words(text: str) -> list[str]:
    """Normalize case and punctuation, retaining Unicode letters and numbers."""
    if not isinstance(text, str):
        raise TypeError("Reference and hypothesis text must be strings.")
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return "".join(
        character if character.isalnum() or character.isspace() else " " for character in normalized
    ).split()


def word_error_rate(reference: str, hypothesis: str) -> dict:
    """Levenshtein WER; edit ties prefer substitution, deletion, then insertion."""
    expected, actual = normalize_words(reference), normalize_words(hypothesis)
    # Each cell stores distance, substitutions, deletions, and insertions.
    previous = [(index, 0, 0, index) for index in range(len(actual) + 1)]
    for row, reference_word in enumerate(expected, 1):
        current = [(row, 0, row, 0)]
        for column, hypothesis_word in enumerate(actual, 1):
            distance, substitutions, deletions, insertions = previous[column - 1]
            substitution = int(reference_word != hypothesis_word)
            diagonal = (
                distance + substitution,
                substitutions + substitution,
                deletions,
                insertions,
            )
            distance, substitutions, deletions, insertions = previous[column]
            deletion = (distance + 1, substitutions, deletions + 1, insertions)
            distance, substitutions, deletions, insertions = current[column - 1]
            insertion = (distance + 1, substitutions, deletions, insertions + 1)
            current.append(min((diagonal, deletion, insertion), key=lambda item: item[0]))
        previous = current
    errors, substitutions, deletions, insertions = previous[-1]
    return {
        "referenceWords": len(expected),
        "hypothesisWords": len(actual),
        "substitutions": substitutions,
        "deletions": deletions,
        "insertions": insertions,
        "errors": errors,
        "wordErrorRate": errors / len(expected) if expected else None,
    }


def _turns(turns: list[dict], *, reference: bool) -> list[dict]:
    result = []
    for turn in turns:
        start, end, speaker = turn["start"], turn["end"], turn.get("speakerId")
        if (
            isinstance(start, bool)
            or isinstance(end, bool)
            or not isinstance(start, (int, float))
            or not isinstance(end, (int, float))
            or not math.isfinite(start)
            or not math.isfinite(end)
            or not 0 <= start < end
        ):
            raise ValueError("Reference and prediction turns require finite nonnegative intervals.")
        if (speaker is None and reference) or (
            speaker is not None and (not isinstance(speaker, str) or not speaker.strip())
        ):
            raise ValueError("Reference speakers require nonempty anonymous IDs.")
        result.append({"start": float(start), "end": float(end), "speakerId": speaker})
    return result


def _maximum_matching(weights: dict[tuple[str, str], float]) -> tuple[float, dict[str, str]]:
    """Maximum weighted one-to-one label mapping, with optional unmatched labels."""
    predicted = sorted({pair[0] for pair in weights})
    reference = sorted({pair[1] for pair in weights})
    # Mask the smaller side so an excess of predicted labels remains inexpensive.
    transpose = len(predicted) < len(reference)
    rows, columns = (reference, predicted) if transpose else (predicted, reference)
    if len(columns) > 20:
        raise ValueError("Reference scoring supports at most 20 speakers on the smaller side.")
    states = {0: (0.0, ())}
    for row in rows:
        updated = dict(states)
        for mask, (score, pairs) in states.items():
            for index, column in enumerate(columns):
                if mask & (1 << index):
                    continue
                pair = (column, row) if transpose else (row, column)
                weight = weights.get(pair, 0.0)
                if weight <= 0:
                    continue
                new_mask = mask | (1 << index)
                candidate = (score + weight, tuple(sorted((*pairs, pair))))
                existing = updated.get(new_mask)
                if (
                    existing is None
                    or candidate[0] > existing[0]
                    or (candidate[0] == existing[0] and candidate[1] < existing[1])
                ):
                    updated[new_mask] = candidate
        states = updated
    best = min(states.values(), key=lambda item: (-item[0], item[1]))
    return best[0], dict(best[1])


def speaker_attribution(
    reference_turns: list[dict],
    predicted_turns: list[dict],
    *,
    duration: float | None = None,
    collar: float = 0.25,
    overlap_turns: list[dict] | None = None,
) -> dict:
    """Score single-speaker reference duration after collars and overlap exclusions.

    More than one simultaneous predicted label receives no attribution credit.
    Regular prediction overlap is measured separately from selected scoring turns.
    """
    reference = _turns(reference_turns, reference=True)
    predicted = _turns(predicted_turns, reference=False)
    regular = _turns(
        overlap_turns if overlap_turns is not None else predicted_turns, reference=False
    )
    if not math.isfinite(collar) or collar < 0:
        raise ValueError("The boundary collar must be finite and nonnegative.")
    largest_end = max((turn["end"] for turn in reference + predicted + regular), default=0.0)
    duration = largest_end if duration is None else duration
    if not math.isfinite(duration) or duration < largest_end or duration < 0:
        raise ValueError("Scoring duration must contain every reference and predicted interval.")
    collars = [
        (max(0.0, boundary - collar), min(duration, boundary + collar))
        for turn in reference
        for boundary in (turn["start"], turn["end"])
    ]
    boundaries = {0.0, duration}
    for turn in reference + predicted + regular:
        boundaries.update((turn["start"], turn["end"]))
    for start, end in collars:
        boundaries.update((start, end))
    timeline = sorted(boundaries)
    totals = dict.fromkeys(
        (
            "referenceSpeechSeconds",
            "scoredReferenceSeconds",
            "excludedReferenceOverlapSeconds",
            "excludedReferenceCollarSeconds",
            "collarRegionSeconds",
            "missedSpeechSeconds",
            "unknownSpeakerSeconds",
            "ambiguousPredictionSeconds",
            "falsePositiveSeconds",
            "predictionOverlapSeconds",
            "predictionOverlapOnScoredReferenceSeconds",
        ),
        0.0,
    )
    weights = {}
    labels = {turn["speakerId"] for turn in predicted if turn["speakerId"] is not None}

    def active(turns, time):
        return {turn["speakerId"] for turn in turns if turn["start"] <= time < turn["end"]}

    for start, end in pairwise(timeline):
        length, midpoint = end - start, (start + end) / 2
        ref, pred, raw = (
            active(reference, midpoint),
            active(predicted, midpoint),
            active(regular, midpoint),
        )
        in_collar = any(left <= midpoint < right for left, right in collars)
        raw_overlap = len(raw - {None}) > 1
        if raw_overlap:
            totals["predictionOverlapSeconds"] += length
        if in_collar:
            totals["collarRegionSeconds"] += length
        if ref:
            totals["referenceSpeechSeconds"] += length
        if len(ref) > 1:
            totals["excludedReferenceOverlapSeconds"] += length
            continue
        if in_collar:
            if ref:
                totals["excludedReferenceCollarSeconds"] += length
            continue
        if not ref:
            if pred:
                totals["falsePositiveSeconds"] += length
            continue
        totals["scoredReferenceSeconds"] += length
        if raw_overlap:
            totals["predictionOverlapOnScoredReferenceSeconds"] += length
        if not pred:
            totals["missedSpeechSeconds"] += length
        elif None in pred:
            totals["unknownSpeakerSeconds"] += length
        elif len(pred) > 1:
            totals["ambiguousPredictionSeconds"] += length
        else:
            pair = (next(iter(pred)), next(iter(ref)))
            weights[pair] = weights.get(pair, 0.0) + length
    correct, mapping = _maximum_matching(weights)
    eligible = totals["scoredReferenceSeconds"]
    incorrect = max(0.0, eligible - correct)
    return {
        **totals,
        "correctSeconds": correct,
        "incorrectSeconds": incorrect,
        "correctFraction": correct / eligible if eligible else None,
        "errorFraction": incorrect / eligible if eligible else None,
        "confusedSpeakerSeconds": max(
            0.0,
            incorrect
            - totals["missedSpeechSeconds"]
            - totals["unknownSpeakerSeconds"]
            - totals["ambiguousPredictionSeconds"],
        ),
        "speakerMapping": mapping,
        "unmatchedPredictionLabels": sorted(labels - mapping.keys()),
        "durationSeconds": duration,
        "boundaryCollarSecondsPerSide": collar,
    }


def score_reference(
    reference: dict,
    transcript: dict,
    *,
    text_source: str = "raw",
    speaker_source: str = "segments",
    collar: float = 0.25,
) -> dict:
    """Return aggregate-only evidence; never include private reference/transcript text."""
    if text_source == "raw":
        text = transcript.get("originalText")
        if text is None:
            text = " ".join(segment["text"] for segment in transcript.get("modelSegments", []))
    elif text_source == "saved":
        text = " ".join(
            segment["editedText"] if segment.get("editedText") is not None else segment["text"]
            for segment in transcript.get("segments", [])
        )
    else:
        raise ValueError("Text source must be raw or saved.")
    fields = {"segments": "segments", "exclusive": "exclusiveTurns", "regular": "regularTurns"}
    if speaker_source not in fields:
        raise ValueError("Speaker source must be segments, exclusive, or regular.")
    if fields[speaker_source] not in transcript:
        raise ValueError("The selected speaker source is absent from this transcript.")
    return {
        "schemaVersion": 1,
        "method": {
            "normalization": "NFKC, casefold, Unicode alphanumeric tokens, punctuation to spaces",
            "textSource": text_source,
            "speakerSource": speaker_source,
            "boundaryCollarSecondsPerSide": collar,
            "referenceOverlapExcluded": True,
            "mapping": "maximum-duration one-to-one permutation-invariant matching",
        },
        "wer": word_error_rate(reference["text"], text),
        "speakers": speaker_attribution(
            reference["turns"],
            transcript[fields[speaker_source]],
            duration=transcript.get("duration"),
            collar=collar,
            overlap_turns=transcript.get("regularTurns"),
        ),
    }
