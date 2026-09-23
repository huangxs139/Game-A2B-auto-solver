"""Tests for the owner-facing candidate review TUI."""

from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.review_candidates import (
    CandidateReviewTUI,
    update_owner_decision,
)


class CandidateReviewTUITests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.state_directory = Path(self.temporary_directory.name)

    def _write_state(
        self,
        problem_id: str,
        status: str = "pending",
        *,
        reason: str | None = None,
    ) -> Path:
        state = {
            "problem_id": problem_id,
            "candidate": "a=b\nbb=b",
            "local_validation": {
                "passed": True,
                "case_count": 2,
                "line_count": 2,
            },
            "status": status,
        }
        if reason is not None:
            state["reason"] = reason
        path = self.state_directory / f"{problem_id}.solve"
        path.write_text(json.dumps(state), encoding="utf-8")
        return path

    def test_review_shows_copyable_candidate_and_records_rejection(self) -> None:
        path = self._write_state("c2_3_demo")
        answers = iter(("2-3", "2", "wrong game output"))
        output = StringIO()
        tui = CandidateReviewTUI(
            self.state_directory,
            input_function=lambda prompt: next(answers),
            output=output,
        )

        self.assertTrue(tui.review_candidates())

        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual("rejected", saved["status"])
        self.assertEqual("wrong game output", saved["reason"])
        self.assertEqual("a=b\nbb=b", saved["candidate"])
        self.assertIn("a=b\nbb=b", output.getvalue())

    def test_acceptance_removes_an_existing_failure_reason(self) -> None:
        path = self._write_state(
            "c1_1_demo", "re-solve", reason="previous mismatch"
        )

        update_owner_decision(path, "accepted")

        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual("accepted", saved["status"])
        self.assertNotIn("reason", saved)
        self.assertEqual(2, saved["local_validation"]["case_count"])

    def test_re_solve_can_record_an_optional_failure_reason(self) -> None:
        path = self._write_state("c3_4_demo")

        update_owner_decision(path, "re-solve", "fails case 12")

        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual("re-solve", saved["status"])
        self.assertEqual("fails case 12", saved["reason"])

    def test_summary_groups_and_numerically_orders_all_statuses(self) -> None:
        self._write_state("c1_10_tenth", "pending")
        self._write_state("c1_2_second", "pending")
        self._write_state("c2_1_yes", "accepted")
        self._write_state("c3_1_no", "rejected", reason="wrong")
        self._write_state("c4_1_again", "re-solve", reason="retry")
        output = StringIO()
        tui = CandidateReviewTUI(self.state_directory, output=output)

        tui.show_summary()

        text = output.getvalue()
        self.assertIn(
            "STATUS     COUNT  PUZZLES",
            text,
        )
        self.assertRegex(text, r"accepted\s+1\s+c2_1_yes")
        self.assertRegex(text, r"rejected\s+1\s+c3_1_no")
        self.assertRegex(text, r"re-solve\s+1\s+c4_1_again")
        self.assertRegex(text, r"pending\s+2\s+c1_2_second, c1_10_tenth")
        self.assertLess(text.index("c1_2_second"), text.index("c1_10_tenth"))

    def test_review_accepts_underscore_coordinate_and_saves_without_confirmation(
        self,
    ) -> None:
        path = self._write_state("c4_6_demo")
        answers = iter(("4_6", "1", "q"))
        output = StringIO()
        tui = CandidateReviewTUI(
            self.state_directory,
            input_function=lambda prompt: next(answers),
            output=output,
        )

        self.assertFalse(tui.review_candidates())

        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual("accepted", saved["status"])
        self.assertIn("Saved c4_6_demo as accepted.", output.getvalue())

    def test_review_uses_accepted_default_and_enter_keeps_current_status(
        self,
    ) -> None:
        path = self._write_state("c2_4_done", "accepted")
        answers = iter(("", "", "q"))
        prompts: list[str] = []
        output = StringIO()

        def answer(prompt: str) -> str:
            prompts.append(prompt)
            return next(answers)

        tui = CandidateReviewTUI(
            self.state_directory,
            input_function=answer,
            output=output,
        )

        self.assertFalse(tui.review_candidates())

        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual("accepted", saved["status"])
        self.assertTrue(
            any("Puzzle coordinate [2-4]" in prompt for prompt in prompts)
        )
        self.assertIn("Test result [keep]: ", prompts)
        self.assertIn("[Enter] Keep current status", output.getvalue())
        self.assertIn("No change made.", output.getvalue())

    def test_review_continues_with_next_pending_candidate_as_default(self) -> None:
        first = self._write_state("c1_1_first")
        second = self._write_state("c1_2_second")
        answers = iter(
            ("", "1", "", "3", "needs another solution", "q")
        )
        prompts: list[str] = []
        output = StringIO()

        def answer(prompt: str) -> str:
            prompts.append(prompt)
            return next(answers)

        tui = CandidateReviewTUI(
            self.state_directory,
            input_function=answer,
            output=output,
        )

        self.assertFalse(tui.review_candidates())

        first_state = json.loads(first.read_text(encoding="utf-8"))
        second_state = json.loads(second.read_text(encoding="utf-8"))
        self.assertEqual("accepted", first_state["status"])
        self.assertEqual("re-solve", second_state["status"])
        self.assertEqual("needs another solution", second_state["reason"])
        self.assertTrue(any("Puzzle coordinate [1-1]" in prompt for prompt in prompts))
        self.assertTrue(any("Puzzle coordinate [1-2]" in prompt for prompt in prompts))
        self.assertGreaterEqual(output.getvalue().count("\033[2J\033[H"), 3)

    def test_run_starts_in_review_flow_with_status_summary(self) -> None:
        self._write_state("c1_1_demo", "accepted")
        answers = iter(("q",))
        prompts: list[str] = []
        output = StringIO()

        def answer(prompt: str) -> str:
            prompts.append(prompt)
            return next(answers)

        tui = CandidateReviewTUI(
            self.state_directory,
            input_function=answer,
            output=output,
        )

        exit_code = tui.run()

        self.assertEqual(0, exit_code)
        text = output.getvalue()
        self.assertTrue(text.startswith("\033[2J\033[HA2B Candidate Review"))
        self.assertIn("Status summary", text)
        self.assertNotIn("[s] Status summary", text)
        self.assertEqual(1, len(prompts))
        self.assertIn("Puzzle coordinate [1-1]", prompts[0])
        self.assertIn("Review tool closed.", text)


if __name__ == "__main__":
    unittest.main()
