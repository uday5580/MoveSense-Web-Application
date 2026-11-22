import tempfile
import unittest
import math
from pathlib import Path
from unittest.mock import patch

import backend
from backend import MotionSample, SessionTracker
from fastapi import HTTPException


class SessionTrackerTests(unittest.TestCase):
    def run_with_clock(self, tracker, samples, step=0.06):
        current_time = [0.0]

        def clock():
            current_time[0] += step
            return current_time[0]

        with patch("backend.time.monotonic", side_effect=clock):
            tracker.start("phone")
            for sample in samples:
                tracker.process(sample)
            return tracker.snapshot()

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
                current_time = [0.0]

                def clock():
                    current_time[0] += 0.06
                    return current_time[0]

                with patch("backend.time.monotonic", side_effect=clock):
                    tracker.start("phone")
                    for index in range(100):
                        tracker.process(
                            MotionSample(
                                x=2.2 * math.sin(index * 2 * math.pi / 12),
                                y=0,
                                z=0,
                            )
                        )
                    saved = tracker.stop()
                sessions = backend.list_sessions()

        self.assertIsNotNone(saved)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["source"], "phone")
        self.assertGreaterEqual(sessions[0]["steps"], 3)
        self.assertGreater(sessions[0]["distance"], 0)

    def test_sample_is_rejected_when_session_is_stopped(self) -> None:
        tracker = SessionTracker()
        with self.assertRaises(HTTPException):
            tracker.process(MotionSample(x=0, y=0, z=9.8))

    def test_stationary_samples_are_not_counted_as_steps(self) -> None:
        tracker = SessionTracker()
        snapshot = self.run_with_clock(
            tracker,
            [MotionSample(x=0, y=0, z=0) for _ in range(60)],
        )
        self.assertEqual(snapshot["steps"], 0)
        self.assertEqual(snapshot["activity"], "Idle")

    def test_repeated_movement_is_classified_as_walking_or_running(self) -> None:
        tracker = SessionTracker()
        snapshot = self.run_with_clock(
            tracker,
            [
                MotionSample(
                    x=2.2 * math.sin(index * 2 * math.pi / 12),
                    y=0,
                    z=0,
                )
                for index in range(100)
            ],
        )
        self.assertGreater(snapshot["steps"], 0)
        self.assertEqual(snapshot["activity"], "Walking")

    def test_isolated_motion_spikes_do_not_count_as_steps(self) -> None:
        tracker = SessionTracker()
        samples = []
        for index in range(100):
            x = 2.5 if index in {10, 55} else 0
            samples.append(MotionSample(x=x, y=0, z=0))
        snapshot = self.run_with_clock(tracker, samples)
        self.assertEqual(snapshot["steps"], 0)
        self.assertEqual(snapshot["activity"], "Idle")

    def test_stationary_gravity_samples_do_not_count_as_steps(self) -> None:
        tracker = SessionTracker()
        samples = [
            MotionSample(
                x=9.8 + (0.08 if index % 2 else -0.08),
                y=0.05 if index % 3 else -0.05,
                z=0,
                includes_gravity=True,
            )
            for index in range(100)
        ]
        snapshot = self.run_with_clock(tracker, samples)
        self.assertEqual(snapshot["steps"], 0)
        self.assertEqual(snapshot["activity"], "Idle")


if __name__ == "__main__":
    unittest.main()
