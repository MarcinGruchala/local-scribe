"""Hand-computed scoring cases; no inference, credentials, or downloaded assets."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from localscribe.scoring import (
    normalize_words,
    score_reference,
    speaker_attribution,
    word_error_rate,
)


def turn(start, end, speaker):
    return {"start": start, "end": end, "speakerId": speaker}


def test_wer_normalization_retains_polish_diacritics_and_numbers():
    assert normalize_words("ZAŻÓŁĆ, gęślą—jaźń! 123\n４５") == [
        "zażółć",
        "gęślą",
        "jaźń",
        "123",
        "45",
    ]
    assert word_error_rate("Zażółć gęślą jaźń", "zażółć, GĘŚLĄ jaźń!")["wordErrorRate"] == 0
    assert word_error_rate("żółć 21", "zolc twenty one")["errors"] == 3
    assert word_error_rate("21", "twenty one")["wordErrorRate"] == 2


@pytest.mark.parametrize(
    "reference,hypothesis,counts",
    [
        ("one two three", "one three", (0, 1, 0)),
        ("one two", "one new two", (0, 0, 1)),
        ("one two", "one other", (1, 0, 0)),
    ],
)
def test_wer_counts_known_edits(reference, hypothesis, counts):
    result = word_error_rate(reference, hypothesis)
    assert (result["substitutions"], result["deletions"], result["insertions"]) == counts
    assert result["errors"] == sum(counts)
    assert result["wordErrorRate"] == sum(counts) / result["referenceWords"]


def test_empty_reference_reports_insertions_without_claiming_a_quality_rate():
    result = word_error_rate("", "hallucinated text")
    assert result["insertions"] == 2
    assert result["wordErrorRate"] is None
    assert word_error_rate("", "")["wordErrorRate"] is None


def test_swapped_speaker_labels_receive_full_credit_after_boundary_collars():
    reference = [turn(0, 2, "ref_A"), turn(2, 4, "ref_B")]
    predicted = [turn(0, 2, "pred_Y"), turn(2, 4, "pred_X")]
    result = speaker_attribution(reference, predicted)
    assert result["scoredReferenceSeconds"] == 3
    assert result["excludedReferenceCollarSeconds"] == 1
    assert result["correctSeconds"] == 3
    assert result["correctFraction"] == 1
    assert result["speakerMapping"] == {"pred_Y": "ref_A", "pred_X": "ref_B"}
    assert result == speaker_attribution(list(reversed(reference)), list(reversed(predicted)))


def test_matching_maximizes_global_duration_and_counts_confusion():
    reference = [turn(0, 2, "A"), turn(2, 4, "B")]
    predicted = [turn(0, 3, "X"), turn(3, 4, "Y")]
    result = speaker_attribution(reference, predicted, collar=0)
    assert result["speakerMapping"] == {"X": "A", "Y": "B"}
    assert result["correctSeconds"] == 3
    assert result["incorrectSeconds"] == result["confusedSpeakerSeconds"] == 1
    assert result["correctFraction"] == 0.75


def test_matching_does_not_greedily_consume_the_best_reference_label():
    reference = [turn(0, 3, "A"), turn(3, 5, "B"), turn(5, 6, "C")]
    predicted = [turn(0, 2, "X"), turn(2, 3, "Y"), turn(3, 5, "X")]
    result = speaker_attribution(reference, predicted, collar=0)
    # X ties on A/B. Assigning X to A would prevent the only useful mapping for Y.
    assert result["speakerMapping"] == {"X": "B", "Y": "A"}
    assert result["correctSeconds"] == 3
    assert result["confusedSpeakerSeconds"] == 2
    assert result["missedSpeechSeconds"] == 1


def test_missed_unknown_and_unmatched_speakers_remain_in_denominator():
    reference = [turn(0, 4, "A")]
    predicted = [turn(0, 1, "X"), turn(1, 2, None), turn(2, 2.5, "Y")]
    result = speaker_attribution(reference, predicted, collar=0)
    assert result["scoredReferenceSeconds"] == 4
    assert result["correctSeconds"] == 1
    assert result["unknownSpeakerSeconds"] == 1
    assert result["missedSpeechSeconds"] == 1.5
    assert result["confusedSpeakerSeconds"] == 0.5
    assert result["unmatchedPredictionLabels"] == ["Y"]
    assert result["incorrectSeconds"] == 3


def test_reference_overlap_is_excluded_and_false_positives_are_separate():
    reference = [turn(1, 4, "A"), turn(3, 5, "B")]
    predicted = [turn(0, 6, "X")]
    result = speaker_attribution(reference, predicted, collar=0)
    assert result["referenceSpeechSeconds"] == 4
    assert result["excludedReferenceOverlapSeconds"] == 1
    assert result["scoredReferenceSeconds"] == 3
    assert result["correctSeconds"] == 2
    assert result["incorrectSeconds"] == 1
    assert result["falsePositiveSeconds"] == 2


def test_regular_prediction_overlap_is_diagnostic_even_with_exclusive_attribution():
    reference = [turn(0, 4, "A")]
    exclusive = [turn(0, 4, "X")]
    regular = exclusive + [turn(1, 2, "Y")]
    result = speaker_attribution(reference, exclusive, overlap_turns=regular, collar=0)
    assert result["correctSeconds"] == 4
    assert result["predictionOverlapSeconds"] == 1
    assert result["predictionOverlapOnScoredReferenceSeconds"] == 1
    regular_result = speaker_attribution(reference, regular, collar=0)
    assert regular_result["correctSeconds"] == 3
    assert regular_result["incorrectSeconds"] == regular_result["ambiguousPredictionSeconds"] == 1


def test_duplicate_same_speaker_turns_do_not_count_as_overlap():
    reference = [turn(0, 2, "A"), turn(1, 3, "A")]
    predicted = [turn(0, 3, "X"), turn(1, 2, "X")]
    result = speaker_attribution(reference, predicted, collar=0)
    assert result["scoredReferenceSeconds"] == result["correctSeconds"] == 3
    assert result["excludedReferenceOverlapSeconds"] == result["predictionOverlapSeconds"] == 0


def test_boundary_collar_excludes_union_without_double_counting_overlap():
    result = speaker_attribution([turn(1, 3, "A")], [turn(0, 4, "X")])
    assert result["correctSeconds"] == result["scoredReferenceSeconds"] == 1.5
    assert result["excludedReferenceCollarSeconds"] == 0.5
    assert result["collarRegionSeconds"] == 1
    assert result["falsePositiveSeconds"] == 1.5
    # Every moment of overlapping reference speech is excluded just once.
    overlap = speaker_attribution([turn(0, 2, "A"), turn(1, 3, "B")], [turn(0, 3, "X")])
    assert overlap["excludedReferenceOverlapSeconds"] == 1
    assert overlap["excludedReferenceCollarSeconds"] == 1
    assert overlap["scoredReferenceSeconds"] == 1


def test_empty_or_completely_collared_reference_has_no_quality_rate():
    result = speaker_attribution([], [], duration=3)
    assert result["correctFraction"] is None
    assert result["errorFraction"] is None
    assert speaker_attribution([turn(0, 0.1, "A")], [turn(0, 0.1, "X")])["correctFraction"] is None


@pytest.mark.parametrize(
    "bad", [turn(-1, 1, "A"), turn(1, 1, "A"), turn(0, float("inf"), "A"), turn(0, 1, None)]
)
def test_invalid_reference_intervals_or_speakers_are_rejected(bad):
    with pytest.raises(ValueError):
        speaker_attribution([bad], [])


def test_scoring_rejects_turns_beyond_recording_duration():
    with pytest.raises(ValueError, match="contain"):
        speaker_attribution([turn(0, 2, "A")], [turn(0, 3, "X")], duration=2)


def test_export_sources_are_explicit_and_raw_wer_ignores_user_edits():
    reference = {"text": "correct speech", "turns": [turn(0, 2, "A")]}
    transcript = {
        "duration": 2,
        "originalText": "wrong speech",
        "segments": [{**turn(0, 2, "X"), "text": "wrong speech", "editedText": "correct speech"}],
        "exclusiveTurns": [turn(0, 2, "Y")],
        "regularTurns": [turn(0, 2, "Y")],
    }
    raw = score_reference(reference, transcript)
    assert raw["wer"]["wordErrorRate"] == 0.5
    assert raw["speakers"]["speakerMapping"] == {"X": "A"}
    saved = score_reference(reference, transcript, text_source="saved", speaker_source="exclusive")
    assert saved["wer"]["wordErrorRate"] == 0
    assert saved["speakers"]["speakerMapping"] == {"Y": "A"}
    assert saved["method"]["textSource"] == "saved"
    assert "correct speech" not in json.dumps(saved)
    transcript["segments"][0]["editedText"] = ""
    assert score_reference(reference, transcript, text_source="saved")["wer"]["deletions"] == 2


def test_score_cli_outputs_aggregate_only_json(tmp_path):
    reference = tmp_path / "reference.json"
    transcript = tmp_path / "transcript.json"
    output = tmp_path / "score.json"
    reference.write_text(
        json.dumps({"text": "Private corrected words", "turns": [turn(0, 2, "A")]})
    )
    transcript.write_text(
        json.dumps(
            {
                "duration": 2,
                "originalText": "Private corrected words",
                "segments": [turn(0, 2, "X")],
            }
        )
    )
    script = Path(__file__).resolve().parents[1] / "scripts" / "score-reference.py"
    process = subprocess.run(
        [sys.executable, str(script), str(reference), str(transcript), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    content = output.read_text()
    assert process.stdout == ""
    assert "Private corrected words" not in content
    assert json.loads(content)["wer"]["wordErrorRate"] == 0
