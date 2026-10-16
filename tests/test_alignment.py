import copy

import pytest
from localscribe.alignment import assemble


def result(segments, regular=None, exclusive=None, **kwargs):
    return assemble(
        {"language": "pl", "segments": segments},
        regular or [],
        exclusive or [],
        10,
        "job-1",
        {"language": "pl"},
        **kwargs,
    )


def segment(text=" Hello world", words=None, start=0, end=2):
    return {
        "start": start,
        "end": end,
        "text": text,
        "words": words
        if words is not None
        else [
            {"start": 0, "end": 1, "word": " Hello"},
            {"start": 1, "end": 2, "word": " world"},
        ],
    }


def test_changes_preserve_model_boundaries_text_and_repeated_speakers():
    turns = [
        {"start": 1, "end": 2, "speaker": "A"},
        {"start": 0, "end": 1, "speaker": "Z"},
        {"start": 3, "end": 4, "speaker": "Z"},
    ]
    inputs = [segment(), segment(" again", [{"start": 3, "end": 4, "word": " again"}], 3, 4)]
    immutable = copy.deepcopy(inputs)
    output = result(inputs, turns, turns)
    assert [item["speakerId"] for item in output["segments"]] == [
        "speaker_1",
        "speaker_2",
        "speaker_1",
    ]
    assert [item["text"].strip() for item in output["segments"]] == ["Hello", "world", "again"]
    assert output["modelSegments"] == immutable
    assert inputs == immutable
    assert output == result(inputs, list(reversed(turns)), list(reversed(turns)))


def test_greatest_overlap_then_earliest_turn_then_stable_id():
    word = [segment("word", [{"start": 1, "end": 2, "word": "word"}], 1, 2)]
    turns = [
        {"start": 0, "end": 1.5, "speaker": "early"},
        {"start": 1.5, "end": 3, "speaker": "late"},
    ]
    assert result(word, turns, turns)["segments"][0]["speakerId"] == "speaker_1"
    turns[1]["start"] = 1.4
    assert result(word, turns, turns)["segments"][0]["speakerId"] == "speaker_2"
    ties = [{"start": 1, "end": 2, "speaker": "B"}, {"start": 1, "end": 2, "speaker": "A"}]
    assert result(word, ties, ties)["segments"][0]["speakerId"] == "speaker_1"


def test_gaps_and_touching_boundaries_have_unknown_speaker():
    turns = [{"start": 2, "end": 3, "speaker": "A"}]
    assert all(item["speakerId"] is None for item in result([segment()], turns, turns)["words"])


def test_overlap_requires_simultaneous_distinct_speakers():
    exclusive = [{"start": 0, "end": 2, "speaker": "A"}]
    sequential = exclusive + [{"start": 2, "end": 3, "speaker": "B"}]
    assert result([segment()], sequential, exclusive)["segments"][0]["overlap"] is False
    overlap = exclusive + [{"start": 0.5, "end": 1.5, "speaker": "B"}]
    assert result([segment()], overlap, exclusive)["segments"][0]["overlap"] is True
    duplicate = exclusive + [{"start": 0.5, "end": 1.5, "speaker": "A"}]
    assert result([segment()], duplicate, exclusive)["segments"][0]["overlap"] is False


@pytest.mark.parametrize(
    "words", [[], [{"word": "Hello world"}], [{"start": 0, "end": 1, "word": "Hello"}]]
)
def test_missing_or_incomplete_words_preserve_every_character(words):
    output = result([segment(" Zażółć gęślą jaźń!", words)])
    assert output["segments"][0]["text"] == " Zażółć gęślą jaźń!"
    assert output["warnings"][0]["code"] == "alignment_fallback"
    assert output["modelSegments"][0]["words"] == words


def test_disabled_and_failed_diarization_do_not_attribute_speakers():
    asr = {"segments": [segment()]}
    turns = [{"start": 0, "end": 2, "speaker": "A"}]
    disabled = assemble(asr, turns, turns, 10, "job", {"diarization": False})
    assert disabled["options"]["diarization"] is False
    assert disabled["warnings"] == []
    failed = assemble(
        asr,
        turns,
        turns,
        10,
        "job",
        {},
        warnings=[{"code": "diarization_failed", "message": "Speaker labels are unavailable."}],
    )
    for output in (disabled, failed):
        assert output["speakers"] == []
        assert all(item["speakerId"] is None for item in output["segments"])
        assert output["segments"][0]["text"] == " Hello world"
    assert failed["warnings"][0]["code"] == "diarization_failed"


@pytest.mark.parametrize("start,end", [(-1, 1), (0, float("nan")), (1, 1), (0, 11)])
def test_invalid_model_intervals_are_rejected(start, end):
    with pytest.raises(ValueError):
        result([segment(start=start, end=end)])


def test_empty_transcript_has_notice_and_provenance():
    output = result([], provenance={"asr": {"revision": "immutable-sha"}})
    assert output["segments"] == []
    assert output["warnings"][0]["code"] == "empty_transcript"
    assert output["provenance"]["asr"]["revision"] == "immutable-sha"


def test_raw_turn_labels_and_diagnostics_are_preserved():
    turns = [{"start": 0, "end": 2, "speakerId": "raw-id", "confidence": 0.75}]
    output = result([segment()], turns, turns)
    assert output["regularTurns"][0]["originalSpeakerId"] == "raw-id"
    assert output["regularTurns"][0]["speakerId"] == "speaker_1"
    assert output["exclusiveTurns"][0]["confidence"] == 0.75


def test_text_without_timestamped_segments_is_not_reported_as_silence():
    with pytest.raises(ValueError, match="timestamped"):
        assemble({"text": "Recognized speech", "segments": []}, [], [], 10, "job", {})
