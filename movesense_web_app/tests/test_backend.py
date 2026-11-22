import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backend
from backend import MotionSample, SessionTracker
from fastapi import HTTPException


class SessionTrackerTests(unittest.TestCase):
    def test_completed_session_is_saved_with_estimated_distance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            with patch.multiple(
                backend,
                DATA_DIR=data_dir,
                DATABASE_PATH=data_dir / "test.sqlite3",
            ):
                backend.initialize_database()
                backend.update_profile("Test", 75)
                tracker = SessionTracker()
                tracker.start("demo")
                tracker.process(
                    MotionSample(x=0, y=0, z=20, alpha=1, beta=2, gamma=3)
                )

                saved = tracker.stop()
                sessions = backend.list_sessions()

        self.assertIsNotNone(saved)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["source"], "demo")
        self.assertEqual(sessions[0]["steps"], 1)
        self.assertAlmostEqual(sessions[0]["distance"], 0.0008)

    def test_sample_is_rejected_when_session_is_stopped(self) -> None:
        tracker = SessionTracker()
        with self.assertRaises(HTTPException):
            tracker.process(MotionSample(x=0, y=0, z=9.8))

    def test_stationary_samples_are_not_counted_as_steps(self) -> None:
        tracker = SessionTracker()
        tracker.start("phone")
        for _ in range(60):
            tracker.process(MotionSample(x=0, y=0, z=9.8))
        snapshot = tracker.snapshot()
        self.assertEqual(snapshot["steps"], 0)
        self.assertEqual(snapshot["activity"], "Idle")

    def test_repeated_movement_is_classified_as_walking_or_running(self) -> None:
        tracker = SessionTracker()
        tracker.start("demo")
        walking_pattern = [9.8, 12.0, 10.0, 7.5]
        for index in range(60):
            tracker.process(
                MotionSample(
                    x=0,
                    y=0,
                    z=walking_pattern[index % len(walking_pattern)],
                )
            )
        snapshot = tracker.snapshot()
        self.assertGreater(snapshot["steps"], 0)
        self.assertIn(snapshot["activity"], {"Walking", "Running"})


if __name__ == "__main__":
    unittest.main()
