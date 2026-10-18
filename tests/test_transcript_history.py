"""Public Jobs history workflows, using isolated synthetic saved transcripts."""

import json

import pytest
from localscribe.jobs import JobError, Jobs
from localscribe.storage import Storage
from test_jobs import completed, queued, result


def recording(jobs, tmp_path, segments=None, **extra):
    queued(jobs, tmp_path)
    active = jobs.claim()
    path = result(jobs, active)
    payload = json.loads(path.read_text())
    payload.update(
        duration=2000,
        segments=segments
        or [
            {
                "id": f"s{i}",
                "start": i * 2,
                "end": i * 2 + 1,
                "speakerId": "speaker1",
                "text": f"  word{i}  ",
            }
            for i in range(360)
        ],
        **extra,
    )
    path.write_text(json.dumps(payload))
    assert jobs.publish(active["id"], 1, path)
    return active["id"]


def test_bulk_grouping_preview_apply_is_stateless_single_undo_unit(jobs, tmp_path):
    job_id = recording(jobs, tmp_path)
    original = jobs.transcript(job_id)
    immutable = next(jobs.directory(job_id).glob("attempts/*/published.json"))
    before = immutable.read_bytes()
    copies = (jobs.directory(job_id) / "transcript.txt").read_bytes()
    assert len(original["grouping"]["blocks"]) == 360
    preview = jobs.grouping_preview(job_id, 0)
    assert preview == jobs.grouping_preview(job_id, 0)
    assert preview["revision"] == 0 and preview["changed"] is True
    assert (preview["beforeCount"], preview["afterCount"]) == (360, 12)
    assert preview["blocks"][0] == {
        "id": "s0",
        "segmentIds": [f"s{i}" for i in range(30)],
        "start": 0.0,
        "end": 59.0,
        "speakerId": "speaker1",
        "text": " ".join(f"word{i}" for i in range(30)),
    }
    assert jobs.transcript(job_id) == original
    assert jobs.history(job_id)["operations"] == []
    assert (jobs.directory(job_id) / "transcript.txt").read_bytes() == copies
    saved = jobs.grouping_apply(job_id, 0)
    assert saved["grouping"]["blocks"] == preview["blocks"]
    assert saved["segments"] == original["segments"] and saved["revision"] == 1
    assert jobs.history(job_id)["operations"][0]["type"] == "grouping"
    assert jobs.grouping_preview(job_id, 1)["changed"] is False
    assert jobs.grouping_apply(job_id, 1) == saved
    assert len(jobs.history(job_id)["operations"]) == 1
    assert jobs.undo(job_id, 1) == {**original, "revision": 2}
    assert jobs.redo(job_id, 2) == {**saved, "revision": 3}
    assert immutable.read_bytes() == before


def test_grouping_respects_ambiguity_barriers_caps_and_source_order(jobs, tmp_path):
    base = [
        {
            "id": f"s{i}",
            "start": i * 2,
            "end": i * 2 + 1,
            "speakerId": "speaker1",
            "text": f"part{i}",
        }
        for i in range(5)
    ]
    cases = [
        ({"overlap": True}, {}),
        ({"speakerId": None}, {}),
        ({"start": 1.5, "end": 3.5}, {}),
        ({"start": 0.5, "end": 1}, {}),
        ({}, {"words": [{"start": 4, "end": 4.5, "word": "x", "overlap": True}]}),
        (
            {},
            {
                "regularTurns": [
                    {"start": 4, "end": 4.8, "speakerId": "speaker1"},
                    {"start": 4.2, "end": 4.6, "speakerId": "speaker2"},
                ],
                "speakers": [
                    {"id": "speaker1", "displayName": "Same"},
                    {"id": "speaker2", "displayName": "Same"},
                ],
            },
        ),
        ({"text": "X" * 1201}, {}),
        ({"end": 65}, {}),
    ]
    for change, extra in cases:
        segments = [dict(item) for item in base]
        segments[2].update(change)
        job_id = recording(jobs, tmp_path, segments, **extra)
        preview = jobs.grouping_preview(job_id, 0)
        assert [block["segmentIds"] for block in preview["blocks"]] == [
            ["s0", "s1"],
            ["s2"],
            ["s3", "s4"],
        ], (change, extra, preview)
        assert [sid for block in preview["blocks"] for sid in block["segmentIds"]] == [
            "s0",
            "s1",
            "s2",
            "s3",
            "s4",
        ]
        assert jobs.grouping_apply(job_id, 0)["segments"] == jobs.transcript(job_id)["segments"]


