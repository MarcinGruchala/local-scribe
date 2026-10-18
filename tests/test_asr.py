"""Adapter checks run without importing MLX, downloading weights, or using a GPU."""

import sys
from types import ModuleType
from unittest.mock import Mock

import pytest
from localscribe.engines import asr_mlx


@pytest.mark.parametrize("requested,expected", [("auto", None), ("en", "en"), ("pl", "pl")])
def test_adapter_uses_local_original_language_word_timestamps_and_releases_cache(
    monkeypatch, tmp_path, requested, expected
):
    snapshot = tmp_path / "immutable-snapshot"
    snapshot.mkdir()
    monkeypatch.setattr(asr_mlx, "digital_silence", lambda _: False)
    monkeypatch.setattr(asr_mlx, "local_path", Mock(return_value=snapshot))
    monkeypatch.setattr(asr_mlx, "inspect", Mock(return_value={"revision": "sha"}))
    monkeypatch.setattr(asr_mlx.importlib.metadata, "version", lambda _: "test-version")
    mlx = ModuleType("mlx")
    mx = ModuleType("mlx.core")
    mx.clear_cache = Mock()
    mlx.core = mx
    whisper = ModuleType("mlx_whisper")
    whisper.transcribe = Mock(return_value={"language": requested, "segments": [], "text": ""})
    implementation = ModuleType("mlx_whisper.transcribe")

    class Holder:
        model = object()

    implementation.ModelHolder = Holder
    for name, module in {
        "mlx": mlx,
        "mlx.core": mx,
        "mlx_whisper": whisper,
        "mlx_whisper.transcribe": implementation,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    output = asr_mlx.transcribe(tmp_path / "audio.wav", tmp_path, "fast", requested)
    kwargs = whisper.transcribe.call_args.kwargs
    assert kwargs["path_or_hf_repo"] == str(snapshot)
    assert kwargs["task"] == "transcribe"
    assert kwargs["language"] == expected
    assert kwargs["word_timestamps"] is True
    assert kwargs["condition_on_previous_text"] is False
    assert output["provenance"]["asr"]["revision"] == "sha"
    assert output["provenance"]["asr"]["version"] == "test-version"
    assert output["stageTimings"]["asr"] >= 0
    assert Holder.model is None
    mx.clear_cache.assert_called_once()


def test_only_exact_digital_silence_skips_inference(tmp_path, monkeypatch):
    import wave

    path = tmp_path / "silence.wav"
    with wave.open(str(path), "wb") as stream:
        stream.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        stream.writeframes(b"\0\0" * 32000)
    assert asr_mlx.digital_silence(path)
    monkeypatch.setattr(asr_mlx, "local_path", lambda *args: tmp_path)
    monkeypatch.setattr(asr_mlx, "inspect", lambda *args: {"revision": "test-sha"})
    monkeypatch.setattr(asr_mlx.importlib.metadata, "version", lambda _: "test-version")
    result = asr_mlx.transcribe(path, tmp_path, "fast", "auto")
    assert result["segments"] == []
    assert result["text"] == ""
    assert result["provenance"]["asr"]["status"] == "skipped_digital_silence"
    with wave.open(str(path), "wb") as stream:
        stream.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        stream.writeframes(b"\0\0" * 31999 + b"\x01\0")
    assert not asr_mlx.digital_silence(path), (
        "Even one quiet nonzero PCM sample must remain eligible for model inference."
    )
