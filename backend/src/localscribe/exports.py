"""Exports always derive display text and names from one validated saved revision."""

import html
import json
from decimal import ROUND_HALF_UP, Decimal

from .contracts import Transcript


def _milliseconds(seconds: float) -> int:
    return int((Decimal(str(seconds)) * 1000).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _timestamp(milliseconds: int, separator: str) -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02}{separator}{millis:03}"


def render(transcript: dict, format: str, *, layout: str = "grouped") -> tuple[str, str]:
    if format not in {"txt", "srt", "vtt", "json"}:
        raise ValueError("Unsupported export format.")
    if layout not in {"grouped", "segmented"}:
        raise ValueError("Unsupported export layout.")
    saved = Transcript.model_validate(
        {k: v for k, v in transcript.items() if k != "grouping"}
    ).model_dump()
    grouping = transcript.get("grouping") if layout == "grouped" else None
    if format == "json":
        if grouping is not None:
            saved["schemaVersion"] = 2
            saved["grouping"] = grouping
        return json.dumps(saved, ensure_ascii=False, indent=2) + "\n", "application/json"
    speakers = {speaker["id"]: speaker["displayName"] for speaker in saved["speakers"]}
    cues = []
    # Subtitles always use source cues. Only readable TXT uses saved blocks.
    if format == "txt" and grouping is not None:
        segments = grouping["blocks"]
    else:
        segments = sorted(saved["segments"], key=lambda item: (item["start"], item["end"]))
    for segment in segments:
        text = (
            segment.get("editedText") if segment.get("editedText") is not None else segment["text"]
        )
        name = speakers.get(segment["speakerId"], "Unknown speaker")
        body = f"{name}: {text}".replace("\r\n", "\n").replace("\r", "\n")
        cues.append((segment, body))
    if format == "txt":
        notices = [f"Warning: {warning['message']}" for warning in saved["warnings"]]
        body = "\n\n".join(notices + [body for _, body in cues])
        return (body or "No speech was transcribed.") + "\n", "text/plain; charset=utf-8"
    blocks = []
    for index, (segment, body) in enumerate(cues, 1):
        start = _milliseconds(segment["start"])
        # Preserve a positive cue interval even for submillisecond model words.
        end = max(start + 1, _milliseconds(segment["end"]))
        separator = "," if format == "srt" else "."
        timing = f"{_timestamp(start, separator)} --> {_timestamp(end, separator)}"
        # Blank lines terminate cues. Escape markup so transcript text stays literal.
        body = "\n".join(line for line in html.escape(body).split("\n") if line.strip())
        blocks.append(f"{index}\n{timing}\n{body}\n")
    content = "\n".join(blocks)
    if format == "vtt":
        content = "WEBVTT\n\n" + content
        return content, "text/vtt; charset=utf-8"
    return content, "application/x-subrip; charset=utf-8"
