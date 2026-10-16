#!/usr/bin/env python3
"""Prepare the predeclared SBC005 English reference from verified external originals.

No downloads, credentials, model predictions, or access-condition acceptance.
Adapted media and corpus text must remain outside the repository (CC BY-ND 3.0 US).
"""

import argparse
import hashlib
import json
import re
import subprocess
import wave
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
START, END = Decimal("374.19"), Decimal("675.08")
AUDIO_SHA256 = "cc65cf2abb89036fcbd57da0691ded3c1a062721c99bc4bda538cd1cba55a7fb"
TRN_SHA256 = "3c537a69be481e8e96add188437211c4c6a767ddb9f8de106ae5503a689f5e51"
SOURCE_PAGE = (
    "https://www.linguistics.ucsb.edu/research/santa-barbara-corpus-spoken-american-english"
)
TRANSCRIPT_URL = (
    "https://www.linguistics.ucsb.edu/sites/default/files/sitefiles/research/SBC/SBC005.trn"
)
AUDIO_URL = "https://ucsb.app.box.com/s/0wadkhacf960exb0kc59pn4lh159pcmb"
MANUAL_URL = (
    "https://linguistics.ucsb.edu/sites/default/files/sitefiles/research/papers/"
    "Working%20Papers%20Vol%204.pdf"
)
SCOPES = "YWN|MRC|VOX|WH|HI|LO|PAR|ARH|BR|CRY|Q|P|F|W|A|L|X"
OPEN_SCOPE = re.compile(r"<(" + SCOPES + r")(?=\s|<|$)")
CLOSE_SCOPE = re.compile(r"(?<![A-Za-z0-9])(" + SCOPES + r")>")
UNCERTAINTY = re.compile(r"<X(?=\s|<|$)|(?<![A-Za-z0-9])X>")
PARTIAL = re.compile(r"\b[A-Za-z]+-(?!-)")


def remove_overlap_indices(text: str) -> str:
    """Indices touch lexical tokens: [2X2] denotes X, not the word X2."""
    return re.sub(r"\[\d*|\d*\]", "", text)


def clean_text(raw: str) -> tuple[str, dict]:
    """Remove transcription metadata while preserving enclosed lexical content."""
    text = remove_overlap_indices(raw)
    events = []
    while re.search(r"\([^()]*\)", text):
        events.extend(re.findall(r"\(([^()]*)\)", text))
        text = re.sub(r"\([^()]*\)", " ", text)
    scopes = OPEN_SCOPE.findall(text)
    text = OPEN_SCOPE.sub("", text)
    text = CLOSE_SCOPE.sub("", text)
    text = text.replace("<@", "").replace("@>", "").replace("<%", "").replace("%>", "")
    # Lengthening/laughter symbols can occur inside words or incomplete words.
    text = re.sub(r"[=@%~!]", "", text)
    text = re.sub(r"\.{2,}", " ", text)
    text = " ".join(text.split())
    if re.search(r"[<>\[\]()@=%~]", text):
        raise ValueError("Unsupported or unbalanced transcription metadata.")
    source_partials = PARTIAL.findall(remove_overlap_indices(raw).replace("=", ""))
    if source_partials != PARTIAL.findall(text):
        raise ValueError("Incomplete lexical words changed during metadata removal.")
    return text, {
        "parentheticalEvents": events,
        "scopeLabels": scopes,
        "overlapMarked": "[" in raw or "]" in raw,
        "nonLexicalOnly": not bool(re.search(r"[A-Za-z]", text)),
    }


def parse_trn(source: str, lexical_window: tuple[Decimal, Decimal] | None = None) -> list[dict]:
    """Carry labels/scopes globally; normalize lexical annotations only in the window.

    The verified full source also has an unmatched non-uncertainty delimiter outside
    the predeclared case. Unselected units cannot contribute reference text.
    """
    rows, speaker, active = [], None, False
    for number, line in enumerate(source.splitlines(), 1):
        match = re.fullmatch(r"\s*([0-9.]+)\s+([0-9.]+)\s+(?:([A-Z0-9_]+):\s*)?(.*?)\s*", line)
        if not match:
            raise ValueError(f"Invalid TRN syntax at source line {number}.")
        left, right, label, raw = match.groups()
        speaker = label or speaker
        left, right = Decimal(left), Decimal(right)
        if speaker is None or left < 0 or right < left:
            raise ValueError(f"Invalid speaker or interval at source line {number}.")
        body = remove_overlap_indices(raw)
        uncertain_parts, cursor, row_uncertain = [], 0, active
        for marker in UNCERTAINTY.finditer(body):
            if active:
                uncertain_parts.append(body[cursor : marker.start()])
            opening = marker.group().startswith("<")
            if opening == active:
                raise ValueError("Unbalanced uncertainty scope.")
            active, row_uncertain, cursor = opening, True, marker.end()
        if active:
            uncertain_parts.append(body[cursor:])
        selected = lexical_window is None or (
            left < lexical_window[1] and right > lexical_window[0]
        )
        text, removed = clean_text(raw) if selected else ("", {})
        best_guess = (
            clean_text(" ".join(uncertain_parts))[0] if selected and uncertain_parts else ""
        )
        rows.append(
            {
                "sourceLine": number,
                "sourceStart": float(left),
                "sourceEnd": float(right),
                "sourceSpeaker": speaker,
                "sourceText": raw,
                "text": text,
                "metadataRemoved": removed,
                "uncertainHearing": row_uncertain,
                "retainedBestGuess": best_guess,
                "indecipherableTokens": re.findall(r"\bX+\b", text),
                "alternativeHearing": bool(re.search(r"_/|/[^\s/]+/", body)),
            }
        )
    if active:
        raise ValueError("Unclosed uncertainty scope.")
    return rows