def test_selection_preserves_outside_blocks_and_manual_split_survives_regroup(jobs, tmp_path):
    job_id = recording(jobs, tmp_path)
    jobs.grouping_apply(job_id, 0)
    before = jobs.transcript(job_id)
    split = jobs.grouping_split(job_id, 1, "s10")
    assert split["grouping"]["manualSplits"] == ["s10"]
    assert split["grouping"]["blocks"][0]["segmentIds"] == [f"s{i}" for i in range(10)]
    regroup = jobs.grouping_preview(job_id, 2)
    assert regroup["blocks"][0]["segmentIds"] == [f"s{i}" for i in range(10)]
    assert regroup["blocks"][1]["segmentIds"][0] == "s10"
    assert jobs.undo(job_id, 2) == {**before, "revision": 3}
    split = jobs.redo(job_id, 3)
    selected = [f"s{i}" for i in range(35, 65)]
    preview = jobs.grouping_preview(job_id, 4, selected)
    expected = [
        [f"s{i}" for i in range(a, b)] for a, b in [(0, 10), (10, 30), (30, 35), (35, 65), (65, 90)]
    ]
    assert [block["segmentIds"] for block in preview["blocks"][:5]] == expected
    assert preview["blocks"][5:] == split["grouping"]["blocks"][4:]
    saved = jobs.grouping_apply(job_id, 4, selected)
    assert saved["grouping"]["blocks"] == preview["blocks"]
    assert jobs.history(job_id)["operations"][1]["type"] == "split"
    for selection in ([], ["s2", "s4"], ["s3", "s2"], ["s2", "s2"], ["missing"]):
        with pytest.raises(JobError) as error:
            jobs.grouping_apply(job_id, 5, selection)
        assert error.value.status == 422
    for segment_id in ("s0", "missing", "s10"):
        with pytest.raises(JobError) as error:
            jobs.grouping_split(job_id, 5, segment_id)
        assert error.value.status == 422
    assert jobs.transcript(job_id) == saved


@pytest.fixture
def jobs(tmp_path):
    service = Jobs(Storage(tmp_path / "store"))
    service.initialize()
    return service


def test_manual_save_is_exact_persistent_undo_redo_unit(jobs, tmp_path):
    job_id = completed(jobs, tmp_path)["id"]
    original = jobs.transcript(job_id)
    saved = jobs.patch(job_id, 0, {"s1": "  Cześć\n世界  "}, {"speaker1": "Alice"})
    history = jobs.history(job_id)
    assert history["revision"] == 1 and history["canUndo"] and not history["canRedo"]
    assert len(history["operations"]) == 1
    operation = history["operations"][0]
    assert operation["type"] == "manual_save" and operation["applied"] is True
    assert operation["baseRevision"] == 0 and operation["resultRevision"] == 1
    assert operation["id"] and operation["createdAt"] > 0
    restarted = Jobs(Storage(jobs.storage.root))
    restarted.initialize()
    undone = restarted.undo(job_id, 1)
    assert undone == {**original, "revision": 2}
    assert restarted.history(job_id)["canRedo"] is True
    redone = restarted.redo(job_id, 2)
    assert redone == {**saved, "revision": 3}
    assert restarted.history(job_id)["operations"][0]["id"] == operation["id"]


