"""Invented TRN snippets validate preparation without corpus assets or models."""

import runpy
import wave
from decimal import Decimal
from pathlib import Path

import pytest

script = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/prepare-sbc-reference.py")
)
clean_text, parse_trn = script["clean_text"], script["parse_trn"]


def test_indexed_overlap_exposes_indecipherable_syllables_and_preserves_words():
    row = parse_trn("0.00 1.00 ALPHA: [2X2] [3garden3]")[0]
    assert row["text"] == "X garden"
    assert row["indecipherableTokens"] == ["X"]
    assert row["metadataRemoved"]["overlapMarked"] is True
    assert not row["uncertainHearing"]


def test_speaker_labels_carry_across_continuation_rows_and_source_order_is_retained():
    rows = parse_trn("0.00 1.00 ALPHA: First.\n1.00 2.00 Next.\n1.50 2.50 BETA: Reply.")
    assert [row["sourceSpeaker"] for row in rows] == ["ALPHA", "ALPHA", "BETA"]
    assert [row["sourceLine"] for row in rows] == [1, 2, 3]
    assert [row["sourceStart"] for row in rows] == [0, 1, 1.5]


def test_uncertain_and_laughter_scopes_keep_lexical_best_guess():
    row = parse_trn("0.00 1.00 ALPHA: (H) <X <@ perhaps @> X> nearby.")[0]
    assert row["text"] == "perhaps nearby."
    assert row["retainedBestGuess"] == "perhaps"
    assert row["uncertainHearing"] is True
    assert row["indecipherableTokens"] == []
    assert row["metadataRemoved"]["parentheticalEvents"] == ["H"]


def test_uncertainty_scope_can_cross_rows_without_losing_speaker_or_words():
    rows = parse_trn("0.00 1.00 ALPHA: <X tentative\n1.00 2.00 phrase X> clear.\n2.00 3.00 Sure.")
    assert [row["uncertainHearing"] for row in rows] == [True, True, False]
    assert [row["retainedBestGuess"] for row in rows] == ["tentative", "phrase", ""]
    assert rows[1]["text"] == "phrase clear."


def test_lengthening_inside_partial_word_removes_only_prosody():
    text, _ = clean_text("w=- [2s-=2] sil=ver (Hx) <WH softly WH>")
    assert text == "w- s- silver softly"
    assert script["PARTIAL"].findall(text) == ["w-", "s-"]


@pytest.mark.parametrize(
    "source",
    [
        "0.00 1.00 Missing speaker.",
        "2.00 1.00 ALPHA: Invalid.",
        "0.00 1.00 ALPHA: <X unclosed",
        "0.00 1.00 ALPHA: stray X>",
        "0.00 1.00 ALPHA: <UNKNOWN unsupported UNKNOWN>",
    ],
)
def test_malformed_or_unknown_annotation_fails_instead_of_silently_dropping_words(source):
    with pytest.raises(ValueError):
        parse_trn(source)


def test_selection_preserves_whole_units_and_never_turns_them_into_gold_boundaries():
    rows = parse_trn("0.00 1.00 ALPHA: One.\n1.00 2.00 BETA: Two.")
    selected = script["select_window"](rows, Decimal(1), Decimal(2))
    assert selected[0]["sourceLine"] == 2
    assert selected[0]["start"] == 0 and selected[0]["end"] == 1
    assert "turns" not in selected[0]
    with pytest.raises(ValueError, match="clips"):
        script["select_window"](rows, Decimal("0.5"), Decimal(2))


def test_unselected_annotations_cannot_contribute_text_but_speaker_is_carried():
    rows = parse_trn(
        "0.00 1.00 ALPHA: unused >\n1.00 2.00 Selected.",
        lexical_window=(Decimal(1), Decimal(2)),
    )
    selected = script["select_window"](rows, Decimal(1), Decimal(2))
    assert selected[0]["sourceSpeaker"] == "ALPHA"
    assert selected[0]["text"] == "Selected."
    assert rows[0]["text"] == ""


def test_crop_records_nearest_sample_rounding_and_exact_selected_frames(tmp_path):
    source, target = tmp_path / "original.wav", tmp_path / "clip.wav"
    with wave.open(str(source), "wb") as audio:
        audio.setparams((1, 2, 10, 0, "NONE", "not compressed"))
        audio.writeframes(bytes(range(20)))
    frames = script["crop"](source, Decimal("0.15"), Decimal("0.55"), target)
    assert frames["firstFrame"] == 2 and frames["frameCount"] == 4
    assert frames["actualStart"] == 0.2 and frames["actualEnd"] == 0.6
    with wave.open(str(target), "rb") as clip:
        assert clip.readframes(4) == bytes(range(4, 12))


def test_source_hash_mismatch_prevents_output_and_model_free_preparation(tmp_path):
    audio, transcript, output = tmp_path / "wrong.wav", tmp_path / "wrong.trn", tmp_path / "out"
    audio.write_bytes(b"not the verified original")
    transcript.write_text("0.00 1.00 ALPHA: Invented.\n")
    with pytest.raises(ValueError, match="SHA-256"):
        script["prepare"](audio, transcript, output)
    assert not output.exists()
