#!/usr/bin/env python3
"""Explicit public corpus download and reproducible Polish reference preparation.

Source: https://docs.pelcra.pl/doku.php?id=spokesbiz (CC BY-NC-ND 4.0).
No account, credentials, cookies, inference, or access-condition acceptance is used.
"""

import argparse
import csv
import hashlib
import io
import json
import struct
import urllib.parse
import urllib.request
import wave
import zlib
from pathlib import Path

FILE_ID = "1n7pgueKAylKwExzecXhdtauTI6rMzFug"
PUBLIC_URL = f"https://drive.usercontent.google.com/download?id={FILE_ID}&export=download&confirm=t"
SOURCE_PAGE = "https://docs.pelcra.pl/doku.php?id=spokesbiz"
PUBLIC_SAMPLE = f"https://drive.google.com/file/d/{FILE_ID}/view?usp=sharing"
ARCHIVE_BYTES = 761_372_269
ASSETS = {
    "csv": {
        "entry": "spokes_biz_rich_sample.csv",
        "offset": 757_893_087,
        "compressedBytes": 3_477_554,
        "bytes": 12_299_748,
        "sha256": "c5b034dfe5a2345560dfef4a4f128fa27b5528cfe9092856ed839b05c07d1e69",
    },
    "luz": {
        "entry": "CBIZ_LUZ_013/CBIZ_LUZ_013.wav",
        "offset": 164_527_484,
        "compressedBytes": 49_687_424,
        "bytes": 57_641_720,
        "crc32": "ff0d2e2b",
        "sha256": "53009ca3f99bfdc9378cb2af03c96618c14feef2acb0a7c53ac8ab1c2f83e209",
    },
    "bio": {
        "entry": "CBIZ_BIO_051/CBIZ_BIO_051.wav",
        "offset": 75,
        "compressedBytes": 79_012_775,
        "bytes": 120_076_366,
        "crc32": "0d606a2c",
        "sha256": "ccde9b5dfe8a99921b668ecebccf7d39eeff9f77e72a5e21feb8ee22d12c18bc",
    },
}


class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        if parsed.scheme != "https" or parsed.hostname not in {
            "drive.google.com",
            "drive.usercontent.google.com",
        }:
            raise ValueError("Public download redirected outside the fixed Google host allowlist.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: dict):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def download(root: Path, asset: str) -> dict:
    expected = ASSETS[asset]
    cap = expected["compressedBytes"] + 1024
    start, end = expected["offset"], expected["offset"] + cap - 1
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), PublicRedirect())
    request = urllib.request.Request(PUBLIC_URL, headers={"Range": f"bytes={start}-{end}"})
    with opener.open(request, timeout=30) as response:
        if response.status != 206:
            raise ValueError(
                "Public source did not honor Range; full archive download was prevented."
            )
        if response.headers.get("Content-Range") != f"bytes {start}-{end}/{ARCHIVE_BYTES}":
            raise ValueError("Public archive size or requested range has changed.")
        packed = response.read(cap + 1)
        if len(packed) != cap:
            raise ValueError("Public response exceeds the fixed bound or is incomplete.")
    header = struct.unpack_from("<4s5H3L2H", packed)
    if header[0] != b"PK\x03\x04" or header[3] != 8:
        raise ValueError("Expected deflated ZIP entry is absent.")
    name = packed[30 : 30 + header[9]].decode("utf-8")
    if name != expected["entry"]:
        raise ValueError("Archive entry name differs from the recorded public sample.")
    offset = 30 + header[9] + header[10]
    decoder = zlib.decompressobj(-15)
    content = decoder.decompress(
        packed[offset : offset + expected["compressedBytes"]], expected["bytes"] + 1
    )
    if (
        not decoder.eof
        or len(content) != expected["bytes"]
        or sha256(content) != expected["sha256"]
    ):
        raise ValueError("Public asset size or immutable SHA-256 validation failed.")
    crc = f"{zlib.crc32(content):08x}"
    if expected.get("crc32", crc) != crc:
        raise ValueError("WAV ZIP CRC validation failed.")
    target = root / Path(name).name
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.chmod(0o600)
    temporary.replace(target)
    result = {
        "fileId": FILE_ID,
        "name": name,
        "bytesRead": len(packed),
        "bytes": len(content),
        "sha256": sha256(content),
        "zipCrc32": crc,
        "compressedRangeSha256": sha256(packed),
        "sourcePage": SOURCE_PAGE,
        "publicSampleUrl": PUBLIC_SAMPLE,
        "license": "CC BY-NC-ND 4.0",
    }
    if asset != "csv":
        with wave.open(io.BytesIO(content)) as audio:
            result.update(
                durationSeconds=audio.getnframes() / audio.getframerate(),
                sampleRate=audio.getframerate(),
                channels=audio.getnchannels(),
                sampleWidth=audio.getsampwidth(),
            )
    write_json(root / f"public-{asset}-source-manifest.json", result)
    return result


