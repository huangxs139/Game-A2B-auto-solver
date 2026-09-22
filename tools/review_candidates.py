"""Interactive terminal tool for owner review of generated candidates."""

from __future__ import annotations

import argparse
from enum import Enum
import json
import os
from pathlib import Path
import re
import shutil
import sys
from tempfile import NamedTemporaryFile
import textwrap
from typing import Callable, Sequence, TextIO


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_DIRECTORY = REPOSITORY_ROOT / "test_output"
_STATE_NAME_PATTERN = re.compile(
    r"^c(?P<chapter>\d+)_(?P<number>\d+)_.+\.solve$"
)
_COORDINATE_PATTERN = re.compile(r"^(?P<chapter>\d+)[-_](?P<number>\d+)$")
_REVIEW_STATUSES = ("accepted", "rejected", "re-solve", "pending")
_DECISION_CHOICES = {
    "1": "accepted",
    "a": "accepted",
    "accepted": "accepted",
    "2": "rejected",
    "j": "rejected",
    "rejected": "rejected",
    "3": "re-solve",
    "r": "re-solve",
    "re-solve": "re-solve",
}


class CandidateReviewError(RuntimeError):
    """Raised when candidate state cannot be reviewed safely."""


class _Navigation(Enum):
    BACK = "back"
    QUIT = "quit"


def _state_sort_key(path: Path) -> tuple[int, int, str]:
    match = _STATE_NAME_PATTERN.fullmatch(path.name)
    if match is None:
        return (sys.maxsize, sys.maxsize, path.name)
    return (int(match.group("chapter")), int(match.group("number")), path.name)


def _read_state(path: Path) -> dict[str, object]:
    try:
        with path.open(encoding="utf-8") as stream:
            state = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateReviewError(f"cannot read {path.name}: {exc}") from exc
    if not isinstance(state, dict):
        raise CandidateReviewError(f"{path.name} must contain a JSON object")
    problem_id = state.get("problem_id")
    candidate = state.get("candidate")
    status = state.get("status")
    if problem_id != path.stem:
        raise CandidateReviewError(
            f"{path.name} problem_id does not match its filename"
        )
    if not isinstance(candidate, str):
        raise CandidateReviewError(f"{path.name} has no reviewable candidate")
    if status not in _REVIEW_STATUSES:
        raise CandidateReviewError(f"{path.name} has invalid status {status!r}")
    reason = state.get("reason")
    if reason is not None and not isinstance(reason, str):
        raise CandidateReviewError(f"{path.name} has a non-text reason")
    return state


def _write_state_atomically(path: Path, state: dict[str, object]) -> None:
    temporary_name: str | None = None
    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.stem}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
            temporary_name = stream.name
        os.replace(temporary_name, path)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def update_owner_decision(
    path: Path,
    status: str,
    reason: str | None = None,
) -> None:
    """Update only owner-controlled fields while preserving candidate facts."""

    if status not in {"accepted", "rejected", "re-solve"}:
        raise ValueError(f"unsupported owner decision: {status!r}")
    state = _read_state(path)
    state["status"] = status
    if status == "accepted" or not reason:
        state.pop("reason", None)
    else:
        state["reason"] = reason
    _write_state_atomically(path, state)


