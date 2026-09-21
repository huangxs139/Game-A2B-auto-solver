"""Verification for the common Solver algorithm/Executor lifecycle."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.executor import TerminationKind
from src.solver import (
    CandidateFeedback,
    CandidateProposal,
    PuzzleRepository,
    SolverContext,
    SolverFramework,
    create_solver_algorithm,
)


class _TwoStepAlgorithm:
    def __init__(self, context: SolverContext) -> None:
        self.context = context
        self.feedbacks: list[CandidateFeedback | None] = []

    def propose(self, feedback: CandidateFeedback | None) -> CandidateProposal:
        self.feedbacks.append(feedback)
        if feedback is None:
            return CandidateProposal("a=c", case_indices=(0,))
        if not feedback.passed:
            return CandidateProposal("a=b", submit=True)
        raise AssertionError("the tentative candidate should have failed")


class _FailingAlgorithm:
    def propose(self, feedback: CandidateFeedback | None) -> CandidateProposal:
        raise RuntimeError("algorithm failure")


class SolverFrameworkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.puzzle_directory = Path(self.temporary_directory.name)
        (self.puzzle_directory / "c1_1_demo.a2b").write_text(
            json.dumps(
                {
                    "id": "c1_1_demo",
                    "chapter": 1,
                    "min_lines": 1,
                    "input": ["a", "c"],
                    "output": ["b", "c"],
                }
            ),
            encoding="utf-8",
        )

    def test_resolves_puzzle_invokes_algorithm_and_returns_feedback(self) -> None:
        algorithm_holder: list[_TwoStepAlgorithm] = []

        def make_algorithm(context: SolverContext) -> _TwoStepAlgorithm:
            algorithm = _TwoStepAlgorithm(context)
            algorithm_holder.append(algorithm)
            return algorithm

        result = SolverFramework(
            puzzle_repository=PuzzleRepository(self.puzzle_directory)
        ).solve("c1_1_demo", make_algorithm, debug=True)

        algorithm = algorithm_holder[0]
        self.assertEqual("c1_1_demo", algorithm.context.puzzle.problem_id)
        self.assertTrue(algorithm.context.rules_path.is_file())
        self.assertEqual(2, len(algorithm.feedbacks))
        first_feedback = algorithm.feedbacks[1]
        assert first_feedback is not None
        self.assertFalse(first_feedback.passed)
        self.assertEqual((0,), tuple(case.case_index for case in first_feedback.trials))
        self.assertEqual(TerminationKind.NORMAL, first_feedback.trials[0].execution.termination)
        self.assertEqual("c", first_feedback.trials[0].execution.output)
        self.assertEqual("a=b", result.submitted_code)
        self.assertEqual(2, len(result.feedback_history))
        self.assertTrue(result.feedback_history[-1].passed)
        self.assertEqual(2, len(result.feedback_history[-1].trials))
        self.assertTrue(result.feedback_history[0].trials[0].execution.observations)

    def test_algorithm_failure_propagates_abnormally(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "algorithm failure"):
            SolverFramework(
                puzzle_repository=PuzzleRepository(self.puzzle_directory)
            ).solve("c1_1_demo", lambda context: _FailingAlgorithm())

    def test_rejects_unknown_or_malformed_puzzle_data(self) -> None:
        repository = PuzzleRepository(self.puzzle_directory)
        with self.assertRaisesRegex(ValueError, "cannot read puzzle"):
            repository.resolve("c1_99_missing")

        (self.puzzle_directory / "c1_2_bad.a2b").write_text(
            json.dumps(
                {
                    "id": "c1_2_bad",
                    "chapter": 1,
                    "min_lines": 1,
                    "input": ["a"],
                    "output": [],
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "unequal input/output"):
            repository.resolve("c1_2_bad")


class _ChapterSynthesisTestCase(unittest.TestCase):
    def _assert_chapter_is_solved(self, chapter: int, expected_count: int) -> None:
        framework = SolverFramework()
        problem_ids = sorted(
            path.stem for path in Path("test_data").glob(f"c{chapter}_*.a2b")
        )

        self.assertEqual(expected_count, len(problem_ids))
        for problem_id in problem_ids:
            with self.subTest(problem_id=problem_id):
                result = framework.solve(problem_id, create_solver_algorithm)
                puzzle = PuzzleRepository().resolve(problem_id)

                self.assertGreaterEqual(len(result.feedback_history), 2)
                self.assertFalse(result.feedback_history[0].proposal.submit)
                self.assertTrue(result.feedback_history[-1].passed)
                self.assertTrue(result.feedback_history[-1].proposal.submit)
                self.assertLessEqual(
                    len(result.submitted_code.splitlines()), puzzle.min_lines
                )


class ChapterOneSynthesisTests(_ChapterSynthesisTestCase):
    def test_synthesizes_every_chapter_one_candidate_from_puzzle_data(self) -> None:
        self._assert_chapter_is_solved(1, 6)


class ChapterTwoSynthesisTests(_ChapterSynthesisTestCase):
    def test_synthesizes_every_chapter_two_candidate_from_puzzle_data(self) -> None:
        self._assert_chapter_is_solved(2, 9)


class ChapterThreeSynthesisTests(_ChapterSynthesisTestCase):
    def test_synthesizes_every_chapter_three_candidate_from_puzzle_data(self) -> None:
        self._assert_chapter_is_solved(3, 7)


class ChapterFourSynthesisTests(_ChapterSynthesisTestCase):
    def test_synthesizes_every_chapter_four_candidate_from_puzzle_data(self) -> None:
        self._assert_chapter_is_solved(4, 16)


class ChapterFiveSynthesisTests(_ChapterSynthesisTestCase):
    def test_synthesizes_every_chapter_five_candidate_from_puzzle_data(self) -> None:
        self._assert_chapter_is_solved(5, 6)


class ChapterSixSynthesisTests(_ChapterSynthesisTestCase):
    def test_synthesizes_every_chapter_six_candidate_from_puzzle_data(self) -> None:
        self._assert_chapter_is_solved(6, 3)


if __name__ == "__main__":
    unittest.main()