def test_new_published_attempt_resets_history_and_records_attempt_provenance(jobs, tmp_path):
    job_id = recording(jobs, tmp_path)
    jobs.grouping_apply(job_id, 0)
    jobs.patch(job_id, 1, {"s0": "old attempt"})
    jobs.undo(job_id, 2)
    with jobs.storage.connect() as db:
        provenance = json.loads(
            db.execute(
                "SELECT provenance FROM transcript_operations WHERE job_id=? ORDER BY position",
                (job_id,),
            ).fetchone()[0]
        )
    assert provenance["attempt"] == 1
    # A missing canonical result permits retry; old user history must not attach to its replacement.
    next(jobs.directory(job_id).glob("attempts/*/published.json")).unlink()
    jobs.recover()
    jobs.retry(job_id)
    active = jobs.claim()
    assert active["attempt"] == 2
    assert jobs.publish(job_id, 2, result(jobs, active))
    assert jobs.history(job_id) == {
        "revision": 0,
        "canUndo": False,
        "canRedo": False,
        "operations": [],
    }
    assert jobs.transcript(job_id)["grouping"]["manualSplits"] == []
    saved = jobs.patch(job_id, 0, {"s1": "new attempt"})
    assert jobs.undo(job_id, 1)["segments"][0]["editedText"] is None
    assert jobs.redo(job_id, 2) == {**saved, "revision": 3}
    with jobs.storage.connect() as db:
        rows = db.execute(
            "SELECT provenance FROM transcript_operations WHERE job_id=?", (job_id,)
        ).fetchall()
        checkpoint = db.execute(
            "SELECT checkpoint FROM transcript_history_state WHERE job_id=?", (job_id,)
        ).fetchone()[0]
    assert len(rows) == 1 and json.loads(rows[0][0])["attempt"] == 2
    assert json.loads(checkpoint) == {"segments": {}, "speakers": {}}


def test_grouping_refuses_exact_value_conflict_even_for_noop(jobs, tmp_path):
    job_id = recording(jobs, tmp_path)
    jobs.grouping_apply(job_id, 0)
    with jobs.storage.connect() as db:
        edits = json.loads(db.execute("SELECT edits FROM jobs WHERE id=?", (job_id,)).fetchone()[0])
        edits["speakers"]["speaker1"] = "out-of-band change"
        db.execute("UPDATE jobs SET edits=? WHERE id=?", (json.dumps(edits), job_id))
    for mutate in (jobs.grouping_preview, jobs.grouping_apply):
        with pytest.raises(JobError) as error:
            mutate(job_id, 1)
        assert error.value.code == "history_conflict"
    assert jobs.get(job_id)["revision"] == 1


def legacy_history_schema(jobs):
    with jobs.storage.connect() as db:
        db.execute("DROP TABLE transcript_operations")
        db.execute("DROP TABLE transcript_history_state")
        db.execute("DELETE FROM schema_migrations WHERE version=5")


def test_old_store_saved_edits_become_checkpoint_not_invented_history(jobs, tmp_path):
    job_id = completed(jobs, tmp_path)["id"]
    checkpoint = jobs.patch(job_id, 0, {"s1": "Existing saved edit"}, {"speaker1": "Alice"})
    legacy_history_schema(jobs)
    jobs.initialize()
    assert jobs.transcript(job_id) == checkpoint
    assert jobs.history(job_id) == {
        "revision": 1,
        "canUndo": False,
        "canRedo": False,
        "operations": [],
    }
    jobs.patch(job_id, 1, {"s1": "New edit"})
    assert jobs.undo(job_id, 2) == {**checkpoint, "revision": 3}
    jobs.initialize()
    assert jobs.redo(job_id, 3)["segments"][0]["editedText"] == "New edit"


