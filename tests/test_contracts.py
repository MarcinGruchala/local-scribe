import pytest
from localscribe.alignment import assemble
from localscribe.contracts import Options, Transcript
from pydantic import ValidationError


@pytest.mark.parametrize(
    "options",
    [
        {"speakerCount": 0},
        {"speakerCount": 11},
        {"speakerCount": 2.5},
        {"speakerCount": True},
        {"language": "de"},
        {"profile": "unknown"},
        {"arbitrary": "option"},
    ],
)
def test_options_reject_unsupported_settings(options):
    with pytest.raises(ValidationError):
        Options.model_validate(options)


def test_full_contract_preserves_extra_engine_diagnostics_and_language():
    output = assemble(
        {
            "language": "pl",
            "text": "Cześć",
            "segments": [
                {
                    "start": 0,
                    "end": 1,
                    "text": "Cześć",
                    "avg_logprob": -0.1,
                    "words": [{"start": 0, "end": 1, "word": "Cześć", "probability": 0.9}],
                }
            ],
        },
        [],
        [],
        1,
        "job",
        {"language": "auto"},
    )
    validated = Transcript.model_validate(output)
    assert validated.requestedLanguage == "auto"
    assert validated.detectedLanguage == "pl"
    assert validated.model_dump()["words"][0]["probability"] == 0.9
    assert validated.model_dump()["modelSegments"][0]["avg_logprob"] == -0.1


def test_contract_rejects_invalid_speaker_references_and_durations():
    output = assemble({"segments": []}, [], [], 1, "job", {})
    output["segments"] = [{"id": "a", "start": 0, "end": 1, "speakerId": "missing", "text": "a"}]
    with pytest.raises(ValidationError, match="Speaker references"):
        Transcript.model_validate(output)
    output["segments"][0]["speakerId"] = None
    output["segments"][0]["end"] = 2
    with pytest.raises(ValidationError, match="duration"):
        Transcript.model_validate(output)
