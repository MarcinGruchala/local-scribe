"""Sequential stages and degraded results at the actual child contract boundary."""

import json
import wave

import pytest
from localscribe import pipeline


def request(tmp_path, diarization=True):
    return {
        "options": {"diarization": diarization},
        "source": str(tmp_path / "source.wav"),
        "attempt_dir": str(tmp_path / "attempt"),
        "model_root": str(tmp_path / "models"),
        "jobId": "test-job",
        "normalized": str(tmp_path / "normalized.wav"),
    }


def fake_normalize(source, target):
    with wave.open(str(target), "wb") as out:
        out.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        out.writeframes(b"\0\0" * 32000)


def test_diarization_failure_keeps_original_asr_and_unknown_labels(tmp_path, monkeypatch):
    order = []
    monkeypatch.setattr(pipeline, "normalize", fake_normalize)

    def asr(*args):
        order.append("asr")
        return {
            "text": "Hello",
            "language": "en",
            "segments": [
                {
                    "start": 0,
                    "end": 1,
                    "text": "Hello",
                    "words": [{"start": 0, "end": 1, "word": "Hello"}],
                }
            ],
        }

    def speaker(*args):
        order.append("speaker")
        raise RuntimeError("private path must not leak")

    monkeypatch.setattr(pipeline, "transcribe", asr)
    monkeypatch.setattr(pipeline, "diarize", speaker)
    output = tmp_path / "result.json"
    pipeline.run(request(tmp_path), output)
    value = json.loads(output.read_text())
    assert order == ["asr", "speaker"]
    assert value["segments"][0]["text"] == "Hello"
    assert value["segments"][0]["speakerId"] is None
    assert value["warnings"][0]["code"] == "diarization_failed"
    assert "private path" not in output.read_text()


def test_disabled_diarization_is_intentional_and_empty_asr_has_notice(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "normalize", fake_normalize)
    monkeypatch.setattr(
        pipeline, "transcribe", lambda *args: {"text": "", "language": "pl", "segments": []}
    )
    monkeypatch.setattr(
        pipeline, "diarize", lambda *args: pytest.fail("Disabled diarization was called")
    )
    output = tmp_path / "result.json"
    pipeline.run(request(tmp_path, False), output)
    value = json.loads(output.read_text())
    assert value["provenance"]["diarization"]["status"] == "disabled"
    assert {w["code"] for w in value["warnings"]} == {"empty_transcript"}


def test_changed_snapshot_fails_before_decoding_or_model_inference(tmp_path, monkeypatch):
    from localscribe.models import ModelRevisionError

    current = request(tmp_path)
    current["job"] = {
        "modelSettings": {
            "fast": {"repo": "mlx-community/whisper-large-v3-turbo", "revision": "a" * 40}
        }
    }
    monkeypatch.setattr(
        pipeline,
        "normalize",
        lambda *args: pytest.fail("Changed models must fail before work starts"),
    )
    with pytest.raises(ModelRevisionError, match="original model snapshots"):
        pipeline.run(current, tmp_path / "result.json")
    assert not (tmp_path / "result.json").exists()