class CandidateReviewTUI:
    """Small line-oriented TUI for reviewing persisted candidates."""

    def __init__(
        self,
        state_directory: Path | str = DEFAULT_STATE_DIRECTORY,
        *,
        input_function: Callable[[str], str] = input,
        output: TextIO | None = None,
    ) -> None:
        self.state_directory = Path(state_directory)
        self._input = input_function
        self._output = output or sys.stdout

    def run(self) -> int:
        self._write("A2B Candidate Review")
        while True:
            self._write("\n[r] Review candidate  [s] Status summary  [q] Quit")
            try:
                choice = self._input("Choice: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                self._write("\nReview tool closed.")
                return 0
            if choice in {"q", "quit"}:
                self._write("Review tool closed.")
                return 0
            if choice in {"r", "review"}:
                if not self.review_candidates():
                    self._write("Review tool closed.")
                    return 0
            elif choice in {"s", "summary"}:
                self.show_summary()
            else:
                self._write("Unknown choice. Enter r, s, or q.")

    def review_candidates(self) -> bool:
        notice: str | None = None
        while True:
            self._clear_screen()
            if notice is not None:
                self._write(notice)
                self._write("")
                notice = None
            grouped = self.show_summary()
            default_problem_id = (
                grouped["pending"][0] if grouped["pending"] else None
            )
            if default_problem_id is None:
                self._write("\nNo pending candidates remain. Returning to main menu.")
                return True
            coordinate = self._read_coordinate(default_problem_id)
            if coordinate is _Navigation.BACK:
                return True
            if coordinate is _Navigation.QUIT:
                return False
            notice = self._review_candidate(coordinate)

    def _review_candidate(self, coordinate: tuple[int, int]) -> str:
        chapter, puzzle = coordinate
        try:
            path = self._find_state(chapter, puzzle)
            state = _read_state(path)
        except CandidateReviewError as exc:
            return f"No change made: {exc}"

        problem_id = str(state["problem_id"])
        candidate = str(state["candidate"])
        self._write(f"\nPuzzle: {problem_id}")
        self._write(f"Current status: {state['status']}")
        if state.get("reason"):
            self._write(f"Current reason: {state['reason']}")
        self._write("\n--- candidate (copy text below) ---")
        self._write(candidate)
        self._write("--- end candidate ---")
        self._write("\n[1] Accepted  [2] Rejected  [3] Re-solve  [s] Skip")
        decision = self._input("Test result: ").strip().lower()
        if decision in {"s", "skip", "b", "back", ""}:
            return "No change made."
        if decision in {"q", "quit"}:
            return "No change made. Use q at the coordinate prompt to quit."
        status = _DECISION_CHOICES.get(decision)
        if status is None:
            return "Invalid test result; no change made."

        reason: str | None = None
        if status != "accepted":
            reason = self._input("Failure reason (optional): ").strip() or None
        try:
            update_owner_decision(path, status, reason)
        except (CandidateReviewError, OSError) as exc:
            return f"No change made: {exc}"
        return f"Saved {problem_id} as {status}."

    def show_summary(self) -> dict[str, list[str]]:
        grouped = {status: [] for status in _REVIEW_STATUSES}
        errors: list[str] = []
        if self.state_directory.is_dir():
            paths = sorted(self.state_directory.glob("*.solve"), key=_state_sort_key)
        else:
            paths = []
        for path in paths:
            try:
                state = _read_state(path)
            except CandidateReviewError as exc:
                errors.append(str(exc))
                continue
            grouped[str(state["status"])].append(str(state["problem_id"]))

        terminal_width = shutil.get_terminal_size(fallback=(100, 24)).columns
        puzzle_width = max(30, terminal_width - 22)
        self._write("\nStatus summary")
        self._write(f"{'STATUS':<10} {'COUNT':>5}  PUZZLES")
        self._write(f"{'-' * 10} {'-' * 5}  {'-' * puzzle_width}")
        for status in _REVIEW_STATUSES:
            puzzle_text = ", ".join(grouped[status]) or "(none)"
            wrapped = textwrap.wrap(
                puzzle_text,
                width=puzzle_width,
                break_long_words=False,
                break_on_hyphens=False,
            ) or ["(none)"]
            self._write(f"{status:<10} {len(grouped[status]):>5}  {wrapped[0]}")
            for continuation in wrapped[1:]:
                self._write(f"{'':<10} {'':>5}  {continuation}")
        if errors:
            self._write("\nINVALID STATE FILES:")
            for error in errors:
                self._write(f"  {error}")
        return grouped

    def _find_state(self, chapter: int, puzzle: int) -> Path:
        if not self.state_directory.is_dir():
            raise CandidateReviewError(
                f"state directory does not exist: {self.state_directory}"
            )
        matches = []
        for path in self.state_directory.glob("*.solve"):
            match = _STATE_NAME_PATTERN.fullmatch(path.name)
            if (
                match is not None
                and int(match.group("chapter")) == chapter
                and int(match.group("number")) == puzzle
            ):
                matches.append(path)
        if not matches:
            raise CandidateReviewError(
                f"no candidate found for chapter {chapter}, puzzle {puzzle}"
            )
        if len(matches) > 1:
            names = ", ".join(sorted(path.name for path in matches))
            raise CandidateReviewError(
                f"multiple candidates found for chapter {chapter}, puzzle {puzzle}: "
                f"{names}"
            )
        return matches[0]

    def _read_coordinate(
        self, default_problem_id: str
    ) -> tuple[int, int] | _Navigation:
        default_match = _STATE_NAME_PATTERN.fullmatch(
            f"{default_problem_id}.solve"
        )
        assert default_match is not None
        default_coordinate = (
            int(default_match.group("chapter")),
            int(default_match.group("number")),
        )
        default_text = f"{default_coordinate[0]}-{default_coordinate[1]}"
        while True:
            value = self._input(
                f"Puzzle coordinate [{default_text}] "
                "(Enter=default, b=menu, q=quit): "
            ).strip().lower()
            if not value:
                return default_coordinate
            if value in {"b", "back"}:
                return _Navigation.BACK
            if value in {"q", "quit"}:
                return _Navigation.QUIT
            match = _COORDINATE_PATTERN.fullmatch(value)
            if match is None:
                self._write(
                    "Invalid coordinate. Use chapter-puzzle, such as 1-5."
                )
                continue
            chapter = int(match.group("chapter"))
            puzzle = int(match.group("number"))
            if chapter <= 0 or puzzle <= 0:
                self._write("Chapter and puzzle numbers must be positive.")
                continue
            return chapter, puzzle

    def _clear_screen(self) -> None:
        self._output.write("\033[2J\033[H")
        self._output.flush()

    def _write(self, text: str) -> None:
        print(text, file=self._output)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Interactively review A2B candidate solutions."
    )
    parser.add_argument(
        "--state-directory",
        type=Path,
        default=DEFAULT_STATE_DIRECTORY,
        help="directory containing .solve files (default: repository test_output)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    return CandidateReviewTUI(args.state_directory).run()


if __name__ == "__main__":
    raise SystemExit(main())