def build_reference(rows: list[dict], csv_sha: str, wav_sha: str) -> dict:
    selected = [
        row
        for row in rows
        if row["recording_id"] == "CBIZ_LUZ_013"
        and float(row["segment_ts_start_ms"]) >= 0
        and float(row["segment_ts_end_ms"]) <= 582590
    ]
    selected.sort(key=lambda row: int(row["segment_seq"]))
    speakers = {}
    for row in selected:
        start, end = float(row["segment_ts_start_ms"]), float(row["segment_ts_end_ms"])
        if not 0 <= start < end <= 582590:
            raise ValueError("Selected reference segments require valid millisecond intervals.")
        speakers.setdefault(row["speaker_id"], f"ref_{len(speakers) + 1}")
    if len(speakers) != 2:
        raise ValueError("The predeclared reference must contain exactly two speakers.")
    return {
        "text": " ".join(row["segment_text"] for row in selected),
        "turns": [
            {
                "start": float(row["segment_ts_start_ms"]) / 1000,
                "end": float(row["segment_ts_end_ms"]) / 1000,
                "speakerId": speakers[row["speaker_id"]],
            }
            for row in selected
        ],
        "metadata": {
            "recordingId": "CBIZ_LUZ_013",
            "sourceWindowSeconds": {"start": 0, "end": 582.59},
            "selectionPolicy": "Predeclared first whole-segment window, selected without model predictions.",
            "textReferenceStatus": "human_corrected_corpus_text",
            "speakerReferenceStatus": "automatically_realigned_not_independently_audited",
            "speakerAttributionGateEligible": False,
            "sourcePage": SOURCE_PAGE,
            "license": "CC BY-NC-ND 4.0",
            "csvSha256": csv_sha,
            "originalWavSha256": wav_sha,
            "timestampUnits": "Source CSV milliseconds converted to seconds.",
            "sourceSegmentIds": [row["segment_id"] for row in selected],
            "sourceSpeakerMapping": speakers,
            "sourceSegmentWordCount": sum(int(row["segment_word_count"]) for row in selected),
        },
    }


def prepare_pl(root: Path) -> dict:
    csv_path, source = root / "spokes_biz_rich_sample.csv", root / "CBIZ_LUZ_013.wav"
    csv_sha, wav_sha = sha256(csv_path.read_bytes()), sha256(source.read_bytes())
    if csv_sha != ASSETS["csv"]["sha256"] or wav_sha != ASSETS["luz"]["sha256"]:
        raise ValueError("Preparation requires the verified original public CSV and LUZ recording.")
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        prefix = handle.read(8192)
        handle.seek(0)
        rows = list(csv.DictReader(handle, delimiter=csv.Sniffer().sniff(prefix).delimiter))
    reference = build_reference(rows, csv_sha, wav_sha)
    reference_path = root / "pl-luz-000000-582590-reference.json"
    write_json(reference_path, reference)
    clip = root / "pl-luz-000000-582590.wav"
    temporary = clip.with_suffix(".tmp.wav")
    with wave.open(str(source)) as audio:
        rate = audio.getframerate()
        frames = round(582.59 * rate)
        with wave.open(str(temporary), "wb") as output:
            output.setparams(audio.getparams())
            output.writeframes(audio.readframes(frames))
    temporary.chmod(0o600)
    temporary.replace(clip)
    result = {
        "clip": str(clip),
        "reference": str(reference_path),
        "durationSeconds": frames / rate,
        "segments": len(reference["turns"]),
        "speakers": 2,
        "wordCount": reference["metadata"]["sourceSegmentWordCount"],
        "referenceSha256": sha256(reference_path.read_bytes()),
        "clipSha256": sha256(clip.read_bytes()),
        "textReferenceStatus": reference["metadata"]["textReferenceStatus"],
        "speakerReferenceStatus": reference["metadata"]["speakerReferenceStatus"],
    }
    write_json(root / "pl-luz-000000-582590-manifest.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("download", "prepare-pl"))
    parser.add_argument("--asset", choices=ASSETS, default="luz")
    parser.add_argument(
        "--root", type=Path, required=True, help="External directory; never the repository"
    )
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    if root.is_relative_to(Path(__file__).resolve().parents[1]):
        parser.exit(1, "Corpus recordings and references must remain outside the repository.\n")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        result = download(root, args.asset) if args.action == "download" else prepare_pl(root)
    except (OSError, ValueError, KeyError, csv.Error, zlib.error, struct.error, wave.Error):
        parser.exit(
            1,
            "Public reference preparation failed. Check public-source availability and verified local assets. No access conditions were accepted.\n",
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
