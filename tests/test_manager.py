"""Verification for the Manager-owned integrated workflow."""

from __future__ import annotations

from io import StringIO
import json
import multiprocessing as mp
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Timer
import time
import unittest
from unittest.mock import patch

from src.executor import TerminationKind
from src.manager import (
    Manager,
    PuzzleStateError,
    PuzzleStateRepository,
    RunSummary,
    ValidationOutcome,
    build_argument_parser,
    main,
    validate_candidate,
)
from src.solver import create_solver_algorithm
from src.solver_framework import (
    CandidateFeedback,
    CandidateProposal,
    PuzzleRepository,
    SolverContext,
)


class _ImmediateAlgorithm:
    def __init__(self, context: SolverContext) -> None:
        self._code = "a=b"

    def propose(self, feedback: CandidateFeedback | None) -> CandidateProposal:
        return CandidateProposal(self._code, submit=True)


class _RetryAlgorithm:
    def __init__(self, context: SolverContext) -> None:
        self._attempt = 0

    def propose(self, feedback: CandidateFeedback | None) -> CandidateProposal:
        self._attempt += 1
        if self._attempt == 1:
            return CandidateProposal("a=c", submit=True)
        if feedback is None or feedback.passed:
            raise AssertionError("Manager validation failure was not returned")
        return CandidateProposal("a=b", submit=True)


class _ReplacementAlgorithm:
    def __init__(self, context: SolverContext) -> None:
        self._attempt = 0

    def propose(self, feedback: CandidateFeedback | None) -> CandidateProposal:
        self._attempt += 1
        if self._attempt == 1:
            return CandidateProposal("a=b", submit=True)
        if feedback is None or not any(
            "identical" in reason for reason in feedback.failure_reasons
        ):
            raise AssertionError("duplicate replacement feedback was not returned")
        return CandidateProposal("a=c\nc=b", submit=True)


class _FailingAlgorithm:
    def __init__(self, context: SolverContext) -> None:
        pass

    def propose(self, feedback: CandidateFeedback | None) -> CandidateProposal:
        raise RuntimeError("controlled Solver failure")


class _SlowAlgorithm:
    def __init__(self, context: SolverContext) -> None:
        pass

    def propose(self, feedback: CandidateFeedback | None) -> CandidateProposal:
        time.sleep(10)
        return CandidateProposal("a=b", submit=True)


def _make_immediate_algorithm(context: SolverContext) -> _ImmediateAlgorithm:
    return _ImmediateAlgorithm(context)


def _make_retry_algorithm(context: SolverContext) -> _RetryAlgorithm:
    return _RetryAlgorithm(context)


def _make_replacement_algorithm(context: SolverContext) -> _ReplacementAlgorithm:
    return _ReplacementAlgorithm(context)


def _make_failing_algorithm(context: SolverContext) -> _FailingAlgorithm:
    return _FailingAlgorithm(context)


def _make_slow_algorithm(context: SolverContext) -> _SlowAlgorithm:
    return _SlowAlgorithm(context)


class ManagerWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.puzzle_directory = self.root / "test_data"
        self.output_directory = self.root / "test_output"
        self.report_directory = self.root / "reports"
        self.puzzle_directory.mkdir()
        self.context = mp.get_context("spawn")

    def _write_puzzle(
        self, problem_id: str, chapter: int, *, min_lines: int = 1
    ) -> None:
        (self.puzzle_directory / f"{problem_id}.a2b").write_text(
            json.dumps(
                {
                    "id": problem_id,
                    "chapter": chapter,
                    "min_lines": min_lines,
                    "input": ["a"],
                    "output": ["b"],
                }
            ),
            encoding="utf-8",
        )

    def _write_state(
        self,
        problem_id: str,
        status: str,
        *,
        reason: str | None = None,
        candidate: str = "a=b",
    ) -> None:
        self.output_directory.mkdir(exist_ok=True)
        state = {
            "problem_id": problem_id,
            "candidate": candidate,
            "local_validation": {
                "passed": True,
                "case_count": 1,
                "line_count": 1,
            },
            "status": status,
        }
        if reason is not None:
            state["reason"] = reason
        (self.output_directory / f"{problem_id}.solve").write_text(
            json.dumps(state), encoding="utf-8"
        )

    def _manager(self, algorithm_factory, *, max_concurrency: int = 1) -> Manager:
        return Manager(
            puzzle_directory=self.puzzle_directory,
            output_directory=self.output_directory,
            report_directory=self.report_directory,
            max_concurrency=max_concurrency,
            algorithm_factory=algorithm_factory,
            output=StringIO(),
            mp_context=self.context,
        )

    def test_status_eligibility_persistence_and_chapter_advancement(self) -> None:
        statuses = ("pending", "accepted", "rejected", "re-solve")
        for number, status in enumerate(statuses, 1):
            problem_id = f"c1_{number}_{status.replace('-', '')}"
            self._write_puzzle(problem_id, 1)
            self._write_state(
                problem_id,
                status,
                reason="try again" if status == "re-solve" else None,
                candidate="a=b# old" if status == "re-solve" else "a=b",
            )
        self._write_puzzle("c1_5_missing", 1)
        self._write_puzzle("c1_6_initial", 1)
        self.output_directory.mkdir(exist_ok=True)
        (self.output_directory / "c1_6_initial.solve").write_text(
            json.dumps({"problem_id": "c1_6_initial"}), encoding="utf-8"
        )

        summary = self._manager(_make_immediate_algorithm).solve_all()

        self.assertEqual(6, summary.discovered)
        self.assertEqual(3, summary.eligible)
        self.assertEqual(3, summary.skipped)
        self.assertEqual(3, summary.solved)
        self.assertEqual(4, summary.pending_owner_validation)
        for problem_id in ("c1_4_resolve", "c1_5_missing", "c1_6_initial"):
            state = PuzzleStateRepository(self.output_directory).load(problem_id)
            assert state is not None
            self.assertEqual("pending", state.status)
            self.assertIsNone(state.reason)
            self.assertEqual("a=b", state.candidate)

    def test_validation_failure_returns_to_same_solver_instance(self) -> None:
        self._write_puzzle("c1_1_retry", 1)

        summary = self._manager(_make_retry_algorithm).solve_all(debug=True)

        self.assertEqual(1, summary.validation_failures)
        self.assertEqual(1, summary.solved)
        state = PuzzleStateRepository(self.output_directory).load("c1_1_retry")
        assert state is not None
        self.assertEqual("a=b", state.candidate)
        reports = tuple(self.report_directory.glob("c1_1_retry_*.report.json"))
        self.assertEqual(4, len(reports))

    def test_re_solve_rejects_identical_candidate_and_persists_replacement(
        self,
    ) -> None:
        self._write_puzzle("c1_1_resolve", 1, min_lines=2)
        self._write_state(
            "c1_1_resolve",
            "re-solve",
            reason="replace this candidate",
        )

        summary = self._manager(_make_replacement_algorithm).solve_all(debug=True)

        self.assertEqual(1, summary.validation_failures)
        self.assertEqual(1, summary.solved)
        state = PuzzleStateRepository(self.output_directory).load("c1_1_resolve")
        assert state is not None
        self.assertEqual("a=c\nc=b", state.candidate)
        self.assertEqual("pending", state.status)
        self.assertIsNone(state.reason)
        reports = tuple(self.report_directory.glob("c1_1_resolve_*.report.json"))
        self.assertEqual(4, len(reports))

    def test_runs_different_chapters_concurrently(self) -> None:
        self._write_puzzle("c1_1_first", 1)
        self._write_puzzle("c2_1_second", 2)

        summary = self._manager(
            _make_immediate_algorithm, max_concurrency=2
        ).solve_all()

        self.assertEqual(2, summary.solved)
        self.assertEqual(2, summary.max_active_chapters)

    def test_solver_error_is_fail_fast(self) -> None:
        self._write_puzzle("c1_1_failure", 1)
        self._write_puzzle("c2_1_unrelated", 2)

        summary = self._manager(
            _make_failing_algorithm, max_concurrency=2
        ).solve_all()

        self.assertEqual(1, summary.exit_code)
        self.assertIn("controlled Solver failure", summary.fatal_error or "")
        self.assertFalse(self.output_directory.exists())
        self.assertEqual(
            1,
            len(tuple(self.report_directory.glob("c1_1_failure_*.report.json"))),
        )

    def test_graceful_stop_terminates_active_process_and_writes_report(self) -> None:
        self._write_puzzle("c1_1_slow", 1)
        manager = self._manager(_make_slow_algorithm)
        timer = Timer(0.1, manager.request_stop)
        timer.start()
        self.addCleanup(timer.cancel)

        summary = manager.solve_all()

        self.assertTrue(summary.interrupted)
        self.assertEqual(130, summary.exit_code)
        self.assertEqual(
            1,
            len(tuple(self.report_directory.glob("c1_1_slow_*.report.json"))),
        )
        self.assertFalse(self.output_directory.exists())

    def test_targeted_debug_does_not_overwrite_authoritative_state(self) -> None:
        self._write_puzzle("c1_1_target", 1)
        self._write_state("c1_1_target", "accepted")
        state_path = self.output_directory / "c1_1_target.solve"
        before = state_path.read_text(encoding="utf-8")

        summary = self._manager(_make_immediate_algorithm).solve_target(
            "c1_1_target"
        )

        self.assertEqual(1, summary.solved)
        self.assertEqual(before, state_path.read_text(encoding="utf-8"))
        self.assertEqual(
            2,
            len(tuple(self.report_directory.glob("c1_1_target_*.report.json"))),
        )

    def test_debug_reports_include_executor_observations_from_search_and_validation(
        self,
    ) -> None:
        self._write_puzzle("c1_1_diagnostics", 1)

        summary = self._manager(_make_immediate_algorithm).solve_target(
            "c1_1_diagnostics"
        )

        self.assertEqual(0, summary.exit_code)
        reports = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in self.report_directory.glob("c1_1_diagnostics_*.report.json")
        ]
        by_event = {report["event"]: report["details"] for report in reports}
        search_trial = by_event["search_diagnostics"]["feedback_events"][0]["trials"][0]
        validation_trial = by_event["validation_pass"]["debug_trials"][0]
        self.assertEqual("a", search_trial["observations"][0]["before"])
        self.assertEqual("b", validation_trial["observations"][0]["after"])

    def test_corrupted_owner_state_is_rejected(self) -> None:
        self._write_puzzle("c1_1_badstate", 1)
        self._write_state("c1_1_badstate", "unknown")

        with self.assertRaises(PuzzleStateError):
            self._manager(_make_immediate_algorithm).solve_all()

    def test_raw_lines_count_toward_min_lines(self) -> None:
        self._write_puzzle("c1_1_lines", 1)
        puzzle = PuzzleRepository(self.puzzle_directory).resolve("c1_1_lines")

        result = validate_candidate(puzzle, "# comment\na=b")

        self.assertEqual(ValidationOutcome.FAIL, result.outcome)
        self.assertEqual(2, result.line_count)
        assert result.feedback is not None
        self.assertIn("2 lines", result.feedback.failure_reasons[0])

    def test_length_limit_violation_is_a_candidate_failure(self) -> None:
        self._write_puzzle("c1_1_length", 1)
        puzzle = PuzzleRepository(self.puzzle_directory).resolve("c1_1_length")
        candidate = "a=b#" + "x" * 251

        result = validate_candidate(puzzle, candidate)

        self.assertEqual(ValidationOutcome.FAIL, result.outcome)
        self.assertIsNone(result.error)
        assert result.feedback is not None
        self.assertEqual(1, len(result.feedback.trials))
        self.assertEqual(
            TerminationKind.INVALID_PROGRAM,
            result.feedback.trials[0].execution.termination,
        )

    def test_validation_infrastructure_error_is_distinct_from_candidate_failure(
        self,
    ) -> None:
        self._write_puzzle("c1_1_error", 1)
        puzzle = PuzzleRepository(self.puzzle_directory).resolve("c1_1_error")

        result = validate_candidate(
            puzzle,
            "a=b",
            rules_path=self.root / "missing-rules.yaml",
        )

        self.assertEqual(ValidationOutcome.ERROR, result.outcome)
        self.assertIsNotNone(result.error)
        self.assertIsNone(result.feedback)

    def test_real_solver_runs_through_targeted_manager_entry(self) -> None:
        project_puzzles = Path(__file__).resolve().parents[1] / "test_data"
        problem_id = sorted(project_puzzles.glob("c1_*.a2b"))[0].stem
        manager = Manager(
            puzzle_directory=project_puzzles,
            output_directory=self.output_directory,
            report_directory=self.report_directory,
            algorithm_factory=create_solver_algorithm,
            output=StringIO(),
            mp_context=self.context,
        )

        summary = manager.solve_target(problem_id)

        self.assertEqual(0, summary.exit_code)
        self.assertEqual(1, summary.solved)
        self.assertFalse(self.output_directory.exists())
        self.assertEqual(
            2,
            len(tuple(self.report_directory.glob(f"{problem_id}_*.report.json"))),
        )

    def test_cli_parser_exposes_solve_all_and_targeted_debug(self) -> None:
        parser = build_argument_parser()

        all_args = parser.parse_args(["solve", "all", "--max-concurrency", "2"])
        target_args = parser.parse_args(["solve", "c1_1_demo", "--debug"])

        self.assertEqual(("solve", "all", 2), (
            all_args.command,
            all_args.target,
            all_args.max_concurrency,
        ))
        self.assertEqual("c1_1_demo", target_args.target)
        self.assertTrue(target_args.debug)

    def test_cli_entry_runs_solve_all_and_returns_summary_exit_code(self) -> None:
        summary = RunSummary(
            discovered=1,
            eligible=0,
            skipped=1,
            solved=0,
            validation_failures=0,
            pending_owner_validation=1,
            accepted=0,
            rejected=0,
            interrupted=False,
            fatal_error=None,
            max_active_chapters=0,
        )
        with patch("src.manager.Manager") as manager_class:
            manager_class.return_value.solve_all.return_value = summary

            exit_code = main(["solve", "all", "--max-concurrency", "2"])

        self.assertEqual(0, exit_code)
        manager_class.assert_called_once_with(max_concurrency=2)
        manager_class.return_value.solve_all.assert_called_once_with(debug=False)


if __name__ == "__main__":
    unittest.main()
