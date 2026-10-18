"""Pure deterministic speaker assignment; no model or filesystem dependencies."""

import math
import re
from collections import defaultdict

from .contracts import Options, Transcript


def _interval(item: dict, duration: float) -> tuple[float, float]:
    start, end = float(item["start"]), float(item["end"])
    if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= duration):
        raise ValueError("Invalid timestamp interval.")
    return start, end


def _intersection(start: float, end: float, other: dict) -> float:
    return max(0.0, min(end, other["end"]) - max(start, other["start"]))


def _speaker(start: float, end: float, turns: list[dict]) -> str | None:
    candidates = [turn for turn in turns if _intersection(start, end, turn) > 0]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda turn: (-_intersection(start, end, turn), turn["start"], turn["speakerId"]),
    )["speakerId"]


def _overlap(start: float, end: float, turns: list[dict]) -> bool:
    intersecting = [turn for turn in turns if _intersection(start, end, turn) > 0]
    return any(
        left["speakerId"] != right["speakerId"]
        and max(start, left["start"], right["start"]) < min(end, left["end"], right["end"])
        for index, left in enumerate(intersecting)
        for right in intersecting[index + 1 :]
    )


def _join_words(words: list[dict]) -> str:
    result = ""
    for item in words:
        word = item["word"]
        if (
            result
            and word
            and not result[-1].isspace()
            and not word[0].isspace()
            and word[0] not in ",.!?;:)]}…"
            and result[-1] not in "([{"
        ):
            result += " "
        result += word
    return result.strip()


def assemble(
    asr: dict,
    regular: list[dict],
    exclusive: list[dict],
    duration: float,
    job_id: str,
    options: dict,
    warnings: list[dict] | None = None,
    provenance: dict | None = None,
) -> dict:
    settings = Options.model_validate(options).model_dump()
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Recording duration must be positive and finite.")
    notices = [dict(item) for item in warnings or []]
    enabled = settings["diarization"] and not any(
        item["code"] == "diarization_failed" for item in notices
    )
    raw_turns = (regular + exclusive) if enabled else []
    first_occurrence = defaultdict(lambda: math.inf)
    for turn in raw_turns:
        _interval(turn, duration)
        label = str(turn.get("speakerId", turn.get("speaker", "")))
        if not label:
            raise ValueError("Speaker turns require a speaker label.")
        first_occurrence[label] = min(first_occurrence[label], turn["start"])
    labels = sorted(first_occurrence, key=lambda label: (first_occurrence[label], label))
    mapping = {label: f"speaker_{index + 1}" for index, label in enumerate(labels)}

    def normalized(turns):
        return (
            sorted(
                [
                    {
                        **turn,
                        "start": float(turn["start"]),
                        "end": float(turn["end"]),
                        "originalSpeakerId": str(turn.get("speakerId", turn.get("speaker"))),
                        "speakerId": mapping[str(turn.get("speakerId", turn.get("speaker")))],
                    }
                    for turn in turns
                ],
                key=lambda turn: (turn["start"], turn["end"], turn["speakerId"]),
            )
            if enabled
            else []
        )

    regular_turns, exclusive_turns = normalized(regular), normalized(exclusive)
    segments, words, model_segments = [], [], []

    def display(start, end, text, speaker_id, overlap):
        segments.append(
            {
                "id": f"segment_{len(segments) + 1}",
                "start": start,
                "end": end,
                "speakerId": speaker_id,
                "text": text,
                "editedText": None,
                "overlap": overlap,
            }
        )

    raw_segments = asr.get("segments", [])
    if not raw_segments and asr.get("text", "").strip():
        raise ValueError("ASR text requires timestamped model segments.")
    for model_segment in raw_segments:
        start, end = _interval(model_segment, duration)
        original = dict(model_segment)
        original.setdefault("words", [])
        model_segments.append(original)
        text = model_segment["text"]
        candidate_words = model_segment.get("words") or []
        valid_words = bool(candidate_words)
        checked = []
        for raw_word in candidate_words:
            try:
                word_start, word_end = _interval(raw_word, duration)
                if not isinstance(raw_word["word"], str):
                    raise TypeError("Word text must be a string.")
                checked.append({**raw_word, "start": word_start, "end": word_end})
            except (KeyError, TypeError, ValueError):
                valid_words = False
        # Segment fallback also protects text omitted by incomplete word results.
        if re.sub(r"\s+", "", _join_words(checked)) != re.sub(r"\s+", "", text):
            valid_words = False
        for word in checked:
            word["speakerId"] = _speaker(word["start"], word["end"], exclusive_turns)
            word["overlap"] = _overlap(word["start"], word["end"], regular_turns)
            words.append(word)
        if not valid_words:
            notices.append(
                {
                    "code": "alignment_fallback",
                    "message": "Word timestamps are missing or incomplete; segment overlap was used.",
                }
            )
            display(
                start,
                end,
                text,
                _speaker(start, end, exclusive_turns),
                _overlap(start, end, regular_turns),
            )
            continue
        groups = []
        for word in checked:
            if not groups or groups[-1][0]["speakerId"] != word["speakerId"]:
                groups.append([])
            groups[-1].append(word)
        for group in groups:
            display(
                min(item["start"] for item in group),
                max(item["end"] for item in group),
                text if len(groups) == 1 else _join_words(group),
                group[0]["speakerId"],
                any(item["overlap"] for item in group),
            )
    if not segments:
        notices.append({"code": "empty_transcript", "message": "No speech was transcribed."})
    elif enabled and not raw_turns:
        notices.append(
            {
                "code": "no_speaker_turns",
                "message": "No speaker turns were detected. Review the transcript for possible spurious text.",
            }
        )
    # Repeated fallbacks are one actionable warning, rather than one per segment.
    notices = list({(item["code"], item["message"]): item for item in notices}.values())
    return Transcript.model_validate(
        {
            "schemaVersion": 1,
            "jobId": job_id,
            "revision": 0,
            "duration": duration,
            "language": asr.get("language"),
            "requestedLanguage": settings["language"],
            "detectedLanguage": asr.get("language") if settings["language"] == "auto" else None,
            "options": settings,
            "originalText": asr.get("text", "".join(item["text"] for item in model_segments)),
            "segments": segments,
            "speakers": [
                {"id": mapping[label], "displayName": f"Speaker {index + 1}"}
                for index, label in enumerate(labels)
            ],
            "modelSegments": model_segments,
            "words": words,
            "regularTurns": regular_turns,
            "exclusiveTurns": exclusive_turns,
            "warnings": notices,
            "provenance": provenance or {},
            "stageTimings": asr.get("stageTimings", {}),
        }
    ).model_dump()
