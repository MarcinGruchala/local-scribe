"""Download two pinned, public FLEURS human-speech compatibility samples outside Git.

The dataset viewer is currently unavailable. Stream each official test audio archive
only until its first manifest-matched WAV, then close it without downloading the rest.
These single-utterance samples are not representative release quality references.
"""

import argparse
import hashlib
import json
import os
import tarfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPOSITORY = "google/fleurs"
REVISION = "70bb2e84b976b7e960aa89f1c648e09c59f894dd"
SOURCE = f"https://huggingface.co/datasets/{REPOSITORY}/resolve/{REVISION}/data"
DATASET_CARD = "https://huggingface.co/datasets/google/fleurs"
LICENSE = "CC-BY-4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
LANGUAGES = {"pl": "pl_pl", "en": "en_us"}
MAX_MANIFEST_BYTES = 2 * 1024**2
MAX_ARCHIVE_BYTES = 16 * 1024**2
MAX_AUDIO_BYTES = 8 * 1024**2
ALLOWED_HOSTS = {
    "huggingface.co",
    "cdn-lfs.huggingface.co",
    "cdn-lfs-us-1.huggingface.co",
    "cdn-lfs-eu-1.huggingface.co",
    "cas-bridge.xethub.hf.co",
    "us.aws.cdn.hf.co",
}


class PublicRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlparse(newurl)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
            raise ValueError("The public dataset redirected outside its approved hosts.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class BoundedReader:
    def __init__(self, source, maximum):
        self.source, self.maximum, self.count = source, maximum, 0

    def read(self, size=-1):
        remaining = self.maximum - self.count
        if remaining <= 0:
            raise ValueError("The bounded archive transfer limit was reached.")
        block = self.source.read(min(size if size >= 0 else remaining, remaining))
        self.count += len(block)
        return block


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def save_private(path, data):
    temporary = path.with_name(path.name + ".partial")
    try:
        with temporary.open("wb") as handle:
            os.chmod(temporary, 0o600)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def download_sample(opener, output, language, config):
    manifest_url = f"{SOURCE}/{config}/test.tsv"
    audio_url = f"{SOURCE}/{config}/audio/test.tar.gz"
    with opener.open(manifest_url, timeout=60) as response:
        manifest = response.read(MAX_MANIFEST_BYTES + 1)
    if len(manifest) > MAX_MANIFEST_BYTES:
        raise ValueError("The dataset manifest exceeds its expected size limit.")
    rows = {}
    # FLEURS uses literal tab-separated fields; embedded quotation marks are text.
    for line in manifest.decode("utf-8").splitlines():
        row = line.split("\t")
        if len(row) != 7 or not row[0].isdigit() or not row[5].isdigit():
            raise ValueError("The pinned dataset manifest has an unexpected schema.")
        rows[row[1]] = row
    selected = None
    with opener.open(audio_url, timeout=60) as response:
        bounded = BoundedReader(response, MAX_ARCHIVE_BYTES)
        with tarfile.open(fileobj=bounded, mode="r|gz") as archive:
            for member in archive:
                name = Path(member.name).name
                if not member.isfile() or name not in rows or not name.endswith(".wav"):
                    continue
                if member.size > MAX_AUDIO_BYTES:
                    raise ValueError("The selected short sample exceeds the audio size limit.")
                handle = archive.extractfile(member)
                if handle is None:
                    continue
                audio = handle.read(MAX_AUDIO_BYTES + 1)
                if len(audio) != member.size or len(audio) > MAX_AUDIO_BYTES:
                    raise ValueError("The selected sample is incomplete or exceeds its size limit.")
                selected = (name, audio, rows[name])
                break
        transferred = bounded.count
    if selected is None:
        raise ValueError("No manifest-matched WAV was found within the transfer limit.")
    name, audio, row = selected
    if audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
        raise ValueError("The selected upstream sample is not WAV audio.")
    audio_path = output / f"fleurs-{language}.wav"
    reference_path = output / f"fleurs-{language}.reference.json"
    reference = {
        "text": row[2],
        "normalizedText": row[3],
        "turns": [],
        "referenceScope": "Dataset-provided single-utterance text; no hand-labelled speaker turns.",
        "purpose": "Human speech model compatibility only; not the MVP long-form quality gate.",
        "language": language,
        "dataset": REPOSITORY,
        "datasetRevision": REVISION,
        "datasetConfig": config,
        "split": "test",
        "sampleId": row[0],
        "sampleFilename": name,
        "numSamples": int(row[5]),
        "sampleRate": 16000,
        "durationSeconds": int(row[5]) / 16000,
        "sourceUrl": audio_url,
        "sourceMember": name,
        "manifestUrl": manifest_url,
        "manifestSha256": sha256(manifest),
        "license": LICENSE,
        "licenseUrl": LICENSE_URL,
        "attribution": "FLEURS: Few-shot Learning Evaluation of Universal Representations of Speech, Google.",
        "datasetCard": DATASET_CARD,
        "audioSha256": sha256(audio),
        "audioBytes": len(audio),
    }
    save_private(audio_path, audio)
    reference_bytes = (json.dumps(reference, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    save_private(reference_path, reference_bytes)
    # Never print reference text, archive response bodies, or signed redirect URLs.
    return {
        "language": language,
        "sampleId": row[0],
        "audioBytes": len(audio),
        "durationSeconds": reference["durationSeconds"],
        "audioSha256": reference["audioSha256"],
        "referenceSha256": sha256(reference_bytes),
        "archiveTransferBytes": transferred,
        "referenceCharacters": len(row[2]),
        "license": LICENSE,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("/private/tmp/localscribe-validation"))
    parser.add_argument("--language", choices=("all", "pl", "en"), default="all")
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    repository_root = Path(__file__).resolve().parents[1]
    if output.is_relative_to(repository_root):
        parser.error("Recordings and reference text must be stored outside the repository.")
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    opener = urllib.request.build_opener(PublicRedirects())
    # No credentials, token lookup, authentication header, or gated-terms acceptance.
    try:
        samples = [
            download_sample(opener, output, language, config)
            for language, config in LANGUAGES.items()
            if args.language in ("all", language)
        ]
    except (OSError, ValueError, tarfile.TarError) as error:
        status = getattr(error, "code", None)
        raise SystemExit(
            f"Public FLEURS sample download failed ({type(error).__name__}; HTTP status={status})."
        ) from None
    print(
        json.dumps(
            {
                "dataset": REPOSITORY,
                "revision": REVISION,
                "license": LICENSE,
                "source": DATASET_CARD,
                "samples": samples,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
