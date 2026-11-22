"""SQLite persistence and motion-session processing for MoveSense."""

from __future__ import annotations

import math
import os
import sqlite3
import time
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Iterator

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field


DATA_DIR = Path(os.environ.get("MOVESENSE_DATA_DIR", Path(__file__).resolve().parent / "data"))
DATABASE_PATH = DATA_DIR / "movesense.sqlite3"


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database() -> None:
    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                activity TEXT NOT NULL,
                seconds INTEGER NOT NULL,
                steps INTEGER NOT NULL,
                distance REAL NOT NULL,
                source TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT NOT NULL,
                step_length_cm REAL NOT NULL
            );
            INSERT OR IGNORE INTO profile (id, name, step_length_cm)
            VALUES (1, 'User', 70);
            """
        )


def get_profile() -> dict[str, Any]:
    with _connect() as connection:
        row = connection.execute(
            "SELECT name, step_length_cm FROM profile WHERE id = 1"
        ).fetchone()
    if row is None:
        raise RuntimeError("MoveSense profile is missing from the database.")
    return dict(row)


def update_profile(name: str, step_length_cm: float) -> None:
    normalized_name = name.strip() or "User"
    if len(normalized_name) > 30:
        raise ValueError("Display name must be 30 characters or fewer.")
    if not 30 <= step_length_cm <= 120:
        raise ValueError("Average step length must be between 30 and 120 cm.")
    with _connect() as connection:
        connection.execute(
            "UPDATE profile SET name = ?, step_length_cm = ? WHERE id = 1",
            (normalized_name, step_length_cm),
        )


def list_sessions(limit: int = 500) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, date, activity, seconds, steps, distance, source
            FROM sessions
            ORDER BY date DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def save_session(session: dict[str, Any]) -> None:
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO sessions (date, activity, seconds, steps, distance, source)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session["date"],
                session["activity"],
                session["seconds"],
                session["steps"],
                session["distance"],
                session["source"],
            ),
        )


def clear_sessions() -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM sessions")


class MotionSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = Field(ge=-1000, le=1000)
    y: float = Field(ge=-1000, le=1000)
    z: float = Field(ge=-1000, le=1000)
    alpha: float = Field(default=0, ge=-10000, le=10000)
    beta: float = Field(default=0, ge=-10000, le=10000)
    gamma: float = Field(default=0, ge=-10000, le=10000)


class SensorError(BaseModel):
    message: str = Field(min_length=1, max_length=300)


class SessionTracker:
    """Keeps a live signal in memory and persists completed sessions to SQLite."""

    def __init__(self) -> None:
        self._lock = RLock()
        self.active = False
        self.source = "phone"
        self.started_at = 0.0
        self.steps = 0
        self.peaks = 0
        self.smoothed = 0.0
        self._last_dynamic = 0.0
        self._last_peak_at = 0.0
        self._magnitudes: deque[float] = deque(maxlen=18)
        self.samples: deque[dict[str, Any]] = deque(maxlen=80)
        self.activity = "Idle"
        self.latest = {"x": 0.0, "y": 0.0, "z": 0.0, "alpha": 0.0, "beta": 0.0, "gamma": 0.0}
        self.last_error = ""

    def start(self, source: str) -> None:
        if source not in {"phone", "demo"}:
            raise ValueError("Unknown sensor source.")
        with self._lock:
            if self.active:
                raise ValueError("A monitoring session is already active.")
            self.active = True
            self.source = source
            self.started_at = time.monotonic()
            self.steps = 0
            self.peaks = 0
            self.smoothed = 0.0
            self._last_dynamic = 0.0
            self._last_peak_at = 0.0
            self._magnitudes.clear()
            self.samples.clear()
            self.activity = "Monitoring"
            self.last_error = ""

    def process(self, sample: MotionSample) -> dict[str, Any]:
        with self._lock:
            if not self.active:
                raise HTTPException(status_code=409, detail="No sensor session is active.")
            self.latest = sample.model_dump()
            magnitude = math.sqrt(sample.x**2 + sample.y**2 + sample.z**2)
            self.smoothed = self.smoothed * 0.78 + magnitude * 0.22
            now = time.monotonic()
            dynamic = abs(self.smoothed - 9.8)
            if dynamic > 1.5 and self._last_dynamic <= 1.5 and now - self._last_peak_at > 0.35:
                self.steps += 1
                self.peaks += 1
                self._last_peak_at = now
            self._last_dynamic = dynamic
            self._magnitudes.append(abs(self.smoothed - 9.8))
            variation = sum(self._magnitudes) / len(self._magnitudes)
            self.activity = "Running" if variation > 4.2 else "Walking" if variation > 1.35 else "Idle"
            self.samples.append(
                {
                    "time": datetime.now().astimezone().strftime("%H:%M:%S"),
                    **self.latest,
                }
            )
            return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            seconds = int(time.monotonic() - self.started_at) if self.active else 0
            return {
                "active": self.active,
                "source": self.source,
                "seconds": seconds,
                "steps": self.steps,
                "peaks": self.peaks,
                "activity": self.activity,
                "magnitude": self.smoothed,
                "latest": dict(self.latest),
                "samples": list(self.samples),
                "last_error": self.last_error,
            }

    def set_error(self, message: str) -> None:
        with self._lock:
            self.last_error = message

    def stop(self) -> dict[str, Any] | None:
        with self._lock:
            if not self.active:
                return None
            seconds = max(1, int(time.monotonic() - self.started_at))
            self.active = False
            activity = self.activity if self.activity != "Idle" else "Movement session"
            steps = self.steps
            source = self.source
            step_length_cm = float(get_profile()["step_length_cm"])
            session = {
                "date": datetime.now(timezone.utc).isoformat(),
                "activity": activity,
                "seconds": seconds,
                "steps": steps,
                "distance": round(steps * step_length_cm / 100000, 4),
                "source": source,
            }
        if steps > 0 or seconds > 5:
            save_session(session)
            return session
        return None


initialize_database()
tracker = SessionTracker()
