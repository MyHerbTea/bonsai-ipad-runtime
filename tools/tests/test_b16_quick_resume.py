"""Quick restart checkpoint recovery is fail-closed; no inference is replayed."""
import copy
import tempfile
import unittest
from pathlib import Path
from tools import b16_testkit as kit


class QuickResumeTests(unittest.TestCase):
    def journal(self, root, stop="A2"):
        identity={"build_number": "111", "source_git_sha": "a" * 40}
        journal = kit.Journal(root / "B16-quick", identity)
        previous = ("A1", "B")[:("A1", "B", "A2").index(stop)]
        events = []
        measurements = []
        for label in previous:
            for name in ("arm_next_launch", "restart", "qualification",
                         "quick_medium.0", "quick_medium.1",
                         "quick_long.0", "quick_long.1",
                         "quick_decode.0", "quick_decode.1", "quick_liveness"):
                events.append({"case": label + "." + name, "state": "PASS"})
            for work in ("medium", "long"):
                for rep in range(2):
                    measurements.append({"arm": label, "workload": work, "rep": rep})
        events.append({"case": stop + ".arm_next_launch", "state": "PASS"})
        journal.state.update(
            mode="quick", direction="prefill-batch", status="INCOMPLETE",
            stage=stop + "_restart", events=events, measurements=measurements,
            restart={"label": stop, "arm": "CANDIDATE16" if stop == "B" else "BASELINE8",
                     "phase": "scheduled", "previous": {}},
            waiting_restart=stop,
            inflight=None,
        )
        journal.save()
        return journal

    def test_safe_scheduled_quick_restart_is_resumable_without_replay(self):
        for stop in ("A1", "B", "A2"):
            with self.subTest(stop=stop), tempfile.TemporaryDirectory() as temp:
                old = self.journal(Path(temp), stop)
                kit.quick_resume_boundary(old.state)
                restored = kit.Journal(old.folder, old.state["identity"], resume=True)
                self.assertEqual(restored.state["events"], old.state["events"])
                self.assertEqual(restored.state["measurements"], old.state["measurements"])
                self.assertEqual(restored.state["restart"], old.state["restart"])
                self.assertIsNone(restored.state["inflight"])

    def test_quick_execute_skips_completed_stages_instead_of_replaying(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            journal = self.journal(Path(temp), "A2")
            device = kit.QuickDeviceRun(journal, journal.state["identity"], "http://test", "key")
            with patch.object(device, "restart", side_effect=kit.Incomplete("stop at A2")) as restart, \
                 patch.object(device, "performance") as performance:
                with self.assertRaisesRegex(kit.Incomplete, "stop at A2"):
                    device.execute()
            restart.assert_called_once_with("A2", "BASELINE8")
            performance.assert_not_called()

    def test_unsafe_quick_states_stop_before_loading(self):
        with tempfile.TemporaryDirectory() as temp:
            journal = self.journal(Path(temp))
            old = journal.state
            cases = [
                dict(inflight="A2.quick_medium.0"),
                dict(mode="full"),
                dict(direction="other"),
                dict(restart=None),
                dict(waiting_restart="B"),
                dict(restart={**old["restart"], "arm": "CANDIDATE16"}),
                dict(events=old["events"][:-2] + old["events"][-1:]),
                dict(measurements=old["measurements"][:-1]),
                dict(events=old["events"] + [{"case": "A2.quick_decode.0", "state": "PASS"}]),
                dict(status="FAIL"),
            ]
            for mutation in cases:
                state = copy.deepcopy(old)
                state.update(mutation)
                with self.subTest(mutation=list(mutation)):
                    with self.assertRaises(kit.Incomplete):
                        kit.quick_resume_boundary(state)

    def test_quick_cases_are_registered_for_journal_only(self):
        names = set(kit.quick_cases())
        self.assertIn("A2.quick_liveness", names)
        self.assertIn("B.quick_medium.0", names)
        self.assertNotIn("B.strict_sse", names)
        self.assertIn("B.strict_sse", kit.registered_cases())

    def test_completed_quick_is_terminal_for_latest_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            journal = self.journal(folder)
            journal.state["status"] = "QUICK_COMPLETE"
            journal.save()
            self.assertIsNone(kit.latest_checkpoint(folder))


if __name__ == "__main__":
    unittest.main()
