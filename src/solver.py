"""Data-driven A=B Solver algorithms.

The strategies in this module synthesize native A=B programs from puzzle I/O
data.  They deliberately contain neither puzzle identifiers nor a catalogue of
final answers.  Candidate programs are proposed tentatively, evaluated by the
common Solver framework through Executor, and submitted only after passing the
complete requested trial set.
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations, permutations
from typing import Callable, Iterable

from src.solver_framework import (
    AlgorithmFactory,
    CandidateFeedback,
    CandidateProposal,
    DEFAULT_PUZZLE_DIRECTORY,
    DEFAULT_RULES_PATH,
    ExecutionResult,
    Executor,
    Puzzle,
    PuzzleRepository,
    PuzzleResolutionError,
    SolverExecutionError,
    SolverContext,
    SolverFramework,
    SolverRunResult,
    SolvingAlgorithm,
    TerminationKind,
    TrialResult,
)


__all__ = [
    "AlgorithmFactory",
    "CandidateFeedback",
    "CandidateProposal",
    "CandidateSynthesisError",
    "CandidateSynthesisAlgorithm",
    "DEFAULT_PUZZLE_DIRECTORY",
    "DEFAULT_RULES_PATH",
    "ExecutionResult",
    "Executor",
    "Puzzle",
    "PuzzleRepository",
    "PuzzleResolutionError",
    "SolverContext",
    "SolverExecutionError",
    "SolverFramework",
    "SolverRunResult",
    "SolvingAlgorithm",
    "TerminationKind",
    "TrialResult",
    "create_solver_algorithm",
]


class CandidateSynthesisError(RuntimeError):
    """Raised when the available synthesis strategies cannot solve a puzzle."""


class CandidateSynthesisAlgorithm:
    """Try generated programs and submit the first fully passing candidate."""

    def __init__(self, context: SolverContext) -> None:
        self._puzzle = context.puzzle
        self._candidates = iter(_generate_candidates(context.puzzle))
        self._current_code: str | None = None

    def propose(self, feedback: CandidateFeedback | None) -> CandidateProposal:
        if feedback is not None and feedback.passed:
            if self._current_code is None:  # pragma: no cover - protocol invariant
                raise CandidateSynthesisError("passing feedback has no candidate")
            return CandidateProposal(self._current_code, submit=True)

        try:
            self._current_code = next(self._candidates)
        except StopIteration as exc:
            raise CandidateSynthesisError(
                f"no generated candidate solved {self._puzzle.problem_id!r}"
            ) from exc
        return CandidateProposal(self._current_code)


def create_solver_algorithm(context: SolverContext) -> CandidateSynthesisAlgorithm:
    """Create the data-driven algorithm for a supported puzzle."""

    if context.puzzle.chapter not in {1, 2, 3}:
        raise ValueError(
            f"FEAT0004 does not provide a strategy for chapter {context.puzzle.chapter}"
        )
    return CandidateSynthesisAlgorithm(context)


def _generate_candidates(puzzle: Puzzle) -> Iterable[str]:
    generated: Iterable[str]
    if puzzle.chapter == 1:
        generated = _basic_replacement_candidates(puzzle)
    elif puzzle.chapter == 2:
        generated = _return_keyword_candidates(puzzle)
    elif puzzle.chapter == 3:
        generated = _boundary_keyword_candidates(puzzle)
    else:
        generated = ()

    seen: set[str] = set()
    for code in generated:
        if code in seen or len(code.splitlines()) > puzzle.min_lines:
            continue
        seen.add(code)
        yield code


def _basic_replacement_candidates(puzzle: Puzzle) -> Iterable[str]:
    symbols = _input_symbols(puzzle)

    mapping = _infer_character_mapping(puzzle)
    if mapping is not None:
        changed = [(source, target) for source, target in mapping.items() if source != target]
        if changed:
            yield "\n".join(f"{source}={target}" for source, target in changed)

    # Generic adjacent-run reducers: collapse every repeated symbol, or remove
    # repeated runs of any selected subset while preserving singleton symbols.
    if symbols:
        yield "\n".join(f"{symbol}{symbol}={symbol}" for symbol in symbols)
        for count in range(1, len(symbols) + 1):
            for selected in combinations(symbols, count):
                lines: list[str] = []
                for symbol in selected:
                    lines.extend((f"{symbol * 3}={symbol * 2}", f"{symbol * 2}="))
                yield "\n".join(lines)

    # Generate bubble-sort rewrite systems for every ordering observed in the
    # input alphabet. Executor feedback determines which ordering, if any,
    # matches the puzzle's required outputs.
    for ordering in permutations(symbols):
        rank = {symbol: index for index, symbol in enumerate(ordering)}
        lines = [
            f"{left}{right}={right}{left}"
            for left in ordering
            for right in ordering
            if rank[left] > rank[right]
        ]
        if lines:
            yield "\n".join(lines)

    # A two-symbol frequency winner can be synthesized by cancelling unlike
    # pairs and normalizing the remaining run to one symbol.
    for first, second in permutations(symbols, 2):
        yield "\n".join(
            (
                f"{first}{second}=",
                f"{second}{first}=",
                f"{first}{first}={first}",
                f"{second}{second}={second}",
            )
        )


def _return_keyword_candidates(puzzle: Puzzle) -> Iterable[str]:
    symbols = _input_symbols(puzzle)
    outputs = tuple(sorted(set(puzzle.expected_outputs)))
    max_length = max(map(len, puzzle.inputs), default=0)

    if len(outputs) == 1:
        yield f"=(return){outputs[0]}"

    for true_output, false_output in permutations(outputs, 2):
        for symbol in symbols:
            for threshold in range(1, max_length + 1):
                predicate = lambda value, s=symbol, n=threshold: value.count(s) >= n
                if _matches_boolean(puzzle, predicate, true_output, false_output):
                    lines = [f"{other}=" for other in symbols if other != symbol]
                    lines.extend(
                        (f"{symbol * threshold}=(return){true_output}",
                         f"=(return){false_output}")
                    )
                    yield "\n".join(lines)

        for target_length in range(max_length + 1):
            predicate = lambda value, n=target_length: len(value) == n
            if _matches_boolean(puzzle, predicate, true_output, false_output):
                marker = symbols[0]
                lines = [f"{symbol}={marker}" for symbol in symbols if symbol != marker]
                lines.extend(
                    (
                        f"{marker * (target_length + 1)}=(return){false_output}",
                        f"{marker * target_length}=(return){true_output}",
                        f"=(return){false_output}",
                    )
                )
                yield "\n".join(lines)

        odd_or_zero = lambda value: all(
            count == 0 or count % 2 == 1 for count in Counter(value).values()
        )
        if _matches_boolean(puzzle, odd_or_zero, true_output, false_output):
            for ordering in permutations(symbols):
                lines = _sorting_lines(ordering)
                lines.extend(f"{symbol * 3}={symbol}" for symbol in ordering)
                lines.extend(
                    f"{symbol * 2}=(return){false_output}" for symbol in ordering
                )
                lines.append(f"=(return){true_output}")
                yield "\n".join(lines)

        exactly_one_singleton_run = lambda value: (
            len(_singleton_runs(value)) == 1
        )
        if _matches_boolean(
            puzzle, exactly_one_singleton_run, true_output, false_output
        ):
            run_marker, normalized = _fresh_symbols(puzzle, 2)
            lines: list[str] = []
            for symbol in symbols:
                lines.extend(
                    (
                        f"{symbol * 3}={symbol * 2}",
                        f"{symbol * 2}={run_marker}",
                        f"{symbol}={normalized}",
                    )
                )
            lines.append(f"{run_marker}=")
            lines.extend(
                (
                    f"{normalized * 2}=(return){false_output}",
                    f"{normalized}=(return){true_output}",
                    f"=(return){false_output}",
                )
            )
            yield "\n".join(lines)

        for lower, middle, upper in permutations(symbols, 3):
            predicate = lambda value, a=lower, b=middle, c=upper: (
                value.count(c) > value.count(b) > value.count(a)
            )
            if _matches_boolean(puzzle, predicate, true_output, false_output):
                marker = _fresh_symbol(puzzle, preferred="|")
                lines = _sorting_lines((lower, middle, upper))
                lines.extend(
                    (
                        f"{middle}{marker}={marker}{middle}",
                        f"{middle}{upper}={marker}",
                        f"{lower}{marker}=",
                        f"{marker}{upper}=(return){true_output}",
                        f"=(return){false_output}",
                    )
                )
                yield "\n".join(lines)

    for divisor in range(2, max_length + 1):
        remainder_outputs: dict[int, str] = {}
        valid = True
        for input_text, expected_output in zip(puzzle.inputs, puzzle.expected_outputs):
            remainder = len(input_text) % divisor
            prior = remainder_outputs.setdefault(remainder, expected_output)
            if prior != expected_output:
                valid = False
                break
        if valid and len(remainder_outputs) == divisor:
            marker = symbols[0]
            lines = [f"{symbol}={marker}" for symbol in symbols if symbol != marker]
            lines.append(f"{marker * (divisor + 1)}={marker}")
            for remainder in range(divisor, 0, -1):
                normalized_remainder = remainder % divisor
                lines.append(
                    f"{marker * remainder}={remainder_outputs[normalized_remainder]}"
                )
            yield "\n".join(lines)

    if len(symbols) == 3:
        for ordering in permutations(symbols):
            most = lambda value: max(Counter(value), key=Counter(value).get)
            if all(
                expected == most(value)
                for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
            ):
                threshold = max_length // 2 + 1
                lines = _sorting_lines(ordering)
                lines.extend(
                    f"{symbol * threshold}=(return){symbol}" for symbol in ordering
                )
                lines.append(f"={''.join(ordering)}")
                yield "\n".join(lines)

            least = lambda value, alphabet=symbols: min(
                alphabet, key=value.count
            )
            if all(
                expected == least(value)
                for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
            ):
                first, second, third = ordering
                lines = _sorting_lines(ordering)
                lines.extend(
                    (
                        f"{first}{second}{third}=(return){second}",
                        f"{first}{first}{second}=(return){third}",
                        f"{second}{third}=(return){first}",
                        f"={first}{second}",
                    )
                )
                yield "\n".join(lines)


def _boundary_keyword_candidates(puzzle: Puzzle) -> Iterable[str]:
    symbols = _input_symbols(puzzle)
    outputs = tuple(sorted(set(puzzle.expected_outputs)))

    for symbol in symbols:
        if all(
            expected == value.strip(symbol)
            for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
        ):
            yield f"(start){symbol}=\n(end){symbol}="

        if all(symbol in value for value in puzzle.inputs) and all(
            expected == value[value.index(symbol) :] + value[: value.index(symbol)]
            for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
        ):
            lines = [
                f"(start){other}=(end){other}"
                for other in symbols
                if other != symbol
            ]
            yield "\n".join(lines)

    for source, target in permutations(symbols, 2):
        if all(
            expected == _replace_boundary_runs(value, source, target)
            for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
        ):
            start_marker, end_marker = _fresh_symbols(puzzle, 2)
            yield "\n".join(
                (
                    f"(start){source}=(end){start_marker}",
                    f"{start_marker}=(start){target}",
                    f"(end){source}=(start){end_marker}",
                    f"{end_marker}=(end){target}",
                )
            )

    for start_symbol, end_symbol in permutations(symbols, 2):
        if all(
            expected == _swap_boundary_runs(value, start_symbol, end_symbol)
            for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
        ):
            marker = _fresh_symbol(puzzle, preferred="|")
            yield "\n".join(
                (
                    f"(end){end_symbol}=(start){marker}{end_symbol}",
                    f"{marker}{end_symbol}{start_symbol}="
                    f"(end){marker}{start_symbol}{end_symbol}",
                    f"{marker}=",
                )
            )

    for true_output, false_output in permutations(outputs, 2):
        same_ends = lambda value: value[0] == value[-1]
        if _matches_boolean(puzzle, same_ends, true_output, false_output):
            markers = _fresh_symbols(puzzle, len(symbols))
            lines = [
                f"(end){symbol}{marker}=(return){true_output}"
                for symbol, marker in zip(symbols, markers)
            ]
            lines.extend(
                f"(start){symbol}=(end){marker}"
                for symbol, marker in zip(symbols, markers)
            )
            lines.append(f"=(return){false_output}")
            yield "\n".join(lines)

        palindrome = lambda value: value == value[::-1]
        if _matches_boolean(puzzle, palindrome, true_output, false_output):
            open_marker, close_marker = _fresh_symbols(puzzle, 2)
            lines = [
                f"{symbol}{open_marker}{symbol}{close_marker}="
                for symbol in symbols
            ]
            lines.extend(
                f"(start){symbol}=(end){open_marker}{symbol}{close_marker}"
                for symbol in symbols
            )
            lines.extend(
                (
                    f"{close_marker}{open_marker}=(return){false_output}",
                    f"=(return){true_output}",
                )
            )
            yield "\n".join(lines)

    if len(symbols) == 3:
        most_runs = lambda value: (
            max(Counter(value), key=Counter(value).get)
            * max(Counter(value).values())
        )
        if all(
            expected == most_runs(value)
            for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
        ):
            for first, second, third in permutations(symbols):
                marker = _fresh_symbol(puzzle, preferred="|")
                yield "\n".join(
                    (
                        f"{first}{second}=(end){marker}{third}",
                        f"{second}{first}=(end){marker}{third}",
                        f"{third}{first}={first}{third}",
                        f"{third}{second}={second}{third}",
                        f"{third}{marker}{third}=(end){marker}",
                        f"{first}{third}=(end){marker}",
                        f"{second}{third}=(end){marker}",
                        f"{first}{marker}={first}{first}",
                        f"{second}{marker}={second}{second}",
                        f"{marker}={third}",
                    )
                )


def _input_symbols(puzzle: Puzzle) -> tuple[str, ...]:
    return tuple(sorted({character for value in puzzle.inputs for character in value}))


def _infer_character_mapping(puzzle: Puzzle) -> dict[str, str] | None:
    mapping: dict[str, str] = {}
    for input_text, expected_output in zip(puzzle.inputs, puzzle.expected_outputs):
        if len(input_text) != len(expected_output):
            return None
        for source, target in zip(input_text, expected_output):
            previous = mapping.setdefault(source, target)
            if previous != target:
                return None
    return mapping


def _matches_boolean(
    puzzle: Puzzle,
    predicate: Callable[[str], bool],
    true_output: str,
    false_output: str,
) -> bool:
    return all(
        expected_output == (true_output if predicate(input_text) else false_output)
        for input_text, expected_output in zip(puzzle.inputs, puzzle.expected_outputs)
    )


def _sorting_lines(ordering: tuple[str, ...]) -> list[str]:
    rank = {symbol: index for index, symbol in enumerate(ordering)}
    return [
        f"{left}{right}={right}{left}"
        for left in ordering
        for right in ordering
        if rank[left] > rank[right]
    ]


def _fresh_symbol(puzzle: Puzzle, *, preferred: str) -> str:
    used = {
        character
        for value in (*puzzle.inputs, *puzzle.expected_outputs)
        for character in value
    }
    if preferred not in used:
        return preferred
    for character in "@$%^&*+-_<>[]{}:;,.?/ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
        if character not in used and character not in "=()#":
            return character
    raise CandidateSynthesisError("no safe auxiliary character is available")


def _fresh_symbols(puzzle: Puzzle, count: int) -> tuple[str, ...]:
    available = []
    used = {
        character
        for value in (*puzzle.inputs, *puzzle.expected_outputs)
        for character in value
    }
    for character in "|@$%^&*+-_<>[]{}:;,.?/ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
        if character not in used and character not in "=()#":
            available.append(character)
        if len(available) == count:
            return tuple(available)
    raise CandidateSynthesisError(f"fewer than {count} safe auxiliary characters")


def _replace_boundary_runs(value: str, source: str, target: str) -> str:
    start = 0
    while start < len(value) and value[start] == source:
        start += 1
    end = len(value)
    while end > start and value[end - 1] == source:
        end -= 1
    return target * start + value[start:end] + target * (len(value) - end)


def _swap_boundary_runs(value: str, start_symbol: str, end_symbol: str) -> str:
    start = 0
    while start < len(value) and value[start] == start_symbol:
        start += 1
    end = len(value)
    while end > start and value[end - 1] == end_symbol:
        end -= 1
    return end_symbol * (len(value) - end) + value[start:end] + start_symbol * start


def _singleton_runs(value: str) -> tuple[str, ...]:
    runs: list[str] = []
    index = 0
    while index < len(value):
        end = index + 1
        while end < len(value) and value[end] == value[index]:
            end += 1
        if end - index == 1:
            runs.append(value[index])
        index = end
    return tuple(runs)
