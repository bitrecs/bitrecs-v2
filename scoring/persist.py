import logging
import signal
import atexit
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional
from threading import Lock

from scoring.types import MinerScores, MinerUID, EnvironmentId

logger = logging.getLogger(__name__)

class ScorePersister:
    """
    SQLite-backed persistence for miner scores.
    Stores (uid, env_id, score, updated_at).
    """

    def __init__(self, base_path: str = "data/weights", filename: str = "scores.db"):
        self.save_dir = Path(base_path)
        self.file_path = self.save_dir / filename
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._registered = False
        self._last_data: Optional[MinerScores] = None
        self._init_db()

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS miner_scores (
                    run_id TEXT NOT NULL,
                    uid INTEGER NOT NULL, 
                    hotkey TEXT NOT NULL,                    
                    task_name TEXT,
                    score REAL NOT NULL,
                    success BOOLEAN,                    
                    duration REAL,
                    created_at TEXT                         
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_scores_uid ON miner_scores(uid)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_scores_run ON miner_scores(run_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_scores_hotkey ON miner_scores(hotkey)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_scores_task ON miner_scores(task_name)")
            
            conn.commit()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.file_path)
        try:
            yield conn
        finally:
            conn.close()

    def register_shutdown_hooks(self):
        """Register handlers to persist on SIGINT/SIGTERM and normal exit."""
        if self._registered:
            return

        def _handler(signum, _frame):
            logger.warning(f"Signal {signum} received. Saving state...")
            self.emergency_save()

        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)
        atexit.register(self.emergency_save)
        self._registered = True

    def save_scores(self, scores: MinerScores, run_id: str, hotkey: str, task_name: str | None = None):
        """Insert aggregated scores into sqlite."""
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        rows: list[tuple[str, int, str, str | None, float, bool | None, float | None, str]] = []

        for uid, env_scores in scores.items():
            # Aggregate env scores into a single score (mean)
            score = sum(env_scores.values()) / max(len(env_scores), 1)
            rows.append((run_id, int(uid), hotkey, task_name, float(score), None, None, now))

        with self._lock, self._connect() as conn:
            self._last_data = scores
            conn.executemany("""
                INSERT INTO miner_scores (run_id, uid, hotkey, task_name, score, success, duration, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
            conn.commit()
            logger.info(f"Persisted {len(rows)} scores to {self.file_path}")

    def load_scores(self) -> MinerScores:
        """Load scores into MinerScores format (collapsed by uid)."""
        result: MinerScores = {}
        with self._connect() as conn:
            for uid, score in conn.execute("SELECT uid, score FROM miner_scores"):
                result.setdefault(MinerUID(uid), {})[EnvironmentId("overall")] = float(score)
        self._last_data = result
        return result

    def emergency_save(self):
        """Save last known state during shutdown/interrupts."""
        if self._last_data is not None:
            logger.warning(f"Emergency save to {self.file_path}")
            self.save_scores(self._last_data)

    def save_result(
        self,
        uid: MinerUID,
        hotkey: str,
        score: float,
        run_id: str,
        task_name: str | None = None,
        success: bool | None = None,
        duration: float | None = None,
        created_at: str | None = None,
    ) -> bool:
        """Insert a single scored result with metadata."""

        try:
            created_at = created_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            row = (run_id, int(uid), hotkey, task_name, float(score), success, duration, created_at)

            with self._lock, self._connect() as conn:
                conn.execute("""
                    INSERT INTO miner_scores (run_id, uid, hotkey, task_name, score, success, duration, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, row)
                conn.commit()
                logger.info(f"Saved result for uid {uid} to {self.file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save result for uid {uid}: {e}")
            return False

    def __enter__(self):
        self.register_shutdown_hooks()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.emergency_save()
        return False  # propagate exceptions

# Usage Example
# --------------------------------------------------
# from scoring.persist import ScorePersister
#
# with ScorePersister() as persister:
#     # Load prior state (if any)
#     previous = persister.load()
#     if previous:
#         print("Loaded previous state")
#
#     try:
#         while True:
#             scores = compute_some_scores()
#             persister.save(scores)
#     except KeyboardInterrupt:
#         # Optional: already handled by hooks, but you can still log
#         print("Interrupted; state saved.")