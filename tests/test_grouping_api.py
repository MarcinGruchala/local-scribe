"""History/grouping HTTP contract, independent of model adapters."""

# Pytest discovers the imported shared client fixture; parameters intentionally shadow it.
# ruff: noqa: F811
import pytest
from localscribe.exports import render
from test_api import client  # noqa: F401
from test_transcript_history import recording


def test_http_grouping_history_workflow(client, tmp_path):
    job_id = recording(client.app.state.jobs, tmp_path)
    path = f"/api/jobs/{job_id}"
    history = client.get(path + "/history")
    assert history.status_code == 200
    assert history.json() == {"revision": 0, "canUndo": False, "canRedo": False, "operations": []}
    preview = client.post(path + "/grouping/preview", json={"expectedRevision": 0})
    assert preview.status_code == 200
    assert preview.json()["afterCount"] == 12
    saved = client.post(path + "/grouping/apply", json={"expectedRevision": 0})
    assert saved.status_code == 200 and saved.json()["revision"] == 1
    split = client.post(
        path + "/grouping/split", json={"expectedRevision": 1, "beforeSegmentId": "s10"}
    )
    assert split.status_code == 200 and split.json()["revision"] == 2
    for operation, revision in (("undo", 2), ("redo", 3)):
        response = client.post(path + f"/history/{operation}", json={"expectedRevision": revision})
        assert response.status_code == 200 and response.json()["revision"] == revision + 1
    assert len(client.get(path + "/history").json()["operations"]) == 2
    stale = client.post(path + "/grouping/apply", json={"expectedRevision": 0})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "stale_revision"
    for endpoint, payload in (
        ("grouping/preview", {}),
        ("grouping/apply", {"expectedRevision": True}),
        ("history/undo", {"expectedRevision": "4"}),
        ("history/redo", {"expectedRevision": -1}),
        ("grouping/apply", {"expectedRevision": 4, "blocks": []}),
        ("grouping/preview", {"expectedRevision": 4, "segmentIds": None}),
        ("grouping/preview", {"expectedRevision": 4, "segmentIds": []}),
        ("grouping/preview", {"expectedRevision": 4, "segmentIds": [1]}),
        ("grouping/split", {"expectedRevision": 4, "beforeSegmentId": ""}),
    ):
        response = client.post(path + "/" + endpoint, json=payload)
        assert response.status_code == 422, (endpoint, payload, response.text)
        assert "error" in response.json()
    denied = client.post(
        path + "/history/undo",
        json={"expectedRevision": 4},
        headers={"X-LocalScribe-Token": "wrong"},
    )
    assert denied.status_code == 403
    assert client.get(path + "/transcript").json()["revision"] == 4


@pytest.mark.parametrize("output", ["rendered", "download", "automatic"])
def test_grouped_txt_preserves_saved_source_order_with_backwards_times(client, tmp_path, output):
    jobs = client.app.state.jobs
    job_id = recording(
        jobs,
        tmp_path,
        segments=[
            {"id": sid, "start": start, "end": end, "speakerId": "speaker1", "text": sid}
            for sid, start, end in [("A", 10, 11), ("B", 0, 1), ("C", 1, 2)]
        ],
    )
    path = f"/api/jobs/{job_id}/export"
    subtitles = {}
    for format in ("srt", "vtt"):
        response = client.get(path, params={"format": format})
        assert response.status_code == 200
        subtitles[format] = response.text
        assert response.text.index("Speaker 1: B") < response.text.index("Speaker 1: C")
        assert response.text.index("Speaker 1: C") < response.text.index("Speaker 1: A")
    saved = jobs.grouping_apply(job_id, 0)
    assert [block["segmentIds"] for block in saved["grouping"]["blocks"]] == [["A"], ["B", "C"]]
    assert render(saved, "txt", layout="segmented")[0] == (
        "Speaker 1: B\n\nSpeaker 1: C\n\nSpeaker 1: A\n"
    )
    for format, expected in subtitles.items():
        for layout in ("grouped", "segmented"):
            response = client.get(path, params={"format": format, "layout": layout})
            assert response.status_code == 200 and response.text == expected
        assert (jobs.directory(job_id) / f"transcript.{format}").read_text() == expected
    if output == "rendered":
        actual = render(saved, "txt")[0]
    elif output == "download":
        response = client.get(path, params={"format": "txt"})
        assert response.status_code == 200
        assert "attachment" in response.headers["content-disposition"]
        actual = response.text
    else:
        actual = (jobs.directory(job_id) / "transcript.txt").read_text()
    assert actual == "Speaker 1: A\n\nSpeaker 1: B C\n"


def test_saved_grouped_exports_and_original_source_cues(client, tmp_path):
    import json

    jobs = client.app.state.jobs
    job_id = recording(jobs, tmp_path)
    path = f"/api/jobs/{job_id}"
    immutable = next(jobs.directory(job_id).glob("attempts/*/published.json"))
    source_bytes = immutable.read_bytes()
    before_srt = client.get(path + "/export?format=srt").text
    before_vtt = client.get(path + "/export?format=vtt").text
    jobs.grouping_preview(job_id, 0)
    assert len(client.get(path + "/export?format=json").json()["grouping"]["blocks"]) == 360
    jobs.grouping_apply(job_id, 0)
    current = client.get(path + "/export?format=json").json()
    assert current["schemaVersion"] == 2
    assert len(current["grouping"]["blocks"]) == 12 and len(current["segments"]) == 360
    grouped_txt = client.get(path + "/export?format=txt").text
    assert grouped_txt.count("Speaker 1:") == 12
    assert client.get(path + "/export?format=srt").text == before_srt
    assert client.get(path + "/export?format=vtt&layout=grouped").text == before_vtt
    edited = client.patch(
        path + "/transcript",
        json={"revision": 1, "texts": {"s0": "Edited"}, "names": {"speaker1": "Alice"}},
    )
    assert edited.status_code == 200
    for query in ("source=original", "source=original&layout=segmented", "layout=segmented"):
        output = client.get(path + "/export?format=json&" + query).json()
        assert output["schemaVersion"] == 1 and "grouping" not in output
        if "source=original" in query:
            assert output["segments"][0]["editedText"] is None
            assert output["speakers"][0]["displayName"] == "Speaker 1"
    assert "Alice: Edited word1" in client.get(path + "/export?format=txt").text
    assert client.get(path + "/export?format=txt&layout=segmented").text.count("Alice:") == 360
    assert client.get(path + "/export?format=srt&source=original").text == before_srt
    assert client.get(path + "/export?format=vtt&source=original").text == before_vtt
    assert immutable.read_bytes() == source_bytes
    for format in ("txt", "srt", "vtt", "json"):
        assert (jobs.directory(job_id) / f"transcript.{format}").read_text() == client.get(
            path + "/export?format=" + format
        ).text
    assert (
        json.loads((jobs.directory(job_id) / "transcript.json").read_text())["schemaVersion"] == 2
    )
    for query in ("source=invalid", "layout=invalid", "format=html"):
        assert (
            client.get(
                path
                + "/export?"
                + ("format=json&" if not query.startswith("format") else "")
                + query
            ).status_code
            == 422
        )
