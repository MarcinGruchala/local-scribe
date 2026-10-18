"""Public-reference conversion tests use invented text and never fetch corpus assets."""

import runpy
from pathlib import Path

import pytest

build_reference = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/public-reference.py")
)["build_reference"]


def row(sequence, speaker, text, start, end):
    return {
        "recording_id": "CBIZ_LUZ_013",
        "segment_seq": str(sequence),
        "speaker_id": speaker,
        "segment_text": text,
        "segment_ts_start_ms": str(start),
        "segment_ts_end_ms": str(end),
        "segment_id": f"segment-{sequence}",
        "segment_word_count": str(len(text.split())),
    }


def test_reference_retains_whole_human_segments_and_converts_milliseconds():
    reference = build_reference(
        [
            row(2, "speaker-b", "Second corrected sentence.", 1500, 3000),
            row(1, "speaker-a", "First corrected sentence.", 1000, 1400),
            row(3, "speaker-a", "Crossing boundary must remain excluded.", 582000, 583000),
        ],
        "csv-hash",
        "wav-hash",
    )
    assert reference["text"] == "First corrected sentence. Second corrected sentence."
    assert reference["turns"] == [
        {"start": 1.0, "end": 1.4, "speakerId": "ref_1"},
        {"start": 1.5, "end": 3.0, "speakerId": "ref_2"},
    ]
    assert reference["metadata"]["sourceSegmentIds"] == ["segment-1", "segment-2"]
    assert reference["metadata"]["csvSha256"] == "csv-hash"
    assert reference["metadata"]["originalWavSha256"] == "wav-hash"
    assert reference["metadata"]["sourceSegmentWordCount"] == 6


def test_automatic_boundaries_never_claim_a_hand_labelled_quality_reference():
    reference = build_reference(
        [row(1, "a", "First.", 0, 1000), row(2, "b", "Second.", 1000, 2000)], "csv", "wav"
    )
    assert reference["metadata"]["speakerAttributionGateEligible"] is False
    assert (
        reference["metadata"]["speakerReferenceStatus"]
        == "automatically_realigned_not_independently_audited"
    )
    assert reference["metadata"]["textReferenceStatus"] == "human_corrected_corpus_text"


def test_source_window_must_have_exactly_two_speakers():
    with pytest.raises(ValueError, match="exactly two"):
        build_reference([row(1, "a", "Single speaker.", 0, 1000)], "csv", "wav")


def test_invalid_source_interval_cannot_become_reference_turn():
    with pytest.raises(ValueError, match="intervals"):
        build_reference(
            [row(1, "a", "First.", 1000, 1000), row(2, "b", "Second.", 1000, 2000)], "csv", "wav"
        )
