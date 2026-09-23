"""Manager-owned orchestration for the integrated A=B solving workflow."""

from __future__ import annotations

import argparse
from io import StringIO
import json
import multiprocessing as mp
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
import re
import signal
import sys
from tempfile import NamedTemporaryFile
from threading import Event
import time
import traceback
from typing import Sequence, TextIO
from uuid import uuid4

from src.executor import DEFAULT_RULES_PATH, Executor, TerminationKind
from src.solver import create_solver_algorithm
from src.solver_framework import (
    AlgorithmFactory,
    CandidateFeedback,
    CandidateProposal,
    Puzzle,
    PuzzleRepository,
    SolverFramework,
    TrialResult,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIRECTORY = PROJECT_ROOT / "test_output"
DEFAULT_REPORT_DIRECTORY = PROJECT_ROOT / "reports"
_PROBLEM_ID_PATTERN = re.compile(r"^c(?P<chapter>\d+)_(?P<number>\d+)_.+$")
_OWNER_STATUSES = frozenset({"pending", "accepted", "rejected", "re-solve"})


class ManagerError(RuntimeError):
    """Raised when integrated execution can no longer continue safely."""


class PuzzleStateError(ManagerError):
    """Raised when persisted puzzle state is malformed or inconsistent."""


class ValidationOutcome(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"


@dataclass(frozen=True)
class PuzzleState:
    problem_id: str
    candidate: str | None
    status: str | None
    reason: str | None
    local_validation: dict[str, object] | None

    @property
    def requires_solver(self) -> bool:
        return self.candidate is None or self.status == "re-solve"


@dataclass(frozen=True)
class ValidationResult:
    problem_id: str
    outcome: ValidationOutcome
    candidate: str
    line_count: int
    case_count: int
    elapsed_seconds: float
    feedback: CandidateFeedback | None = None
    error: str | None = None
    debug_trials: tuple[TrialResult, ...] = ()


@dataclass(frozen=True)
class RunSummary:
    discovered: int
    eligible: int
    skipped: int
    solved: int
    validation_failures: int
    pending_owner_validation: int
    accepted: int
    rejected: int
    interrupted: bool
    fatal_error: str | None
    max_active_chapters: int

    @property
    def exit_code(self) -> int:
        if self.fatal_error is not None:
            return 1
        if self.interrupted:
            return 130
        return 0


@dataclass(frozen=True)
class _StartPuzzle:
    problem_id: str


@dataclass(frozen=True)
class _ValidationPassed:
    pass


@dataclass(frozen=True)
class _ValidationFailed:
    feedback: CandidateFeedback


@dataclass(frozen=True)
class _StopWorker:
    pass


@dataclass(frozen=True)
class _CandidateSubmitted:
    problem_id: str
    candidate: str
    search_feedback_count: int
    search_feedback_history: tuple[CandidateFeedback, ...] = ()


@dataclass(frozen=True)
class _SolverFailure:
    problem_id: str | None
    error: str


@dataclass(frozen=True)
class _WorkerStopped:
    pass


@dataclass
class _ChapterRuntime:
    chapter: int
    remaining_problem_ids: list[str]
    process: mp.Process
    connection: object
    current_problem_id: str | None = None


@dataclass
class _ValidationRuntime:
    problem_id: str
    candidate: str
    search_feedback_count: int
    process: mp.Process
    connection: object


class PuzzleStateRepository:
    """Read and atomically write Manager-owned portions of ``.solve`` state."""

    def __init__(self, directory: Path | str = DEFAULT_OUTPUT_DIRECTORY) -> None:
        self.directory = Path(directory)

    def load(self, problem_id: str) -> PuzzleState | None:
        path = self.directory / f"{problem_id}.solve"
        if not path.exists():
            return None
        try:
            with path.open(encoding="utf-8") as stream:
                raw = json.load(stream)
        except (OSError, json.JSONDecodeError) as exc:
            raise PuzzleStateError(
                f"cannot read persisted state for {problem_id!r}: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise PuzzleStateError(f"state for {problem_id!r} must be a JSON object")
        if raw.get("problem_id", problem_id) != problem_id:
            raise PuzzleStateError(
                f"state filename and problem_id disagree for {problem_id!r}"
            )

        candidate = raw.get("candidate")
        status = raw.get("status")
        reason = raw.get("reason")
        local_validation = raw.get("local_validation")
        if candidate is None:
            if status is not None or reason is not None or local_validation is not None:
                raise PuzzleStateError(
                    f"state for {problem_id!r} has candidate metadata "
                    "without a candidate"
                )
            return PuzzleState(problem_id, None, None, None, None)
        if not isinstance(candidate, str):
            raise PuzzleStateError(f"candidate for {problem_id!r} must be a string")
        if status not in _OWNER_STATUSES:
            raise PuzzleStateError(
                f"candidate for {problem_id!r} has invalid status {status!r}"
            )
        if reason is not None and (
            not isinstance(reason, str) or status not in {"rejected", "re-solve"}
        ):
            raise PuzzleStateError(
                f"candidate reason for {problem_id!r} is invalid for status {status!r}"
            )
        if not isinstance(local_validation, dict):
            raise PuzzleStateError(
                f"candidate for {problem_id!r} lacks local validation data"
            )
        if local_validation.get("passed") is not True:
            raise PuzzleStateError(
                f"candidate for {problem_id!r} is not recorded as locally valid"
            )
        for key in ("case_count", "line_count"):
            value = local_validation.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise PuzzleStateError(
                    f"candidate for {problem_id!r} has invalid {key}"
                )
        return PuzzleState(
            problem_id,
            candidate,
            status,
            reason,
            local_validation,
        )

    def persist_valid_candidate(self, puzzle: Puzzle, result: ValidationResult) -> None:
        if result.outcome is not ValidationOutcome.PASS:
            raise ValueError("only passing validation results may be persisted")
        payload = {
            "problem_id": puzzle.problem_id,
            "candidate": result.candidate,
            "local_validation": {
                "passed": True,
                "case_count": result.case_count,
                "line_count": result.line_count,
            },
            "status": "pending",
        }
        self.directory.mkdir(parents=True, exist_ok=True)
        destination = self.directory / f"{puzzle.problem_id}.solve"
        temporary_name: str | None = None
        try:
            with NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.directory,
                prefix=f".{puzzle.problem_id}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
                temporary_name = stream.name
            os.replace(temporary_name, destination)
        finally:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)


class DiagnosticReporter:
    """Persist uniquely named raw diagnostic events."""

    def __init__(self, directory: Path | str = DEFAULT_REPORT_DIRECTORY) -> None:
        self.directory = Path(directory)

    def write(self, problem_id: str, event: str, details: dict[str, object]) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        marker = f"{time.time_ns()}_{uuid4().hex[:8]}"
        path = self.directory / f"{problem_id}_{marker}.report.json"
        payload = {
            "problem_id": problem_id,
            "event": event,
            "recorded_at": datetime.now(UTC).isoformat(),
            "details": details,
        }
        with path.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        return path


def validate_candidate(
    puzzle: Puzzle,
    candidate: str,
    *,
    rules_path: Path | str = DEFAULT_RULES_PATH,
    debug: bool = False,
) -> ValidationResult:
    """Perform Manager-owned authoritative validation through Executor."""

    started = time.monotonic()
    line_count = len(candidate.splitlines())
    proposal = CandidateProposal(candidate, submit=True)
    failure_reasons: list[str] = []
    if line_count > puzzle.min_lines:
        failure_reasons.append(
            f"candidate has {line_count} lines but min_lines is {puzzle.min_lines}"
        )

    try:
        executor = Executor(puzzle.chapter, rules_path=rules_path)
        failed_trials: list[TrialResult] = []
        debug_trials: list[TrialResult] = []
        for index, (input_text, expected_output) in enumerate(
            zip(puzzle.inputs, puzzle.expected_outputs)
        ):
            execution = executor.execute(input_text, candidate, debug=debug)
            trial = TrialResult(
                case_index=index,
                input_text=input_text,
                expected_output=expected_output,
                execution=execution,
                matches_expected_output=execution.output == expected_output,
            )
            if debug:
                debug_trials.append(trial)
            if execution.termination is TerminationKind.EXECUTOR_ERROR:
                return ValidationResult(
                    problem_id=puzzle.problem_id,
                    outcome=ValidationOutcome.ERROR,
                    candidate=candidate,
                    line_count=line_count,
                    case_count=len(puzzle.inputs),
                    elapsed_seconds=time.monotonic() - started,
                    error=(
                        f"Executor failed on case {index}: "
                        f"{'; '.join(execution.errors)}"
                    ),
                    debug_trials=tuple(debug_trials),
                )
            if not trial.matches_expected_output or not execution.terminated_normally:
                failed_trials.append(trial)
    except Exception as exc:
        return ValidationResult(
            problem_id=puzzle.problem_id,
            outcome=ValidationOutcome.ERROR,
            candidate=candidate,
            line_count=line_count,
            case_count=len(puzzle.inputs),
            elapsed_seconds=time.monotonic() - started,
            error=f"{type(exc).__name__}: {exc}",
        )

    if failure_reasons or failed_trials:
        feedback = CandidateFeedback(
            proposal=proposal,
            trials=tuple(failed_trials),
            failure_reasons=tuple(failure_reasons),
        )
        return ValidationResult(
            problem_id=puzzle.problem_id,
            outcome=ValidationOutcome.FAIL,
            candidate=candidate,
            line_count=line_count,
            case_count=len(puzzle.inputs),
            elapsed_seconds=time.monotonic() - started,
            feedback=feedback,
            debug_trials=tuple(debug_trials),
        )
    return ValidationResult(
        problem_id=puzzle.problem_id,
        outcome=ValidationOutcome.PASS,
        candidate=candidate,
        line_count=line_count,
        case_count=len(puzzle.inputs),
        elapsed_seconds=time.monotonic() - started,
        debug_trials=tuple(debug_trials),
    )


def _duplicate_replacement_result(
    puzzle: Puzzle, candidate: str
) -> ValidationResult:
    proposal = CandidateProposal(candidate, submit=True)
    return ValidationResult(
        problem_id=puzzle.problem_id,
        outcome=ValidationOutcome.FAIL,
        candidate=candidate,
        line_count=len(candidate.splitlines()),
        case_count=len(puzzle.inputs),
        elapsed_seconds=0.0,
        feedback=CandidateFeedback(
            proposal=proposal,
            trials=(),
            failure_reasons=(
                "candidate is identical to the current candidate marked re-solve",
            ),
        ),
    )


def _solver_worker(
    connection: object,
    puzzle_directory: str,
    rules_path: str,
    algorithm_factory: AlgorithmFactory,
    debug: bool,
) -> None:
    framework = SolverFramework(
        puzzle_repository=PuzzleRepository(puzzle_directory),
        rules_path=rules_path,
    )
    session = None
    current_problem_id: str | None = None
    try:
        while True:
            command = connection.recv()
            if isinstance(command, _StopWorker):
                connection.send(_WorkerStopped())
                return
            if isinstance(command, _StartPuzzle):
                current_problem_id = command.problem_id
                session = framework.start(
                    command.problem_id,
                    algorithm_factory,
                    debug=debug,
                )
                result = session.run_until_submission()
            elif isinstance(command, _ValidationFailed):
                if session is None:
                    raise RuntimeError(
                        "validation failure received without active session"
                    )
                result = session.run_until_submission(command.feedback)
            elif isinstance(command, _ValidationPassed):
                session = None
                current_problem_id = None
                continue
            else:
                raise RuntimeError(f"unknown Manager command: {type(command).__name__}")
            connection.send(
                _CandidateSubmitted(
                    problem_id=current_problem_id,
                    candidate=result.submitted_code,
                    search_feedback_count=len(result.feedback_history),
                    search_feedback_history=(result.feedback_history if debug else ()),
                )
            )
    except BaseException as exc:
        connection.send(
            _SolverFailure(
                current_problem_id,
                f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
            )
        )
        return
    finally:
        connection.close()


def _validation_worker(
    connection: object,
    puzzle: Puzzle,
    candidate: str,
    rules_path: str,
    debug: bool,
) -> None:
    try:
        connection.send(
            validate_candidate(puzzle, candidate, rules_path=rules_path, debug=debug)
        )
    except BaseException as exc:
        connection.send(
            ValidationResult(
                problem_id=puzzle.problem_id,
                outcome=ValidationOutcome.ERROR,
                candidate=candidate,
                line_count=len(candidate.splitlines()),
                case_count=len(puzzle.inputs),
                elapsed_seconds=0.0,
                error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
            )
        )
    finally:
        connection.close()


class Manager:
    """Coordinate chapter Solver processes and independent validation workers."""

    def __init__(
        self,
        *,
        puzzle_directory: Path | str = PuzzleRepository().directory,
        output_directory: Path | str = DEFAULT_OUTPUT_DIRECTORY,
        report_directory: Path | str = DEFAULT_REPORT_DIRECTORY,
        rules_path: Path | str = DEFAULT_RULES_PATH,
        max_concurrency: int = 1,
        algorithm_factory: AlgorithmFactory = create_solver_algorithm,
        output: TextIO | None = None,
        mp_context: mp.context.BaseContext | None = None,
    ) -> None:
        if not isinstance(max_concurrency, int) or isinstance(max_concurrency, bool):
            raise ValueError("max_concurrency must be an integer")
        if max_concurrency <= 0:
            raise ValueError("max_concurrency must be positive")
        self.puzzle_repository = PuzzleRepository(puzzle_directory)
        self.state_repository = PuzzleStateRepository(output_directory)
        self.reporter = DiagnosticReporter(report_directory)
        self.rules_path = Path(rules_path)
        self.max_concurrency = max_concurrency
        self.algorithm_factory = algorithm_factory
        self.output = output or sys.stdout
        self._mp = mp_context or mp.get_context()
        self._stop_requested = Event()

    def request_stop(self) -> None:
        """Request graceful termination at the Manager's next safe point."""

        self._stop_requested.set()

    def discover_puzzles(self) -> tuple[Puzzle, ...]:
        if not self.puzzle_repository.directory.is_dir():
            raise ManagerError(
                f"puzzle directory does not exist: {self.puzzle_repository.directory}"
            )
        discovered: list[tuple[int, int, Puzzle]] = []
        seen_positions: set[tuple[int, int]] = set()
        for path in self.puzzle_repository.directory.glob("*.a2b"):
            match = _PROBLEM_ID_PATTERN.fullmatch(path.stem)
            if match is None:
                raise ManagerError(f"invalid puzzle filename: {path.name}")
            chapter = int(match.group("chapter"))
            number = int(match.group("number"))
            if chapter not in range(1, 7):
                raise ManagerError(
                    f"puzzle {path.stem!r} has unsupported chapter {chapter}"
                )
            position = (chapter, number)
            if position in seen_positions:
                raise ManagerError(
                    f"multiple puzzles occupy chapter {chapter}, position {number}"
                )
            puzzle = self.puzzle_repository.resolve(path.stem)
            if puzzle.chapter != chapter:
                raise ManagerError(
                    f"puzzle {puzzle.problem_id!r} chapter disagrees with filename"
                )
            seen_positions.add(position)
            discovered.append((chapter, number, puzzle))
        if not discovered:
            raise ManagerError(
                f"no puzzle files found in {self.puzzle_repository.directory}"
            )
        return tuple(item[2] for item in sorted(discovered, key=lambda item: item[:2]))

    def solve_all(self, *, debug: bool = False) -> RunSummary:
        puzzles = self.discover_puzzles()
        states = {
            puzzle.problem_id: self.state_repository.load(puzzle.problem_id)
            for puzzle in puzzles
        }
        eligible = tuple(
            puzzle
            for puzzle in puzzles
            if states[puzzle.problem_id] is None
            or states[puzzle.problem_id].requires_solver
        )
        return self._run(
            all_puzzles=puzzles,
            selected_puzzles=eligible,
            initial_states=states,
            persist=True,
            debug=debug,
        )

    def solve_target(self, problem_id: str) -> RunSummary:
        puzzle = self.puzzle_repository.resolve(problem_id)
        state = self.state_repository.load(problem_id)
        return self._run(
            all_puzzles=(puzzle,),
            selected_puzzles=(puzzle,),
            initial_states={problem_id: state},
            persist=False,
            debug=True,
        )

    def _run(
        self,
        *,
        all_puzzles: tuple[Puzzle, ...],
        selected_puzzles: tuple[Puzzle, ...],
        initial_states: dict[str, PuzzleState | None],
        persist: bool,
        debug: bool,
    ) -> RunSummary:
        grouped: dict[int, list[str]] = {}
        puzzle_by_id = {puzzle.problem_id: puzzle for puzzle in all_puzzles}
        for puzzle in selected_puzzles:
            grouped.setdefault(puzzle.chapter, []).append(puzzle.problem_id)

        pending_chapters = sorted(grouped)
        active: dict[int, _ChapterRuntime] = {}
        validations: dict[int, _ValidationRuntime] = {}
        solved = 0
        validation_failures = 0
        max_active = 0
        fatal_error: str | None = None
        interrupted = False

        self._write(
            f"Discovered {len(all_puzzles)} puzzles; "
            f"{len(selected_puzzles)} require Solver work."
        )
        try:
            while pending_chapters or active:
                if self._stop_requested.is_set():
                    interrupted = True
                    break
                while pending_chapters and len(active) < self.max_concurrency:
                    chapter = pending_chapters.pop(0)
                    runtime = self._start_chapter_worker(
                        chapter,
                        list(grouped[chapter]),
                        debug=debug,
                    )
                    active[chapter] = runtime
                    max_active = max(max_active, len(active))
                    self._start_next_puzzle(runtime)

                made_progress = False
                for chapter, runtime in tuple(active.items()):
                    if runtime.connection.poll():
                        made_progress = True
                        message = runtime.connection.recv()
                        if isinstance(message, _CandidateSubmitted):
                            if chapter in validations:
                                raise ManagerError(
                                    f"chapter {chapter} submitted while validation "
                                    "was active"
                                )
                            self._write(
                                f"Candidate submitted for {message.problem_id}."
                            )
                            if debug:
                                self._write(
                                    f"Debug: {message.problem_id} submitted after "
                                    f"{message.search_feedback_count} search feedback "
                                    "events with "
                                    f"{len(message.candidate.splitlines())} lines."
                                )
                                self._record_search(message)
                            initial_state = initial_states[message.problem_id]
                            if (
                                persist
                                and initial_state is not None
                                and initial_state.status == "re-solve"
                                and message.candidate == initial_state.candidate
                            ):
                                result = _duplicate_replacement_result(
                                    puzzle_by_id[message.problem_id],
                                    message.candidate,
                                )
                                validation_failures += 1
                                self._write(
                                    f"Validation FAIL for {message.problem_id}; "
                                    "candidate matches the existing re-solve "
                                    "candidate."
                                )
                                self._record_validation(
                                    result,
                                    "validation_fail",
                                    message.search_feedback_count,
                                )
                                assert result.feedback is not None
                                runtime.connection.send(
                                    _ValidationFailed(result.feedback)
                                )
                                continue
                            validations[chapter] = self._start_validation(
                                puzzle_by_id[message.problem_id],
                                message.candidate,
                                message.search_feedback_count,
                                debug=debug,
                            )
                        elif isinstance(message, _SolverFailure):
                            if message.problem_id is not None:
                                self.reporter.write(
                                    message.problem_id,
                                    "solver_error",
                                    {"error": message.error},
                                )
                            raise ManagerError(
                                f"Solver failed for {message.problem_id!r}: "
                                f"{message.error}"
                            )
                        elif isinstance(message, _WorkerStopped):
                            raise ManagerError(
                                f"chapter {chapter} Solver stopped unexpectedly"
                            )
                        else:
                            raise ManagerError(
                                f"unknown Solver message: {type(message).__name__}"
                            )
                    elif not runtime.process.is_alive():
                        if runtime.current_problem_id is not None:
                            self.reporter.write(
                                runtime.current_problem_id,
                                "solver_process_error",
                                {"exit_code": runtime.process.exitcode},
                            )
                        raise ManagerError(
                            f"chapter {chapter} Solver exited with code "
                            f"{runtime.process.exitcode}"
                        )

                for chapter, validation in tuple(validations.items()):
                    if validation.connection.poll():
                        made_progress = True
                        result = validation.connection.recv()
                        validation.process.join(timeout=1)
                        validation.connection.close()
                        del validations[chapter]
                        if not isinstance(result, ValidationResult):
                            raise ManagerError(
                                "validation worker returned an invalid result"
                            )
                        runtime = active[chapter]
                        if result.outcome is ValidationOutcome.ERROR:
                            self._record_validation(
                                result,
                                "validation_error",
                                validation.search_feedback_count,
                            )
                            raise ManagerError(
                                f"validation failed for {result.problem_id!r}: "
                                f"{result.error}"
                            )
                        if result.outcome is ValidationOutcome.FAIL:
                            validation_failures += 1
                            self._write(
                                f"Validation FAIL for {result.problem_id}; "
                                "returning feedback to its Solver."
                            )
                            self._record_validation(
                                result,
                                "validation_fail",
                                validation.search_feedback_count,
                            )
                            assert result.feedback is not None
                            runtime.connection.send(_ValidationFailed(result.feedback))
                            continue

                        solved += 1
                        puzzle = puzzle_by_id[result.problem_id]
                        if persist:
                            self.state_repository.persist_valid_candidate(
                                puzzle, result
                            )
                        self._write(f"Validation PASS for {result.problem_id}.")
                        if debug:
                            self._record_validation(
                                result,
                                "validation_pass",
                                validation.search_feedback_count,
                            )
                        runtime.connection.send(_ValidationPassed())
                        runtime.current_problem_id = None
                        if runtime.remaining_problem_ids:
                            self._start_next_puzzle(runtime)
                        else:
                            self._stop_chapter_worker(runtime)
                            del active[chapter]
                    elif not validation.process.is_alive():
                        raise ManagerError(
                            f"validation worker for {validation.problem_id!r} exited "
                            f"with code {validation.process.exitcode}"
                        )

                if not made_progress:
                    time.sleep(0.01)
        except Exception as exc:
            fatal_error = str(exc)
            self._write(f"ERROR: {fatal_error}")
        except KeyboardInterrupt:
            interrupted = True
            self.request_stop()
        finally:
            try:
                if interrupted:
                    for runtime in active.values():
                        if runtime.current_problem_id is not None:
                            self.reporter.write(
                                runtime.current_problem_id,
                                "interrupted",
                                {"chapter": runtime.chapter},
                            )
                    self._write("Graceful stop requested; stopping active work.")
            except OSError as exc:
                fatal_error = f"cannot persist interruption diagnostics: {exc}"
                self._write(f"ERROR: {fatal_error}")
            finally:
                self._cleanup_processes(active, validations)

        final_states = dict(initial_states)
        if persist:
            for puzzle in all_puzzles:
                final_states[puzzle.problem_id] = self.state_repository.load(
                    puzzle.problem_id
                )
        pending = sum(
            state is not None and state.status == "pending"
            for state in final_states.values()
        )
        accepted = sum(
            state is not None and state.status == "accepted"
            for state in final_states.values()
        )
        rejected = sum(
            state is not None and state.status == "rejected"
            for state in final_states.values()
        )
        summary = RunSummary(
            discovered=len(all_puzzles),
            eligible=len(selected_puzzles),
            skipped=len(all_puzzles) - len(selected_puzzles),
            solved=solved,
            validation_failures=validation_failures,
            pending_owner_validation=pending,
            accepted=accepted,
            rejected=rejected,
            interrupted=interrupted,
            fatal_error=fatal_error,
            max_active_chapters=max_active,
        )
        self._print_summary(summary, persist=persist)
        return summary

    def _start_chapter_worker(
        self, chapter: int, problem_ids: list[str], *, debug: bool
    ) -> _ChapterRuntime:
        manager_connection, worker_connection = self._mp.Pipe(duplex=True)
        process = self._mp.Process(
            target=_solver_worker,
            args=(
                worker_connection,
                str(self.puzzle_repository.directory),
                str(self.rules_path),
                self.algorithm_factory,
                debug,
            ),
            name=f"a2b-solver-chapter-{chapter}",
        )
        process.start()
        worker_connection.close()
        return _ChapterRuntime(
            chapter=chapter,
            remaining_problem_ids=problem_ids,
            process=process,
            connection=manager_connection,
        )

    @staticmethod
    def _start_next_puzzle(runtime: _ChapterRuntime) -> None:
        problem_id = runtime.remaining_problem_ids.pop(0)
        runtime.current_problem_id = problem_id
        runtime.connection.send(_StartPuzzle(problem_id))

    def _start_validation(
        self,
        puzzle: Puzzle,
        candidate: str,
        search_feedback_count: int,
        *,
        debug: bool,
    ) -> _ValidationRuntime:
        manager_connection, worker_connection = self._mp.Pipe(duplex=False)
        process = self._mp.Process(
            target=_validation_worker,
            args=(worker_connection, puzzle, candidate, str(self.rules_path), debug),
            name=f"a2b-validation-{puzzle.problem_id}",
        )
        process.start()
        worker_connection.close()
        return _ValidationRuntime(
            problem_id=puzzle.problem_id,
            candidate=candidate,
            search_feedback_count=search_feedback_count,
            process=process,
            connection=manager_connection,
        )

    @staticmethod
    def _stop_chapter_worker(runtime: _ChapterRuntime) -> None:
        runtime.connection.send(_StopWorker())
        if runtime.connection.poll(1):
            runtime.connection.recv()
        runtime.process.join(timeout=1)
        runtime.connection.close()
        if runtime.process.is_alive():
            runtime.process.terminate()
            runtime.process.join(timeout=1)

    def _cleanup_processes(
        self,
        active: dict[int, _ChapterRuntime],
        validations: dict[int, _ValidationRuntime],
    ) -> None:
        for validation in validations.values():
            validation.connection.close()
            if validation.process.is_alive():
                validation.process.terminate()
            validation.process.join(timeout=1)
        for runtime in active.values():
            try:
                if runtime.process.is_alive():
                    runtime.connection.send(_StopWorker())
            except (BrokenPipeError, EOFError, OSError):
                pass
            runtime.process.join(timeout=0.2)
            if runtime.process.is_alive():
                runtime.process.terminate()
                runtime.process.join(timeout=1)
            runtime.connection.close()

    def _record_validation(
        self,
        result: ValidationResult,
        event: str,
        search_feedback_count: int,
    ) -> None:
        failed_cases = []
        failure_reasons: tuple[str, ...] = ()
        if result.feedback is not None:
            failure_reasons = result.feedback.failure_reasons
            failed_cases = [
                self._trial_summary(trial)
                for trial in result.feedback.trials
            ]
        self.reporter.write(
            result.problem_id,
            event,
            {
                "outcome": result.outcome.value,
                "candidate": result.candidate,
                "line_count": result.line_count,
                "case_count": result.case_count,
                "search_feedback_count": search_feedback_count,
                "elapsed_seconds": result.elapsed_seconds,
                "failure_reasons": failure_reasons,
                "failed_cases": failed_cases,
                "debug_trials": [
                    self._trial_diagnostics(trial) for trial in result.debug_trials
                ],
                "error": result.error,
            },
        )

    def _record_search(self, message: _CandidateSubmitted) -> None:
        """Persist Solver-side Executor observations received over worker IPC."""

        self.reporter.write(
            message.problem_id,
            "search_diagnostics",
            {
                "feedback_events": [
                    {
                        "candidate": feedback.proposal.code,
                        "case_indices": feedback.proposal.case_indices,
                        "submitted": feedback.proposal.submit,
                        "failure_reasons": feedback.failure_reasons,
                        "trials": [
                            self._trial_diagnostics(trial) for trial in feedback.trials
                        ],
                    }
                    for feedback in message.search_feedback_history
                ],
            },
        )

    @staticmethod
    def _trial_diagnostics(trial: TrialResult) -> dict[str, object]:
        """Serialize a trial, using Executor's canonical observation dumper."""

        observation_stream = StringIO()
        Executor.dump_observations(trial.execution, observation_stream)
        return Manager._trial_summary(trial) | {
            "observations": json.loads(observation_stream.getvalue()),
        }

    @staticmethod
    def _trial_summary(trial: TrialResult) -> dict[str, object]:
        """Serialize the standard non-Debug portion of a trial result."""

        return {
            "case_index": trial.case_index,
            "input": trial.input_text,
            "expected": trial.expected_output,
            "actual": trial.execution.output,
            "termination": trial.execution.termination.value,
            "errors": trial.execution.errors,
        }

    def _write(self, message: str) -> None:
        print(message, file=self.output, flush=True)

    def _print_summary(self, summary: RunSummary, *, persist: bool) -> None:
        self._write(
            "Run summary: "
            f"discovered={summary.discovered}, eligible={summary.eligible}, "
            f"skipped={summary.skipped}, locally_validated={summary.solved}, "
            f"validation_failures={summary.validation_failures}."
        )
        if persist:
            self._write(
                "Owner state: "
                f"pending={summary.pending_owner_validation}, "
                f"accepted={summary.accepted}, rejected={summary.rejected}."
            )
        if summary.interrupted:
            self._write("Run stopped gracefully before all active work completed.")
        elif summary.fatal_error is not None:
            self._write("Run failed; results after the fatal error are not trusted.")
        else:
            self._write(
                "Local workflow finished. This does not claim real-game puzzle "
                "acceptance or project completion."
            )


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="a2bautosolver")
    subcommands = parser.add_subparsers(dest="command", required=True)
    solve = subcommands.add_parser("solve", help="solve project puzzles")
    solve.add_argument("target", help="'all' or one puzzle identifier")
    solve.add_argument(
        "--max-concurrency",
        type=_positive_int,
        default=1,
        help="maximum simultaneously active chapter Solvers (default: 1)",
    )
    solve.add_argument(
        "--debug",
        action="store_true",
        help="persist richer validation diagnostics",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    manager = Manager(max_concurrency=args.max_concurrency)

    previous_handlers: dict[int, object] = {}

    def request_stop(signum: int, frame: object) -> None:
        del signum, frame
        manager.request_stop()

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signum] = signal.signal(signum, request_stop)
    try:
        try:
            if args.target == "all":
                return manager.solve_all(debug=args.debug).exit_code
            if not _PROBLEM_ID_PATTERN.fullmatch(args.target):
                build_argument_parser().error(
                    "solve target must be 'all' or a puzzle identifier"
                )
            return manager.solve_target(args.target).exit_code
        except (ManagerError, OSError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
    finally:
        for signum, previous in previous_handlers.items():
            signal.signal(signum, previous)


if __name__ == "__main__":
    raise SystemExit(main())
