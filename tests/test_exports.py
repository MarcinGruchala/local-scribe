import io
import json

import pytest
import srt
import webvtt
from localscribe.alignment import assemble
from localscribe.exports import render


def transcript():
    turns = [{"start": 0, "end": 65, "speaker": "A"}]
    output = assemble(
        {
            "language": "pl",
            "text": "Original model text",
            "segments": [
                {"start": 59.9995, "end": 61.001, "text": "Original model text", "words": []},
                {"start": 62, "end": 63, "text": "Erase this", "words": []},
            ],
        },
        turns,
        turns,
        65,
        "job",
        {"language": "pl"},
        provenance={"revision": "sha"},
    )
    output["revision"] = 7
    output["speakers"][0]["displayName"] = "Marcin"
    output["segments"][0]["editedText"] = "Zażółć gęślą jaźń\n\nSecond line <literal>"
    output["segments"][1]["editedText"] = ""
    return output


def test_txt_exports_saved_edits_names_and_intentional_empty_edit():
    text, mime = render(transcript(), "txt")
    assert "Marcin: Zażółć gęślą jaźń" in text
    assert "Marcin: \n" in text
    assert "Original model text" not in text
    assert "Erase this" not in text
    assert mime == "text/plain; charset=utf-8"


@pytest.mark.parametrize("format", ["srt", "vtt"])
def test_independent_subtitle_parsers_accept_rounded_unicode_multiline_edits(format):
    content, _ = render(transcript(), format)
    if format == "srt":
        cues = list(srt.parse(content))
        assert cues[0].start.total_seconds() == 60
        assert cues[0].end.total_seconds() == 61.001
        text = cues[0].content
    else:
        cues = list(webvtt.from_buffer(io.StringIO(content)))
        assert cues[0].start == "00:01:00.000"
        assert cues[0].end == "00:01:01.001"
        text = cues[0].raw_text
        assert content.startswith("WEBVTT\n\n")
    assert len(cues) == 2
    assert "Marcin: Zażółć gęślą jaźń" in text
    assert "Second line &lt;literal&gt;" in text
    assert "Erase this" not in content


def test_json_preserves_inference_and_separate_saved_edits():
    content, mime = render(transcript(), "json")
    output = json.loads(content)
    assert output["schemaVersion"] == 1
    assert output["revision"] == 7
    assert output["segments"][0]["text"] == "Original model text"
    assert output["segments"][0]["editedText"].startswith("Zażółć")
    assert output["segments"][1]["editedText"] == ""
    for key in (
        "modelSegments",
        "words",
        "regularTurns",
        "exclusiveTurns",
        "warnings",
        "language",
        "requestedLanguage",
        "detectedLanguage",
        "options",
        "provenance",
    ):
        assert key in output
    assert mime == "application/json"


def test_empty_transcript_has_valid_defined_exports():
    output = assemble({"segments": []}, [], [], 1, "job", {})
    assert "No speech was transcribed" in render(output, "txt")[0]
    assert list(srt.parse(render(output, "srt")[0])) == []
    assert list(webvtt.from_buffer(io.StringIO(render(output, "vtt")[0]))) == []
    assert json.loads(render(output, "json")[0])["segments"] == []


def test_degraded_transcript_exports_unknown_speaker_and_warning():
    output = transcript()
    output["speakers"] = []
    output["regularTurns"] = output["exclusiveTurns"] = []
    for segment in output["segments"]:
        segment["speakerId"] = None
    output["warnings"] = [{"code": "diarization_failed", "message": "Diarization failed."}]
    assert "Unknown speaker: Zażółć" in render(output, "txt")[0]
    assert "Diarization failed." in render(output, "txt")[0]


def test_submillisecond_words_keep_positive_subtitle_duration():
    output = transcript()
    output["segments"][0]["start"] = 0.0001
    output["segments"][0]["end"] = 0.0002
    cue = next(iter(srt.parse(render(output, "srt")[0])))
    assert cue.end > cue.start


def test_unsupported_export_is_rejected():
    with pytest.raises(ValueError, match="Unsupported"):
        render(transcript(), "html")