def test_checkpoint_migration_corruption_rolls_back_schema_and_backfill(jobs, tmp_path):
    first = completed(jobs, tmp_path)["id"]
    second = completed(jobs, tmp_path)["id"]
    legacy_history_schema(jobs)
    with jobs.storage.connect() as db:
        db.execute("UPDATE jobs SET edits='[]' WHERE id=?", (second,))
    with pytest.raises(ValueError, match="Invalid saved transcript edits"):
        jobs.initialize()
    with jobs.storage.connect() as db:
        assert db.execute("SELECT version FROM schema_migrations WHERE version=5").fetchall() == []
        assert (
            db.execute("SELECT name FROM sqlite_master WHERE name LIKE 'transcript_%'").fetchall()
            == []
        )
        db.execute("UPDATE jobs SET edits=? WHERE id=?", ('{"segments":{},"speakers":{}}', second))
    jobs.initialize()
    assert jobs.history(first)["operations"] == []
    assert jobs.history(second)["operations"] == []


def test_redo_branching_monotonic_revisions_and_stale_guards(jobs, tmp_path):
    job_id = completed(jobs, tmp_path)["id"]
    jobs.patch(job_id, 0, {"s1": "first"})
    old = jobs.patch(job_id, 1, {"s1": "second"})
    old_id = jobs.history(job_id)["operations"][-1]["id"]
    jobs.undo(job_id, 2)
    history = jobs.history(job_id)
    assert history["canRedo"] and [op["applied"] for op in history["operations"]] == [True, False]
    for operation in (jobs.undo, jobs.redo, jobs.grouping_preview, jobs.grouping_apply):
        with pytest.raises(JobError) as error:
            operation(job_id, 2)
        assert error.value.code == "stale_revision"
    saved = jobs.patch(job_id, 3, {"s1": "branch"})
    history = jobs.history(job_id)
    assert saved["revision"] == 4 and not history["canRedo"]
    assert history["operations"][-1]["id"] != old_id
    with pytest.raises(JobError) as error:
        jobs.redo(job_id, 4)
    assert error.value.code == "history_unavailable"
    assert jobs.undo(job_id, 4)["segments"][0]["editedText"] == "first"
    assert jobs.redo(job_id, 5) == {**saved, "revision": 6}
    assert old["segments"][0]["editedText"] == "second"


@pytest.mark.parametrize("redo", [False, True])
def test_history_checks_operation_exact_values_before_mutation(jobs, tmp_path, redo):
    job_id = completed(jobs, tmp_path)["id"]
    jobs.patch(job_id, 0, {"s1": "saved"})
    if redo:
        jobs.undo(job_id, 1)
    revision = 2 if redo else 1
    before = jobs.transcript(job_id)
    with jobs.storage.connect() as db:
        # Corrupt the operation rather than current state: both guards must be effective.
        if redo:
            db.execute(
                "UPDATE transcript_operations SET before_value=? WHERE job_id=?",
                ('{"segments":{},"speakers":{"speaker1":"different"}}', job_id),
            )
        else:
            db.execute(
                "UPDATE transcript_operations SET after_value=? WHERE job_id=?",
                ('{"segments":{"s1":"different"},"speakers":{}}', job_id),
            )
    with pytest.raises(JobError) as error:
        (jobs.redo if redo else jobs.undo)(job_id, revision)
    assert error.value.code == "history_conflict"
    assert jobs.transcript(job_id) == before


