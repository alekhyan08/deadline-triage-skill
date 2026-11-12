"""Standalone tests for the deadline-triage helper. Run: python3 -m unittest discover -s tests"""
import json
import runpy
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills/deadline-triage/scripts/triage.py"


class TriageTests(unittest.TestCase):
    def setUp(self):
        self.ns = runpy.run_path(str(SCRIPT))
        self.triage = self.ns["triage"]
        self.request = {"as_of": "2026-11-11T16:00:00+00:00", "timezone": "America/Los_Angeles", "messages": []}

    def message(self, ident="m1", **fields):
        base = dict(id=ident, thread="t1", received_at="2026-11-11T15:00:00+00:00", subject="Synthetic",
                    body="Deadline: 2026-11-12", unread=True, starred=False, draft=False)
        return base | fields

    def first(self, *messages):
        self.request["messages"] = list(messages)
        return self.triage(self.request)["items"][0]

    def test_latest_message_in_thread_wins(self):
        row = self.first(self.message("old", body="Deadline: 2026-11-10", received_at="2026-11-10T15:00:00+00:00"),
                         self.message("new", body="Deadline: 2026-11-13", unread=False))
        self.assertEqual((row["source_id"], row["deadline"], row["priority"]), ("new", "2026-11-13", "due_soon"))

    def test_relative_dates_use_the_message_date(self):
        row = self.first(self.message(body="Due: tomorrow", received_at="2026-11-10T15:00:00+00:00"))
        self.assertEqual((row["deadline"], row["priority"]), ("2026-11-11", "due_today"))

    def test_full_date_phrases(self):
        for body, deadline in (("The report is due by Friday, 13 November 2026 at 17:00 PST.", "2026-11-13"),
                               ("Deadline is November 15, 2026.", "2026-11-15"), ("Due on 2026-11-12 please confirm.", "2026-11-12")):
            self.assertEqual(self.first(self.message(body=body))["deadline"], deadline, body)

    def test_never_guesses(self):
        for body in ("due by Friday, 14 November 2026", "due 13 November", "due by 13 November 2026 or maybe 15 November 2026",
                     "Please finish next Friday", "Deadline: 2026-13-44", "Deadline: 2026-11-11\nDeadline: 2026-11-12"):
            row = self.first(self.message(body=body))
            self.assertEqual(row["priority"], "needs_review", body)
            self.assertIsNone(row["deadline"])

    def test_resolved_status_and_drafts(self):
        row = self.first(self.message("old", body="Deadline: 2026-11-10", received_at="2026-11-10T15:00:00+00:00"),
                         self.message("done", body="Status: resolved"), self.message("draft", body="Deadline: 2026-11-10", draft=True))
        self.assertEqual((row["source_id"], row["priority"], row["deadline"]), ("done", "resolved", None))

    def test_invalid_inputs_are_refused(self):
        for messages in ([self.message(received_at="2026-11-11T15:00:00")], [self.message(received_at="2026-11-12T15:00:00+00:00")],
                         [self.message(), self.message()], [self.message(body_complete=False)]):
            self.request["messages"] = messages
            with self.assertRaises(ValueError):
                self.triage(self.request)

    def test_text_output_and_cli(self):
        self.request["messages"] = [self.message("a", thread="a", body="Deadline: 2026-11-10", subject="Overdue thing"),
                                    self.message("c", thread="c", body="nothing here", subject="Newsletter")]
        text = self.ns["format_text"](self.triage(self.request))
        self.assertIn("OVERDUE", text.splitlines()[1])
        self.assertIn("NEEDS REVIEW", text.splitlines()[2])
        done = subprocess.run([sys.executable, str(SCRIPT), "--text"], input=json.dumps(self.request), text=True,
                              capture_output=True, timeout=10)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("Overdue thing", done.stdout)


if __name__ == "__main__":
    unittest.main()
