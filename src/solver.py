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
    SolverSession,
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
    "SolverSession",
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

    if context.puzzle.chapter not in {1, 2, 3, 4, 5, 6}:
        raise ValueError(
            f"Solver does not provide a strategy for chapter {context.puzzle.chapter}"
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
    elif puzzle.chapter == 4:
        generated = _once_keyword_candidates(puzzle)
    elif puzzle.chapter == 5:
        generated = _numeric_candidates(puzzle)
    elif puzzle.chapter == 6:
        generated = _no_keyword_candidates(puzzle)
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


def _once_keyword_candidates(puzzle: Puzzle) -> Iterable[str]:
    symbols = _input_symbols(puzzle)
    max_length = max(map(len, puzzle.inputs), default=0)

    prefixes = {
        expected[: len(expected) - len(value)]
        for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
        if expected.endswith(value)
    }
    if len(prefixes) == 1 and all(
        expected.endswith(value) and len(expected) >= len(value)
        for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
    ):
        prefix = prefixes.pop()
        if prefix:
            yield f"(once)=(start){prefix}"

    for symbol in symbols:
        max_occurrences = max(value.count(symbol) for value in puzzle.inputs)
        for count in range(1, max_occurrences + 1):
            if all(
                expected == _remove_occurrences(value, symbol, count, from_end=False)
                for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
            ):
                yield "\n".join(f"(once){symbol}=" for _ in range(count))

            if all(
                expected == _remove_occurrences(value, symbol, count, from_end=True)
                for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
            ):
                marker = _fresh_symbol(puzzle, preferred="|")
                lines = [f"(once)=(end){marker * count}", f"{symbol}{marker}="]
                lines.extend(
                    f"{other}{marker}={marker}{other}"
                    for other in symbols
                    if other != symbol
                )
                lines.append(f"{marker}=")
                yield "\n".join(lines)

    for count in range(1, max_length + 1):
        if all(
            expected == value[count:]
            for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
        ):
            marker = _fresh_symbol(puzzle, preferred="|")
            lines = [f"(once)=(start){marker * count}"]
            lines.extend(f"{marker}{symbol}=" for symbol in symbols)
            yield "\n".join(lines)

    if all(
        expected == value[-1] + value[1:-1] + value[0]
        for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
    ):
        scan_marker, boundary_marker = _fresh_symbols(puzzle, 2)
        lines = [f"(once)=(start){scan_marker}"]
        lines.extend(
            f"{scan_marker}{symbol}=(end){boundary_marker}{symbol}"
            for symbol in symbols
        )
        lines.extend(
            f"{symbol}{boundary_marker}=(start){symbol}"
            for symbol in symbols
        )
        yield "\n".join(lines)

    if all(
        expected == value[::-1]
        for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
    ):
        marker = _fresh_symbol(puzzle, preferred="|")
        lines = [f"(once)=(start){marker * max_length}"]
        lines.extend(f"{marker}{symbol}=(start){symbol}" for symbol in symbols)
        lines.append(f"{marker}=")
        yield "\n".join(lines)

    mapping = _infer_character_mapping(puzzle)
    if mapping is not None and any(source != target for source, target in mapping.items()):
        marker = _fresh_symbol(puzzle, preferred="|")
        lines = [f"(once)=(start){marker}"]
        lines.extend(
            f"{marker}{source}={target}{marker}"
            for source, target in mapping.items()
        )
        lines.append(f"{marker}=")
        yield "\n".join(lines)

    if all(
        expected == value[1::2]
        for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
    ):
        marker = _fresh_symbol(puzzle, preferred="|")
        lines = [f"(once)=(start){marker * 2}"]
        lines.extend(f"{marker * 2}{symbol}={marker}" for symbol in symbols)
        lines.extend(
            f"{marker}{symbol}={symbol}{marker * 2}" for symbol in symbols
        )
        lines.append(f"{marker}=")
        yield "\n".join(lines)

    if all(
        expected == value * 2
        for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
    ):
        boundary_marker, scan_marker = _fresh_symbols(puzzle, 2)
        lines = [f"(once)=(end){boundary_marker}"]
        lines.extend(
            f"{scan_marker}{symbol}=(end){symbol}" for symbol in symbols
        )
        lines.extend(
            f"{symbol}{boundary_marker}="
            f"{boundary_marker}{scan_marker}{boundary_marker}{symbol * 2}"
            for symbol in symbols
        )
        lines.append(f"{boundary_marker}=")
        yield "\n".join(lines)

    conditional_mapping = _infer_conditional_mapping(puzzle, symbols)
    if conditional_mapping is not None:
        condition_symbol, source, present_target, absent_target = conditional_mapping
        condition_marker, scan_marker = _fresh_symbols(puzzle, 2)
        prefix_symbols = tuple(symbol for symbol in symbols if symbol != condition_symbol)
        lines = [f"(once){condition_symbol}={condition_marker}"]
        lines.extend(
            f"{symbol}{condition_marker}={condition_marker}{symbol}"
            for symbol in prefix_symbols
        )
        lines.append(
            f"(start){condition_marker}=(start){scan_marker}{condition_symbol}"
        )
        lines.extend(
            f"{scan_marker}{symbol}="
            f"{(present_target if symbol == source else symbol)}{scan_marker}"
            for symbol in symbols
        )
        lines.extend((f"{scan_marker}=", f"{source}={absent_target}"))
        yield "\n".join(lines)

        marker = _fresh_symbol(puzzle, preferred="|")
        lines = [
            f"(once){condition_symbol}={source}{marker}{condition_symbol}",
            f"{condition_symbol}{marker}={marker}{condition_symbol}",
        ]
        lines.extend(
            f"{symbol}{marker}{condition_symbol}="
            f"{marker}{condition_symbol}{symbol}"
            for symbol in symbols
            if symbol not in {condition_symbol, source}
        )
        lines.extend(
            (
                f"{source}{marker}=(end){marker}{present_target}",
                f"{marker}{condition_symbol}=",
                f"{source}={absent_target}",
            )
        )
        yield "\n".join(lines)

    if all(
        len(value) % 2 == 1 and expected == value[len(value) // 2]
        for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
    ):
        marker = _fresh_symbol(puzzle, preferred="|")
        odd_lengths = sorted({len(value) for value in puzzle.inputs})
        rotation_count = _find_rotation_count(
            {length: length // 2 for length in odd_lengths}
        )
        lines = [f"(once)=(start){marker * rotation_count}"]
        lines.extend(f"{marker}{symbol}=(end){symbol}" for symbol in symbols)
        lines.extend(f"(start){symbol}=(return){symbol}" for symbol in symbols)
        yield "\n".join(lines)

    removed_positions = {
        index
        for index in range(max_length)
        if all(
            len(value) > index
            and expected == value[:index] + value[index + 1 :]
            for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
        )
    }
    if removed_positions:
        marker = _fresh_symbol(puzzle, preferred="|")
        for ordering in permutations(symbols):
            low, middle, high = ordering
            for marker_count in range(1, 100):
                yield "\n".join(
                    (
                        f"(once)={marker * marker_count}",
                        f"{marker}{middle}={low}",
                        f"{marker}{high}={middle}",
                        f"{marker * 4}{low}={high}{marker * 3}",
                        f"{marker * 2}={marker}",
                        f"{marker}{low}=",
                    )
                )

    for prefix_length in range(1, max_length + 1):
        if all(
            len(value) >= prefix_length
            and expected == value + value[:prefix_length]
            for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
        ):
            forward_marker, restore_marker = _fresh_symbols(puzzle, 2)
            lines = [f"(once)={forward_marker * prefix_length}"]
            lines.extend(
                f"{restore_marker}{symbol}=(start){symbol}"
                for symbol in symbols
            )
            lines.extend(
                f"{forward_marker}{symbol}="
                f"(end){restore_marker}{symbol * 2}"
                for symbol in symbols
            )
            lines.append(f"(once)={restore_marker * prefix_length}")
            yield "\n".join(lines)

    if all(
        len(value) % 2 == 1
        and expected == value[: len(value) // 2] + value[len(value) // 2 + 1 :]
        for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
    ):
        counter, transfer, phase = _fresh_symbols(puzzle, 3)
        lines = [f"(once)={transfer}{counter}{phase}{counter * 2}"]
        lines.extend(
            f"{counter * 2}{symbol}="
            f"(end){counter}{transfer}{symbol * 2}"
            for symbol in symbols
        )
        lines.extend(
            (
                f"{phase}{counter}=(start){counter}",
                f"{phase}={phase}{counter * 2}{phase}{counter * 2}",
            )
        )
        lines.extend(
            f"{counter}{transfer}{symbol}=" for symbol in symbols
        )
        yield "\n".join(lines)

    if all(
        expected
        == "".join(character * position for position, character in enumerate(value, 1))
        for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
    ) and len(symbols) == 3:
        counter, separator = _fresh_symbols(puzzle, 2)
        first, second, third = symbols
        trigger = counter * 2 + separator
        block = counter + separator + counter
        lines = [f"(once)={trigger * 2}"]
        lines.extend(
            f"{trigger}{symbol}=(end){block}{symbol}{block}"
            for symbol in symbols
        )
        lines.append(
            f"{first}{block * 2}{second}{block * 2}{third}="
            f"(start){counter * 3}{separator}{counter}{separator}"
        )
        lines.extend(
            f"{separator}{trigger}{counter}{symbol}="
            f"{counter}{separator}{trigger * 2}"
            f"{''.join(symbols)}{symbol * 2}"
            for symbol in symbols
        )
        lines.append(f"{block}=")
        yield "\n".join(lines)

    delimiters = set.intersection(
        *(set(value) for value in puzzle.inputs)
    ) if puzzle.inputs else set()
    for delimiter in delimiters - set("abcABC0123456789"):
        if all(
            value.count(delimiter) == 1
            and len(value.split(delimiter)[0]) == len(value.split(delimiter)[1])
            and expected
            == "".join(
                left + right
                for left, right in zip(*value.split(delimiter))
            )
            for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
        ):
            marker = _fresh_symbol(puzzle, preferred=">")
            data_symbols = tuple(symbol for symbol in symbols if symbol != delimiter)
            lines = [
                f"{marker}{delimiter * 3}{symbol}=(end){symbol}"
                for symbol in data_symbols
            ]
            lines.extend(
                (
                    f"{delimiter}{marker}=(start){marker}{delimiter * 3}",
                    f"{marker}{delimiter * 5}=",
                    f"{delimiter}={delimiter}{marker}{delimiter * 2}",
                )
            )
            yield "\n".join(lines)


def _numeric_candidates(puzzle: Puzzle) -> Iterable[str]:
    output_symbols = tuple(
        sorted({character for value in puzzle.expected_outputs for character in value})
    )

    if len(output_symbols) == 1 and all(
        set(value) <= {"0", "1"}
        and expected == output_symbols[0] * int(value, 2)
        for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
    ):
        output_symbol = output_symbols[0]
        yield "\n".join(
            (
                f"{output_symbol}1=1{output_symbol * 2}",
                f"{output_symbol}0=1{output_symbol}",
                f"1={output_symbol}",
            )
        )

    if all(
        set(value) <= {"0", "1"}
        and int(expected, 2) == int(value, 2) + 1
        for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
    ):
        carry = _fresh_symbol(puzzle, preferred="|")
        yield "\n".join(
            (
                f"(once)=(end){carry}",
                f"1{carry}={carry}0",
                f"0{carry}=1",
                f"{carry}=1",
            )
        )

    binary_operation = _infer_binary_operation(puzzle)
    if binary_operation is None:
        return

    operator, operation = binary_operation
    if operation == "add":
        guard, unary = _fresh_symbols(puzzle, 2)
        yield "\n".join(
            (
                f"(once){operator}1={guard}{operator}",
                f"{operator}1=1{operator * 2}",
                f"{operator}0=1{operator}",
                f"{guard}1={guard}{operator}",
                f"{operator}={unary}",
                f"{guard}=",
                f"1{unary}={unary}0",
                f"0{unary}=1",
                f"(start){unary}=(start)1",
            )
        )

    if operation == "subtract":
        unary, carry = _fresh_symbols(puzzle, 2)
        yield "\n".join(
            (
                f"{operator}1={operator}{unary}",
                f"{unary}1=1{unary * 2}",
                f"{unary}0=1{unary}",
                f"{operator}{unary}={carry}{operator}",
                f"0{carry}={carry}1",
                f"(start)1{carry}=(start)",
                f"1{carry}=0",
                f"{operator}=",
            )
        )

    if operation == "multiply":
        (
            left_guard,
            left_unary,
            right_guard,
            right_unary,
            product,
            boundary,
            carry,
        ) = _fresh_symbols(puzzle, 7)
        yield "\n".join(
            (
                f"(once)1={left_guard}{left_unary}",
                f"{left_unary}1=1{left_unary * 2}",
                f"{left_unary}0=1{left_unary}",
                f"{left_guard}1={left_guard}{left_unary}",
                f"{left_guard}=",
                f"(once){operator}1={right_guard}{right_unary}",
                f"{right_unary}1=1{right_unary * 2}",
                f"{right_unary}0=1{right_unary}",
                f"{right_guard}1={right_guard}{right_unary}",
                f"{right_guard}=",
                f"{left_unary}{right_unary}="
                f"{right_unary}{left_unary}{product}",
                f"{product}{right_unary}={right_unary}{product}",
                f"{right_unary}=",
                f"{left_unary}=",
                f"(once)=(start)0{boundary}",
                f"{boundary}{product}={carry}{boundary}",
                f"1{carry}={carry}0",
                f"0{carry}=1",
                f"(start){carry}=(start)1",
                f"{boundary}=",
            )
        )

    if operation == "divide":
        (
            left_guard,
            dividend,
            divisor,
            end_marker,
            failure,
            left_scan,
            right_scan,
            quotient,
            quotient_boundary,
            carry,
            remainder_boundary,
            marked_divisor,
        ) = _fresh_symbols(puzzle, 12)
        yield "\n".join(
            (
                f"(once)1={left_guard}{dividend}",
                f"{dividend}1=1{dividend * 2}",
                f"{dividend}0=1{dividend}",
                f"{left_guard}1={left_guard}{dividend}",
                f"{left_guard}=",
                f"(once){operator}1={operator}{divisor}",
                f"{divisor}1=1{divisor * 2}",
                f"{divisor}0=1{divisor}",
                f"{operator}1={operator}{divisor}",
                f"(once)=(end){end_marker}",
                f"(start){operator}=(start){failure}",
                f"(start){left_scan}{marked_divisor}=(start){failure}",
                f"{marked_divisor}{operator}={operator}{divisor}",
                f"{operator}{divisor}={left_scan}{marked_divisor}",
                f"{marked_divisor}{left_scan}="
                f"{left_scan}{marked_divisor}",
                f"{dividend}{left_scan}={right_scan}",
                f"{right_scan}{marked_divisor}="
                f"{marked_divisor}{right_scan}",
                f"{right_scan}{divisor}={left_scan}{marked_divisor}",
                f"{right_scan}{end_marker}="
                f"{operator}{end_marker}{quotient}",
                f"{marked_divisor}={dividend}",
                f"{divisor}=",
                f"{failure}=",
                f"{end_marker}{quotient}={quotient}{end_marker}",
                f"{dividend}{quotient}={quotient}{dividend}",
                f"{dividend}{end_marker}={end_marker}{dividend}",
                f"(once)=(start)0{quotient_boundary}",
                f"{quotient_boundary}{quotient}="
                f"{carry}{quotient_boundary}",
                f"1{carry}={carry}0",
                f"0{carry}=1",
                f"(start){carry}=(start)1",
                f"{quotient_boundary}=",
                f"{end_marker}=,0{remainder_boundary}",
                f"{remainder_boundary}{dividend}="
                f"{carry}{remainder_boundary}",
                f",{carry}=,1",
                f"{remainder_boundary}=",
            )
        )


def _no_keyword_candidates(puzzle: Puzzle) -> Iterable[str]:
    symbols = _input_symbols(puzzle)
    outputs = tuple(set(puzzle.expected_outputs))

    if len(outputs) == 1:
        output = outputs[0]
        marker = symbols[0]
        lines = [f"{symbol}={marker}" for symbol in symbols if symbol != marker]
        lines.extend((f"{marker * 2}={marker}", f"{marker}={output}"))
        yield "\n".join(lines)

    palindrome_outputs = {
        expected
        for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
        if value == value[::-1]
    }
    non_palindrome_outputs = {
        expected
        for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
        if value != value[::-1]
    }
    if (
        len(symbols) == 3
        and len(palindrome_outputs) == 1
        and len(non_palindrome_outputs) == 1
        and palindrome_outputs != non_palindrome_outputs
    ):
        palindrome_output = next(iter(palindrome_outputs))
        non_palindrome_output = next(iter(non_palindrome_outputs))
        output_characters = set().union(*map(set, puzzle.expected_outputs))
        base = next(
            (
                symbol
                for symbol in symbols
                if all(
                    symbol * 2 not in output
                    for output in puzzle.expected_outputs
                )
                and all(
                    other not in output_characters
                    for other in symbols
                    if other != symbol
                )
            ),
            None,
        )
        if base is not None:
            first, second = (symbol for symbol in symbols if symbol != base)
            encoded, boundary, base_state, encoded_state, failure = _fresh_symbols(
                puzzle, 5
            )
            yield "\n".join(
                (
                    f"{first}={encoded}{base}{encoded}",
                    f"{second}={encoded * 2}{base}{encoded * 2}",
                    f"{base}{boundary}={boundary}{base}",
                    f"{encoded}{boundary}={boundary}{encoded}",
                    f"{base_state}{base}={base}{base_state}",
                    f"{base_state}{encoded}={encoded}{base_state}",
                    f"{encoded_state}{base}={base}{encoded_state}",
                    f"{encoded_state}{encoded}={encoded}{encoded_state}",
                    f"{base}{base_state}=",
                    f"{encoded}{encoded_state}=",
                    f"{boundary}{base_state}={palindrome_output}",
                    f"{boundary}{encoded_state}={palindrome_output}",
                    f"{base_state}={failure}",
                    f"{encoded_state}={failure}",
                    f"{base}{failure}={failure}",
                    f"{encoded}{failure}={failure}",
                    f"{boundary}{failure}={non_palindrome_output}",
                    f"{boundary}{base}={boundary}{base_state}",
                    f"{boundary}{encoded}={boundary}{encoded_state}",
                    f"{boundary}={palindrome_output}",
                    f"{encoded}={encoded}{boundary}",
                    f"{base * 2}={base}{boundary}{base}",
                )
            )

    conditional_mapping = _infer_conditional_mapping(puzzle, symbols)
    if conditional_mapping is not None:
        condition, source, present_target, absent_target = conditional_mapping
        other_symbols = tuple(
            symbol
            for symbol in symbols
            if symbol not in {condition, source}
        )
        if len(other_symbols) == 1:
            bridge = other_symbols[0]
            max_bridge = max(map(len, puzzle.inputs), default=0) - 2
            lines: list[str] = []
            for count in range(max_bridge + 1):
                gap = bridge * count
                lines.extend(
                    (
                        f"{condition}{gap}{source}="
                        f"{condition}{gap}{present_target}",
                        f"{source}{gap}{condition}="
                        f"{present_target}{gap}{condition}",
                    )
                )
            lines.append(f"{source}={absent_target}")
            yield "\n".join(lines)


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


def _infer_binary_operation(puzzle: Puzzle) -> tuple[str, str] | None:
    operations: tuple[tuple[str, Callable[[int, int], str]], ...] = (
        ("add", lambda left, right: format(left + right, "b")),
        ("subtract", lambda left, right: format(left - right, "b")),
        ("multiply", lambda left, right: format(left * right, "b")),
        (
            "divide",
            lambda left, right: f"{left // right:b},{left % right:b}",
        ),
    )
    delimiters = sorted(
        {
            character
            for value in puzzle.inputs
            for character in value
            if character not in {"0", "1"}
        }
    )
    if len(delimiters) != 1:
        return None

    delimiter = delimiters[0]
    parsed: list[tuple[int, int, str]] = []
    for value, expected in zip(puzzle.inputs, puzzle.expected_outputs):
        parts = value.split(delimiter)
        if (
            len(parts) != 2
            or not all(parts)
            or any(set(part) - {"0", "1"} for part in parts)
        ):
            return None
        parsed.append((int(parts[0], 2), int(parts[1], 2), expected))

    for name, operation in operations:
        if all(operation(left, right) == expected for left, right, expected in parsed):
            return delimiter, name
    return None


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


def _remove_occurrences(
    value: str, symbol: str, count: int, *, from_end: bool
) -> str:
    if from_end:
        return _remove_occurrences(value[::-1], symbol, count, from_end=False)[::-1]
    remaining = count
    result: list[str] = []
    for character in value:
        if character == symbol and remaining:
            remaining -= 1
        else:
            result.append(character)
    return "".join(result)


def _infer_conditional_mapping(
    puzzle: Puzzle, symbols: tuple[str, ...]
) -> tuple[str, str, str, str] | None:
    for condition_symbol, source in permutations(symbols, 2):
        for present_target, absent_target in permutations(symbols, 2):
            if all(
                expected
                == value.replace(
                    source,
                    present_target if condition_symbol in value else absent_target,
                )
                for value, expected in zip(puzzle.inputs, puzzle.expected_outputs)
            ):
                return condition_symbol, source, present_target, absent_target
    return None


def _find_rotation_count(remainders: dict[int, int]) -> int:
    candidate = 0
    while True:
        if all(
            candidate % modulus == remainder
            for modulus, remainder in remainders.items()
        ):
            return candidate
        candidate += 1
