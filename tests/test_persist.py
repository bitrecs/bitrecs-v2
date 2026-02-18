import sqlite3

import pytest

from scoring.persist import ScorePersister
from scoring.types import MinerUID, EnvironmentId
from utils.subtensor import get_subtensor


def test_save_result_inserts_row(tmp_path):
    persister = ScorePersister(base_path=str(tmp_path), filename="scores.db")
    print(f"DB path: {persister.file_path}")  # Should show full path
    persister.save_result(
        uid=MinerUID(1),
        hotkey="hk1",
        score=0.75,
        run_id="run-1",
        task_name="task-a",
        success=True,
        duration=1.23,
        created_at="2026-02-18T00:00:00Z",
    )

    conn = sqlite3.connect(tmp_path / "scores.db")
    rows = list(conn.execute("SELECT run_id, uid, hotkey, task_name, score, success, duration, created_at FROM miner_scores"))
    conn.close()

    assert len(rows) == 1
    assert rows[0] == ("run-1", 1, "hk1", "task-a", 0.75, 1, 1.23, "2026-02-18T00:00:00Z")


def test_save_scores_aggregates_and_loads(tmp_path):
    persister = ScorePersister(base_path=str(tmp_path), filename="scores.db")

    scores = {
        MinerUID(1): {
            EnvironmentId("env1"): 0.8,
            EnvironmentId("env2"): 0.6,
        }
    }
    persister.save_scores(scores, run_id="run-2", hotkey="hk2", task_name="task-b")

    loaded = persister.load_scores()
    assert MinerUID(1) in loaded
    assert EnvironmentId("overall") in loaded[MinerUID(1)]
    assert loaded[MinerUID(1)][EnvironmentId("overall")] == 0.7


def test_emergency_save_no_last_data_no_error(tmp_path):
    persister = ScorePersister(base_path=str(tmp_path), filename="scores.db")
    # Should be a no-op if nothing was saved yet
    persister.emergency_save()


@pytest.mark.asyncio
async def test_hotkey_to_uid():
    hotkey = "5F95Nub62Fhwy3UFBMWg5eDou1B45yrzXaa7FjgXMALcER6r"
    sub = await get_subtensor()
    uid = await sub.get_uid_for_hotkey_on_subnet(hotkey_ss58=hotkey, netuid=296)
    print(f"UID for hotkey {hotkey}: {uid}")
    assert isinstance(uid, int), "UID should be an integer"
    assert uid > 0, "UID should be a positive integer"