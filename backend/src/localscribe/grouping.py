"""Deterministic source-ID partitions; display blocks never replace source cues."""


def text(segment):
    edited = segment.get("editedText")
    return segment["text"] if edited is None else edited


def partitions(transcript):
    return [block["segmentIds"] for block in transcript["grouping"]["blocks"]]


def blocks(segments, groups):
    by_id = {segment["id"]: segment for segment in segments}
    result = []
    for ids in groups:
        source = [by_id[segment_id] for segment_id in ids]
        result.append(
            {
                "id": ids[0],
                "segmentIds": ids,
                "start": source[0]["start"],
                "end": source[-1]["end"],
                "speakerId": source[0]["speakerId"],
                "text": " ".join(text(segment).strip() for segment in source),
            }
        )
    return result


def ambiguous_segments(transcript):
    spans = []
    words = transcript.get("words", [])
    spans.extend((word["start"], word["end"]) for word in words if word.get("overlap"))
    # Source intervals are barriers even without word/turn overlap metadata.
    for name in ("segments", "words", "regularTurns", "exclusiveTurns"):
        ordered = sorted(transcript.get(name, []), key=lambda item: item["start"])
        for index, item in enumerate(ordered):
            for other_index in range(index + 1, len(ordered)):
                other = ordered[other_index]
                if other["start"] >= item["end"]:
                    break
                if name == "segments" or item.get("speakerId") != other.get("speakerId"):
                    spans.append((other["start"], min(item["end"], other["end"])))
    return {
        segment["id"]
        for segment in transcript["segments"]
        if segment.get("overlap")
        or any(segment["start"] < end and segment["end"] > start for start, end in spans)
    }


def propose(transcript, segment_ids=None):
    groups = []
    ambiguous = ambiguous_segments(transcript)
    source = transcript["segments"]
    ids = [segment["id"] for segment in source]
    start, stop = 0, len(ids)
    if segment_ids is not None:
        if not segment_ids or segment_ids[0] not in ids:
            raise ValueError("Select a nonempty contiguous ordered source range.")
        start = ids.index(segment_ids[0])
        stop = start + len(segment_ids)
        if ids[start:stop] != segment_ids:
            raise ValueError("Select a nonempty contiguous ordered source range.")
    source = source[start:stop]
    for index, segment in enumerate(source):
        previous = source[index - 1] if index else None
        group = groups[-1] if groups else []
        first = source[index - len(group)] if group else segment
        if (
            previous
            and previous["speakerId"] is not None
            and previous["id"] not in ambiguous
            and segment["id"] not in ambiguous
            and segment["id"] not in transcript["grouping"]["manualSplits"]
            and previous["speakerId"] == segment["speakerId"]
            and 0 <= segment["start"] - previous["end"] <= 2
            and segment["end"] - first["start"] <= 60
            and len(" ".join(text(s).strip() for s in source[index - len(group) : index + 1]))
            <= 1200
        ):
            group.append(segment["id"])
        else:
            groups.append([segment["id"]])
    left_ids, right_ids = set(ids[:start]), set(ids[stop:])
    left, right = [], []
    for group in partitions(transcript):
        before = [sid for sid in group if sid in left_ids]
        after = [sid for sid in group if sid in right_ids]
        if before:
            left.append(before)
        if after:
            right.append(after)
    return left + groups + right
