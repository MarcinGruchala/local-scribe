"""Validated, versioned interchange contracts for local inference results."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator


class Options(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: Literal["auto", "en", "pl"] = "auto"
    profile: Literal["fast", "quality"] = "fast"
    diarization: bool = True
    speakerCount: int | None = Field(default=None, ge=1, le=10, strict=True)


class Timed(BaseModel):
    model_config = ConfigDict(extra="allow")

    start: FiniteFloat = Field(ge=0)
    end: FiniteFloat = Field(gt=0)

    @model_validator(mode="after")
    def positive_interval(self):
        if self.end <= self.start:
            raise ValueError("End must be greater than start.")
        return self


class Warning(BaseModel):
    code: str
    message: str


class Word(Timed):
    word: str
    speakerId: str | None = None
    overlap: bool = False


class ModelSegment(Timed):
    text: str
    # Raw word records also preserve diagnostics and missing timestamps.
    words: list[dict[str, Any]] | None = Field(default_factory=list)


class SpeakerTurn(Timed):
    speakerId: str


class Segment(Timed):
    id: str
    speakerId: str | None
    text: str
    editedText: str | None = None
    overlap: bool = False


class Speaker(BaseModel):
    id: str
    displayName: str


class Transcript(BaseModel):
    model_config = ConfigDict(extra="allow")

    schemaVersion: Literal[1] = 1
    jobId: str
    revision: int = Field(default=0, ge=0)
    duration: FiniteFloat = Field(gt=0)
    language: str | None
    requestedLanguage: Literal["auto", "en", "pl"]
    detectedLanguage: str | None
    options: Options
    originalText: str
    segments: list[Segment]
    speakers: list[Speaker]
    modelSegments: list[ModelSegment]
    words: list[Word]
    regularTurns: list[SpeakerTurn]
    exclusiveTurns: list[SpeakerTurn]
    warnings: list[Warning]
    provenance: dict[str, Any]
    stageTimings: dict[str, FiniteFloat] = Field(default_factory=dict)

    @model_validator(mode="after")
    def consistent_references(self):
        speaker_ids = [speaker.id for speaker in self.speakers]
        if len(speaker_ids) != len(set(speaker_ids)):
            raise ValueError("Speaker IDs must be unique.")
        segment_ids = [segment.id for segment in self.segments]
        if len(segment_ids) != len(set(segment_ids)):
            raise ValueError("Segment IDs must be unique.")
        for collection in (
            self.segments,
            self.modelSegments,
            self.words,
            self.regularTurns,
            self.exclusiveTurns,
        ):
            for item in collection:
                if item.end > self.duration:
                    raise ValueError("Timestamps must not exceed recording duration.")
                speaker_id = getattr(item, "speakerId", None)
                if speaker_id is not None and speaker_id not in speaker_ids:
                    raise ValueError("Speaker references must resolve within this transcript.")
        if any(value < 0 for value in self.stageTimings.values()):
            raise ValueError("Stage timings must be nonnegative.")
        return self