@pytest.mark.parametrize("operation", ["grouping", "split", "undo", "redo"])
def test_history_mutation_copy_failure_commits_and_restart_repairs(
    jobs, tmp_path, monkeypatch, operation
):
    from pathlib import Path

    from localscribe import local_files
    from localscribe.exports import render

    job_id = recording(jobs, tmp_path)
    directory = jobs.directory(job_id)
    immutable = next(directory.glob("attempts/*/published.json"))
    original = immutable.read_bytes()
    if operation != "grouping":
        jobs.grouping_apply(job_id, 0)
    if operation == "redo":
        jobs.undo(job_id, 1)
    revision = jobs.get(job_id)["revision"]
    real_replace = local_files.os.replace

    def broken_replace(source, destination):
        if Path(destination) == directory / "transcript.srt":
            raise OSError("private content must not leak")
        return real_replace(source, destination)

    monkeypatch.setattr(local_files.os, "replace", broken_replace)
    if operation == "grouping":
        saved = jobs.grouping_apply(job_id, revision)
    elif operation == "split":
        saved = jobs.grouping_split(job_id, revision, "s10")
    else:
        saved = getattr(jobs, operation)(job_id, revision)
    assert saved["revision"] == revision + 1 and jobs.transcript(job_id) == saved
    assert jobs.get(job_id)["localFiles"]["status"] == "error"
    assert "private content" not in json.dumps(jobs.get(job_id))
    assert not (directory / local_files.MANIFEST).exists()
    assert not list(directory.glob(".*.pending"))
    monkeypatch.setattr(local_files.os, "replace", real_replace)
    restarted = Jobs(Storage(jobs.storage.root))
    restarted.initialize()
    restarted.recover()
    assert restarted.transcript(job_id) == saved
    assert restarted.get(job_id)["localFiles"]["status"] == "ready"
    for format in local_files.FORMATS:
        assert (directory / f"transcript.{format}").read_text() == render(saved, format)[0]
    assert immutable.read_bytes() == original


def test_deletion_cascades_only_owned_history_and_grouped_copies(jobs, tmp_path):
    job_id = recording(jobs, tmp_path)
    other_id = completed(jobs, tmp_path)["id"]
    jobs.grouping_apply(job_id, 0)
    jobs.grouping_split(job_id, 1, "s10")
    jobs.patch(other_id, 0, {"s1": "other recording"})
    other_history = jobs.history(other_id)
    shared = jobs.storage.root / "models" / "weights"
    shared.parent.mkdir()
    shared.write_bytes(b"shared models")
    backup = jobs.storage.root / "legacy-backup"
    backup.write_bytes(b"immutable legacy backup")
    jobs.delete(job_id)
    assert not jobs.directory(job_id).exists()
    with jobs.storage.connect() as db:
        assert (
            db.execute("SELECT * FROM transcript_operations WHERE job_id=?", (job_id,)).fetchall()
            == []
        )
        assert (
            db.execute(
                "SELECT * FROM transcript_history_state WHERE job_id=?", (job_id,)
            ).fetchall()
            == []
        )
    assert jobs.history(other_id) == other_history
    assert (jobs.directory(other_id) / "transcript.json").exists()
    assert shared.read_bytes() == b"shared models"
    assert backup.read_bytes() == b"immutable legacy backup"


def test_noop_grouping_preserves_redo_branch(jobs, tmp_path):
    job_id = recording(jobs, tmp_path)
    jobs.grouping_apply(job_id, 0)
    jobs.patch(job_id, 1, {"s0": "draft saved later"})
    jobs.undo(job_id, 2)
    before = jobs.history(job_id)
    assert before["canRedo"]
    assert jobs.grouping_apply(job_id, 3)["revision"] == 3
    assert jobs.history(job_id) == before
    assert jobs.redo(job_id, 3)["segments"][0]["editedText"] == "draft saved later"


def test_competing_grouping_applies_have_one_transactional_winner(jobs, tmp_path):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    job_id = recording(jobs, tmp_path)
    barrier = threading.Barrier(2)

    def apply():
        barrier.wait()
        try:
            return jobs.grouping_apply(job_id, 0)["revision"]
        except JobError as error:
            return error.code

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: apply(), range(2)))
    assert sorted(results, key=str) == [1, "stale_revision"]
    assert len(jobs.history(job_id)["operations"]) == 1
    assert jobs.get(job_id)["localFiles"]["savedRevision"] == 1