def select_window(rows: list[dict], start=START, end=END) -> list[dict]:
    selected = []
    for source_row in rows:
        left, right = Decimal(str(source_row["sourceStart"])), Decimal(str(source_row["sourceEnd"]))
        if left >= end or right <= start:
            continue
        if left < start or right > end or left == right:
            raise ValueError("Window clips an intonation unit or includes an empty interval.")
        selected.append(dict(source_row, start=float(left - start), end=float(right - start)))
    return selected


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024**2), b""):
            value.update(chunk)
    return value.hexdigest()


def write_json(path: Path, value: dict):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    path.chmod(0o600)


def crop(source: Path, start: Decimal, end: Decimal, target: Path) -> dict:
    with wave.open(str(source), "rb") as audio:
        rate = audio.getframerate()
        first = int((start * rate).to_integral_value(rounding=ROUND_HALF_UP))
        last = int((end * rate).to_integral_value(rounding=ROUND_HALF_UP))
        if last > audio.getnframes():
            raise ValueError("Source WAV is shorter than the predeclared window.")
        audio.setpos(first)
        with wave.open(str(target), "wb") as output:
            output.setparams(audio.getparams())
            remaining = last - first
            while remaining:
                frames = min(remaining, 16384)
                data = audio.readframes(frames)
                if len(data) != frames * audio.getnchannels() * audio.getsampwidth():
                    raise ValueError("Incomplete source WAV frames.")
                output.writeframes(data)
                remaining -= frames
    target.chmod(0o600)
    return {
        "firstFrame": first,
        "frameCount": last - first,
        "sampleRate": rate,
        "actualStart": first / rate,
        "actualEnd": last / rate,
        "rounding": "Nearest sample frame, half up; at most half a source sample difference.",
    }


