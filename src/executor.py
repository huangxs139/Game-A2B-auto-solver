"""Rules-driven execution for serialized A=B programs.

The Executor owns A=B execution semantics.  It intentionally has no puzzle,
Solver, Manager, or filesystem-output responsibilities.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TextIO

import yaml


DEFAULT_RULES_PATH = Path(__file__).with_name("rules") / "a2b_rules.yaml"


class TerminationKind(str, Enum):
    """The terminal state of one Executor call."""

    NORMAL = "normal_termination"
    RETURN = "immediate_return_termination"
    NONTERMINATION = "nontermination_detected"
    INVALID_PROGRAM = "invalid_program"
    EXECUTOR_ERROR = "executor_error"


class RulesError(ValueError):
    """Raised when the machine-readable Rules cannot be used safely."""


@dataclass(frozen=True)
class ExecutionObservation:
    """One successfully executed instruction, recorded only in Debug mode."""

    step: int
    line_number: int
    before: str
    after: str
    left_keyword: str | None
    right_keyword: str | None
    once_consumed: bool


@dataclass(frozen=True)
class ExecutionResult:
    """The complete outcome of executing one code snippet for one input."""

    output: str | None
    termination: TerminationKind
    steps: int
    loop_detected: bool = False
    errors: tuple[str, ...] = ()
    observations: tuple[ExecutionObservation, ...] = ()

    @property
    def terminated_normally(self) -> bool:
        return self.termination in {TerminationKind.NORMAL, TerminationKind.RETURN}


@dataclass(frozen=True)
class _Instruction:
    line_number: int
    left_keyword: str | None
    left_string: str
    right_keyword: str | None
    right_string: str


class Executor:
    """Execute A=B code for one chapter using the shared Rules definition.

    The chapter is bound when an Executor is created so the normal execution
    interface remains ``execute(input_text, code_snippet)``.
    """

    def __init__(
        self,
        chapter: int,
        *,
        rules_path: Path | str = DEFAULT_RULES_PATH,
        max_steps: int = 100_000,
    ) -> None:
        if max_steps <= 0:
            raise ValueError("max_steps must be positive")
        self._rules = self._load_rules(Path(rules_path))
        chapter_key = str(chapter)
        if chapter_key not in self._rules["chapters"]:
            raise ValueError(f"unsupported chapter: {chapter}")
        self.chapter = chapter
        self._chapter_rules = self._rules["chapters"][chapter_key]
        available_operations = self._chapter_rules["available_operations"]
        if len(available_operations) != 1:
            raise RulesError("each supported chapter must expose exactly one operation")
        operation_id = available_operations[0]
        operation_handlers = {
            "replace_leftmost_occurrence": self._apply_instruction,
        }
        try:
            self._operation = operation_handlers[operation_id]
        except KeyError as exc:
            raise RulesError(f"unsupported Rules operation: {operation_id}") from exc
        self.max_steps = max_steps

    def execute(
        self, input_text: str, code_snippet: str, *, debug: bool = False
    ) -> ExecutionResult:
        """Execute one final serialized A=B program.

        Invalid candidate syntax is represented as ``INVALID_PROGRAM``. An
        unexpected Executor failure is represented as ``EXECUTOR_ERROR`` so a
        caller can distinguish it from an ordinary invalid candidate.
        """

        try:
            instructions = self._parse_program(code_snippet)
        except ValueError as exc:
            return ExecutionResult(
                output=None,
                termination=TerminationKind.INVALID_PROGRAM,
                steps=0,
                errors=(str(exc),),
            )

        current = input_text
        consumed_once_lines: set[int] = set()
        seen_states: set[tuple[str, frozenset[int]]] = set()
        observations: list[ExecutionObservation] = []
        steps = 0

        try:
            while True:
                state = (current, frozenset(consumed_once_lines))
                if state in seen_states:
                    return ExecutionResult(
                        output=current,
                        termination=TerminationKind.NONTERMINATION,
                        steps=steps,
                        loop_detected=True,
                        observations=tuple(observations),
                    )
                seen_states.add(state)

                executed = False
                for instruction in instructions:
                    if (
                        instruction.left_keyword == "once"
                        and instruction.line_number in consumed_once_lines
                    ):
                        continue

                    replacement = self._operation(current, instruction)
                    if replacement is None:
                        continue

                    before = current
                    current, should_return = replacement
                    steps += 1
                    consumed_once = instruction.left_keyword == "once"
                    if consumed_once:
                        consumed_once_lines.add(instruction.line_number)
                    if debug:
                        observations.append(
                            ExecutionObservation(
                                step=steps,
                                line_number=instruction.line_number,
                                before=before,
                                after=current,
                                left_keyword=instruction.left_keyword,
                                right_keyword=instruction.right_keyword,
                                once_consumed=consumed_once,
                            )
                        )
                    if should_return:
                        return ExecutionResult(
                            output=current,
                            termination=TerminationKind.RETURN,
                            steps=steps,
                            observations=tuple(observations),
                        )
                    if steps >= self.max_steps:
                        return ExecutionResult(
                            output=current,
                            termination=TerminationKind.NONTERMINATION,
                            steps=steps,
                            errors=(f"execution exceeded max_steps={self.max_steps}",),
                            observations=tuple(observations),
                        )
                    executed = True
                    break

                if not executed:
                    return ExecutionResult(
                        output=current,
                        termination=TerminationKind.NORMAL,
                        steps=steps,
                        observations=tuple(observations),
                    )
        except Exception as exc:  # pragma: no cover - defensive infrastructure path
            return ExecutionResult(
                output=None,
                termination=TerminationKind.EXECUTOR_ERROR,
                steps=steps,
                errors=(f"{type(exc).__name__}: {exc}",),
                observations=tuple(observations),
            )

    @staticmethod
    def dump_observations(result: ExecutionResult, stream: TextIO) -> None:
        """Write Debug observations as JSON to a caller-owned stream.

        The Executor does not select a report path or manage report files; the
        Manager or another caller owns that persistence decision.
        """

        json.dump(
            [
                {
                    "step": observation.step,
                    "line_number": observation.line_number,
                    "before": observation.before,
                    "after": observation.after,
                    "left_keyword": observation.left_keyword,
                    "right_keyword": observation.right_keyword,
                    "once_consumed": observation.once_consumed,
                }
                for observation in result.observations
            ],
            stream,
            ensure_ascii=False,
            indent=2,
        )

    @staticmethod
    def _load_rules(path: Path) -> dict[str, Any]:
        try:
            with path.open(encoding="utf-8") as stream:
                rules = yaml.safe_load(stream)
        except (OSError, yaml.YAMLError) as exc:
            raise RulesError(f"cannot load Rules from {path}: {exc}") from exc

        if not isinstance(rules, dict):
            raise RulesError("Rules root must be a mapping")
        required = {"syntax", "keywords", "chapters", "operations"}
        missing = required - rules.keys()
        if missing:
            raise RulesError(f"Rules missing required sections: {sorted(missing)}")
        if "replace_leftmost_occurrence" not in rules["operations"]:
            raise RulesError("Rules do not define replace_leftmost_occurrence")
        return rules

    def _parse_program(self, code_snippet: str) -> list[_Instruction]:
        instructions: list[_Instruction] = []
        for line_number, raw_line in enumerate(code_snippet.splitlines(), start=1):
            effective_line = raw_line.split("#", 1)[0]
            if effective_line == "":
                continue
            if not effective_line.isascii():
                raise ValueError(f"line {line_number}: non-ASCII instruction text")
            if effective_line.count("=") != 1:
                raise ValueError(
                    f"line {line_number}: instruction must contain exactly one '='"
                )

            left, right = effective_line.split("=", 1)
            left_keyword, left_string = self._parse_side(left, "left", line_number)
            right_keyword, right_string = self._parse_side(right, "right", line_number)
            instructions.append(
                _Instruction(
                    line_number=line_number,
                    left_keyword=left_keyword,
                    left_string=left_string,
                    right_keyword=right_keyword,
                    right_string=right_string,
                )
            )
        return instructions

    def _parse_side(
        self, side: str, position: str, line_number: int
    ) -> tuple[str | None, str]:
        reserved = set(
            self._rules["syntax"]["reserved_characters_by_chapter"][str(self.chapter)]
        )
        keyword: str | None = None
        literal = side

        if self.chapter != 1 and side.startswith("("):
            close = side.find(")")
            if close == -1:
                raise ValueError(f"line {line_number}: unterminated keyword")
            keyword = side[1:close]
            literal = side[close + 1 :]
            self._validate_keyword(keyword, position, line_number)

        if any(character in reserved for character in literal):
            raise ValueError(
                f"line {line_number}: reserved character used in {position} literal"
            )
        return keyword, literal

    def _validate_keyword(self, keyword: str, position: str, line_number: int) -> None:
        definition = self._rules["keywords"].get(keyword)
        if definition is None:
            raise ValueError(f"line {line_number}: invalid keyword '{keyword}'")
        if self.chapter not in definition["available_chapters"]:
            raise ValueError(
                f"line {line_number}: keyword '{keyword}' is unavailable in chapter {self.chapter}"
            )
        if position not in definition["allowed_sides"]:
            raise ValueError(
                f"line {line_number}: keyword '{keyword}' is not allowed on the {position}"
            )
        if keyword not in self._chapter_rules[f"allowed_{position}_keywords"]:
            raise ValueError(
                f"line {line_number}: keyword '{keyword}' is disallowed by chapter Rules"
            )

    @staticmethod
    def _apply_instruction(
        current: str, instruction: _Instruction
    ) -> tuple[str, bool] | None:
        if instruction.left_keyword == "start":
            if not current.startswith(instruction.left_string):
                return None
            prefix = ""
            suffix = current[len(instruction.left_string) :]
        elif instruction.left_keyword == "end":
            if not current.endswith(instruction.left_string):
                return None
            prefix = current[: len(current) - len(instruction.left_string)]
            suffix = ""
        else:
            index = current.find(instruction.left_string)
            if index == -1:
                return None
            prefix = current[:index]
            suffix = current[index + len(instruction.left_string) :]

        if instruction.right_keyword == "return":
            return instruction.right_string, True
        if instruction.right_keyword == "start":
            return instruction.right_string + prefix + suffix, False
        if instruction.right_keyword == "end":
            return prefix + suffix + instruction.right_string, False
        return prefix + instruction.right_string + suffix, False
