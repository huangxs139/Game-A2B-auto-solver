"""Common lifecycle framework used by A=B Solver algorithms.

This module deliberately does not implement a search strategy or Manager-owned
full validation.  It gives chapter-specific algorithms a small protocol for
proposing serialized candidates and receiving Executor trial results.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from src.executor import (
    DEFAULT_RULES_PATH,
    ExecutionResult,
    Executor,
    TerminationKind,
)


DEFAULT_PUZZLE_DIRECTORY = Path(__file__).resolve().parents[1] / "test_data"


class PuzzleResolutionError(ValueError):
    """Raised when an authoritative puzzle input cannot be safely resolved."""


class SolverExecutionError(RuntimeError):
    """Raised when Executor infrastructure prevents trustworthy search feedback."""


@dataclass(frozen=True)
class Puzzle:
    """The Solver-relevant, immutable portion of one ``.a2b`` input."""

    problem_id: str
    chapter: int
    min_lines: int
    inputs: tuple[str, ...]
    expected_outputs: tuple[str, ...]


class PuzzleRepository:
    """Read and validate authoritative puzzle inputs without modifying them."""

    def __init__(self, directory: Path | str = DEFAULT_PUZZLE_DIRECTORY) -> None:
        self.directory = Path(directory)

    def resolve(self, problem_id: str) -> Puzzle:
        if not problem_id or Path(problem_id).name != problem_id:
            raise PuzzleResolutionError(f"invalid puzzle identifier: {problem_id!r}")

        path = self.directory / f"{problem_id}.a2b"
        try:
            with path.open(encoding="utf-8") as stream:
                raw = json.load(stream)
        except OSError as exc:
            raise PuzzleResolutionError(f"cannot read puzzle {problem_id!r}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise PuzzleResolutionError(f"invalid JSON in puzzle {problem_id!r}: {exc}") from exc

        if not isinstance(raw, dict):
            raise PuzzleResolutionError(f"puzzle {problem_id!r} must contain a JSON object")
        if raw.get("id") != problem_id:
            raise PuzzleResolutionError(
                f"puzzle filename and id disagree for {problem_id!r}"
            )

        chapter = raw.get("chapter")
        min_lines = raw.get("min_lines")
        inputs = raw.get("input")
        expected_outputs = raw.get("output")
        if not isinstance(chapter, int) or isinstance(chapter, bool) or chapter < 1:
            raise PuzzleResolutionError(f"puzzle {problem_id!r} has an invalid chapter")
        if not isinstance(min_lines, int) or isinstance(min_lines, bool) or min_lines < 0:
            raise PuzzleResolutionError(f"puzzle {problem_id!r} has an invalid min_lines")
        if not isinstance(inputs, list) or not all(isinstance(value, str) for value in inputs):
            raise PuzzleResolutionError(f"puzzle {problem_id!r} has invalid input cases")
        if not isinstance(expected_outputs, list) or not all(
            isinstance(value, str) for value in expected_outputs
        ):
            raise PuzzleResolutionError(f"puzzle {problem_id!r} has invalid output cases")
        if len(inputs) != len(expected_outputs):
            raise PuzzleResolutionError(
                f"puzzle {problem_id!r} has unequal input/output case counts"
            )

        return Puzzle(
            problem_id=problem_id,
            chapter=chapter,
            min_lines=min_lines,
            inputs=tuple(inputs),
            expected_outputs=tuple(expected_outputs),
        )


@dataclass(frozen=True)
class SolverContext:
    """Stable information supplied to a concrete Solver algorithm."""

    puzzle: Puzzle
    rules_path: Path


@dataclass(frozen=True)
class CandidateProposal:
    """A serialized candidate and the cases requested for a search-time trial.

    ``case_indices=None`` requests all cases.  ``submit=True`` tells the
    framework that this proposal is the algorithm's final submission; Manager
    must still perform authoritative full local validation later.
    """

    code: str
    case_indices: tuple[int, ...] | None = None
    submit: bool = False


@dataclass(frozen=True)
class TrialResult:
    """One Executor invocation and its expected-output comparison."""

    case_index: int
    input_text: str
    expected_output: str
    execution: ExecutionResult
    matches_expected_output: bool


@dataclass(frozen=True)
class CandidateFeedback:
    """Structured result returned to an algorithm after each proposal."""

    proposal: CandidateProposal
    trials: tuple[TrialResult, ...]

    @property
    def passed(self) -> bool:
        return all(
            trial.matches_expected_output and trial.execution.terminated_normally
            for trial in self.trials
        )


@dataclass(frozen=True)
class SolverRunResult:
    """The submitted candidate plus the complete local search-time trace."""

    submitted_code: str
    feedback_history: tuple[CandidateFeedback, ...]


class SolvingAlgorithm(Protocol):
    """Protocol implemented by concrete, potentially chapter-specific algorithms."""

    def propose(self, feedback: CandidateFeedback | None) -> CandidateProposal:
        """Return the next tentative candidate or a final submission."""


AlgorithmFactory = Callable[[SolverContext], SolvingAlgorithm]


class SolverFramework:
    """Run the common Solver candidate/feedback lifecycle for one puzzle."""

    def __init__(
        self,
        *,
        puzzle_repository: PuzzleRepository | None = None,
        rules_path: Path | str = DEFAULT_RULES_PATH,
    ) -> None:
        self._puzzle_repository = puzzle_repository or PuzzleRepository()
        self._rules_path = Path(rules_path)

    def solve(
        self,
        problem_id: str,
        algorithm_factory: AlgorithmFactory,
        *,
        debug: bool = False,
    ) -> SolverRunResult:
        """Run until the algorithm submits a candidate or raises an error.

        Candidate failures remain ordinary feedback.  Executor infrastructure
        failures and algorithm exceptions propagate as abnormal Solver errors.
        """

        puzzle = self._puzzle_repository.resolve(problem_id)
        context = SolverContext(puzzle=puzzle, rules_path=self._rules_path)
        algorithm = algorithm_factory(context)
        executor = Executor(puzzle.chapter, rules_path=self._rules_path)

        history: list[CandidateFeedback] = []
        feedback: CandidateFeedback | None = None
        while True:
            proposal = algorithm.propose(feedback)
            self._validate_proposal(proposal, len(puzzle.inputs))
            feedback = self._trial_candidate(executor, puzzle, proposal, debug=debug)
            history.append(feedback)
            if proposal.submit:
                return SolverRunResult(proposal.code, tuple(history))

    @staticmethod
    def _validate_proposal(proposal: CandidateProposal, case_count: int) -> None:
        if not isinstance(proposal, CandidateProposal):
            raise TypeError("SolvingAlgorithm.propose must return CandidateProposal")
        if not isinstance(proposal.code, str):
            raise TypeError("candidate code must be a string")
        if proposal.case_indices is None:
            return
        if not proposal.case_indices:
            raise ValueError("candidate proposal must select at least one trial case")
        if len(set(proposal.case_indices)) != len(proposal.case_indices):
            raise ValueError("candidate proposal contains duplicate case indices")
        if any(
            not isinstance(index, int)
            or isinstance(index, bool)
            or index < 0
            or index >= case_count
            for index in proposal.case_indices
        ):
            raise ValueError("candidate proposal contains an invalid case index")

    @staticmethod
    def _trial_candidate(
        executor: Executor,
        puzzle: Puzzle,
        proposal: CandidateProposal,
        *,
        debug: bool,
    ) -> CandidateFeedback:
        indices = proposal.case_indices or tuple(range(len(puzzle.inputs)))
        trials: list[TrialResult] = []
        for index in indices:
            execution = executor.execute(puzzle.inputs[index], proposal.code, debug=debug)
            if execution.termination is TerminationKind.EXECUTOR_ERROR:
                raise SolverExecutionError(
                    f"Executor failed while testing {puzzle.problem_id!r} case {index}: "
                    f"{'; '.join(execution.errors)}"
                )
            trials.append(
                TrialResult(
                    case_index=index,
                    input_text=puzzle.inputs[index],
                    expected_output=puzzle.expected_outputs[index],
                    execution=execution,
                    matches_expected_output=(
                        execution.output == puzzle.expected_outputs[index]
                    ),
                )
            )
        return CandidateFeedback(proposal=proposal, trials=tuple(trials))