def prepare(audio: Path, transcript: Path, root: Path) -> dict:
    audio, transcript, root = (path.expanduser().resolve() for path in (audio, transcript, root))
    if any(path.is_relative_to(REPOSITORY) for path in (audio, transcript, root)):
        raise ValueError(
            "Corpus originals and prepared artifacts must remain outside the repository."
        )
    if sha256(audio) != AUDIO_SHA256 or sha256(transcript) != TRN_SHA256:
        raise ValueError("Original SBC005 WAV/TRN SHA-256 verification failed.")
    rows = select_window(parse_trn(transcript.read_text(), lexical_window=(START, END)))
    if len(rows) != 191 or [rows[0]["sourceLine"], rows[-1]["sourceLine"]] != [239, 429]:
        raise ValueError("Predeclared complete intonation units differ from the audited source.")
    if any(row["indecipherableTokens"] or row["alternativeHearing"] for row in rows):
        raise ValueError("Selected source contains indecipherable or alternative-hearing tokens.")
    uncertain = [row for row in rows if row["uncertainHearing"]]
    if [row["sourceLine"] for row in uncertain] != [252, 326]:
        raise ValueError("Predeclared uncertainty metadata differs from the audited source.")
    mapping = {
        label: f"reference_speaker_{i + 1}"
        for i, label in enumerate(dict.fromkeys(row["sourceSpeaker"] for row in rows))
    }
    if len(mapping) != 2:
        raise ValueError("The predeclared case must contain exactly two speakers.")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if any(root.iterdir()):
        raise ValueError("Use an empty external output directory to avoid overwriting artifacts.")
    root.chmod(0o700)
    for row in rows:
        row["speakerId"] = mapping[row["sourceSpeaker"]]
    original = root / "sbc005-en-374.19-675.08-original.wav"
    normalized = root / "sbc005-en-300.89s.wav"
    reference_path = root / "sbc005-en-300.89s-reference.json"
    frames = crop(audio, START, END, original)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-n",
            "-i",
            str(original),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(normalized),
        ],
        check=True,
        capture_output=True,
    )
    normalized.chmod(0o600)
    with wave.open(str(normalized), "rb") as result:
        duration = result.getnframes() / result.getframerate()
        if (result.getnchannels(), result.getframerate(), result.getsampwidth()) != (1, 16000, 2):
            raise ValueError("Normalized WAV must be mono 16 kHz PCM16.")
        if abs(duration - float(END - START)) > 1 / 16000:
            raise ValueError("Normalized audio duration differs from the predeclared window.")
    audits = []
    for row in uncertain:
        left, right = Decimal(str(row["sourceStart"])), Decimal(str(row["sourceEnd"]))
        path = root / f"sbc005-uncertain-line{row['sourceLine']}-{left:.2f}-{right:.2f}.wav"
        source_frames = crop(audio, left, right, path)
        audits.append(
            {
                "path": str(path),
                "sha256": sha256(path),
                "sourceLine": row["sourceLine"],
                "sourceStart": float(left),
                "sourceEnd": float(right),
                "duration": float(right - left),
                "sourceFrames": source_frames,
                "resolvedByNewHumanReview": False,
            }
        )
    partials = [
        {"sourceLine": row["sourceLine"], "token": token}
        for row in rows
        for token in PARTIAL.findall(row["text"])
    ]
    reference = {
        "schemaVersion": 1,
        "language": "en",
        "duration": duration,
        "text": " ".join(row["text"] for row in rows if row["text"]),
        "turns": [],
        "intonationUnits": rows,
        "referenceType": "published_manual_lexical_candidate",
        "textReferenceStatus": "Two uncertain hearing spans retained; pending targeted human audit.",
        "speakerReferenceStatus": "Not gold: intonation-unit times include pauses and non-speech.",
        "speakerAttributionGateEligible": False,
        "uncertainties": [
            {
                key: row[key]
                for key in (
                    "sourceLine",
                    "sourceStart",
                    "sourceEnd",
                    "start",
                    "end",
                    "retainedBestGuess",
                )
            }
            | {"resolvedByNewHumanReview": False, "timingPrecision": "whole intonation unit"}
            for row in uncertain
        ],
        "indecipherableUnits": [],
        "truncatedWordTokensRetained": partials,
        "predeclaredCase": {
            "selectedBeforeAnyModelPrediction": True,
            "selectionBasis": "Complete source units, two speakers, no indecipherable tokens; source annotations only.",
            "parserCorrection": "Remove overlap indices before unknown-token detection: [2X2] denotes X.",
            "abandonedCandidate": {
                "start": 419.44,
                "end": 719.88,
                "reason": "Parser correction found an indecipherable token at source line433; never scored for selection.",
            },
        },
        "normalization": {
            "sourceOrder": "Original TRN line order, including overlapping utterances.",
            "removed": "Nonlinguistic events, scope delimiters, overlap indices, lengthening, laughter/glottal symbols, pause marks.",
            "preserved": "Enclosed words, author best guesses, fillers, repetitions, incomplete word tokens.",
            "lexicalRegularization": False,
            "modelPredictionsUsed": False,
        },
        "source": {
            "recording": "SBC005",
            "officialPage": SOURCE_PAGE,
            "canonicalAudio": AUDIO_URL,
            "transcriptUrl": TRANSCRIPT_URL,
            "transcriptionManual": MANUAL_URL,
            "audioSha256": AUDIO_SHA256,
            "transcriptSha256": TRN_SHA256,
            "start": float(START),
            "end": float(END),
            "sourceFrames": frames,
        },
        "license": {
            "name": "CC BY-ND 3.0 US",
            "url": "https://creativecommons.org/licenses/by-nd/3.0/us/",
            "use": "Local private evaluation only; adapted excerpt/reference not redistributed.",
        },
        "audio": {
            "path": str(normalized),
            "sha256": sha256(normalized),
            "channels": 1,
            "sampleRate": 16000,
            "sampleWidthBytes": 2,
        },
        "auditClips": audits,
    }
    write_json(reference_path, reference)
    summary = {
        "candidateAudio": str(normalized),
        "candidateReference": str(reference_path),
        "sourceStart": float(START),
        "sourceEnd": float(END),
        "duration": duration,
        "intonationUnits": len(rows),
        "unitsBySpeaker": dict(Counter(r["speakerId"] for r in rows)),
        "uncertainHearingSpans": len(uncertain),
        "indecipherableRows": 0,
        "truncatedWordTokensRetained": len(partials),
        "goldSpeakerTurns": 0,
        "audioSha256": reference["audio"]["sha256"],
        "referenceSha256": sha256(reference_path),
        "auditClips": [
            {key: audit[key] for key in ("path", "sha256", "duration")} for audit in audits
        ],
    }
    write_json(root / "sbc005-primary-candidate-summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", required=True, type=Path, help="Verified external original WAV")
    parser.add_argument(
        "--transcript", required=True, type=Path, help="Verified external original TRN"
    )
    parser.add_argument("--output-root", required=True, type=Path, help="Empty external directory")
    args = parser.parse_args()
    try:
        result = prepare(args.audio, args.transcript, args.output_root)
    except (OSError, ValueError, wave.Error, subprocess.SubprocessError) as error:
        parser.exit(1, f"Reference preparation failed: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
