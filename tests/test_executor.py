"""Verification for the Rules-driven A=B Executor."""

from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import yaml

from src.executor import DEFAULT_RULES_PATH, Executor, TerminationKind


class ExecutorTests(unittest.TestCase):
    def test_plain_replacement_restarts_from_first_line(self) -> None:
        result = Executor(1).execute("ab", "a=b\nb=c")

        self.assertEqual("cc", result.output)
        self.assertEqual(TerminationKind.NORMAL, result.termination)
        self.assertEqual(3, result.steps)

    def test_multi_character_patterns_preserve_correct_boundaries(self) -> None:
        self.assertEqual("cbaa", Executor(1).execute("aaaa", "aaa=cba").output)
        self.assertEqual(
            "dexy", Executor(3).execute("abcde", "(start)abc=(end)xy").output
        )
        self.assertEqual(
            "xyab", Executor(3).execute("abcde", "(end)cde=(start)xy").output
        )
        self.assertEqual(
            "XYzq", Executor(3).execute("zabcq", "abc=(start)XY").output
        )
        self.assertEqual(
            "zqXY", Executor(3).execute("zabcq", "abc=(end)XY").output
        )
        self.assertEqual(
            "done", Executor(2).execute("abcabc", "abc=(return)done").output
        )
        self.assertEqual(
            "xyabc", Executor(4).execute("abcabc", "(once)abc=xy").output
        )

    def test_empty_sides_follow_rules(self) -> None:
        self.assertEqual("babc", Executor(4).execute("abc", "(once)=b").output)
        self.assertEqual("bc", Executor(1).execute("abc", "a=").output)

    def test_return_replaces_entire_string_and_halts(self) -> None:
        result = Executor(2).execute("abc", "a=(return)done\n=never")

        self.assertEqual("done", result.output)
        self.assertEqual(TerminationKind.RETURN, result.termination)
        self.assertEqual(1, result.steps)

    def test_start_and_end_keywords_on_both_sides(self) -> None:
        executor = Executor(3)

        self.assertEqual("xb", executor.execute("ab", "(start)a=(start)x").output)
        self.assertEqual("ax", executor.execute("ab", "(end)b=(end)x").output)
        self.assertEqual("bx", executor.execute("ab", "(start)a=(end)x").output)

    def test_once_is_consumed_only_after_a_successful_execution(self) -> None:
        executor = Executor(4)

        first = executor.execute("aba", "(once)a=(start)x")
        second = executor.execute("aba", "(once)a=(start)x")
        self.assertEqual("xba", first.output)
        self.assertEqual("xba", second.output)
        self.assertEqual(1, first.steps)
        self.assertEqual(1, second.steps)

    def test_chapter_five_exposes_once_and_chapter_six_rejects_keywords(self) -> None:
        self.assertEqual("xb", Executor(5).execute("ab", "(once)a=(start)x").output)

        invalid = Executor(6).execute("a", "a=(return)b")
        self.assertEqual(TerminationKind.INVALID_PROGRAM, invalid.termination)
        self.assertIn("unavailable", invalid.errors[0])

    def test_chapter_one_treats_parentheses_as_literal_text(self) -> None:
        result = Executor(1).execute("(a)", "(a)=b")

        self.assertEqual("b", result.output)
        self.assertEqual(TerminationKind.NORMAL, result.termination)

    def test_comments_are_ignored_but_whitespace_is_significant(self) -> None:
        self.assertEqual("b", Executor(1).execute("a", "a=b# ignored").output)

        whitespace = Executor(1).execute("a", "a =b")
        self.assertEqual("a", whitespace.output)
        self.assertEqual(TerminationKind.NORMAL, whitespace.termination)

    def test_invalid_program_is_not_an_executor_error(self) -> None:
        result = Executor(2).execute("a", "(start)a=b")

        self.assertEqual(TerminationKind.INVALID_PROGRAM, result.termination)
        self.assertFalse(result.errors[0].startswith("Executor"))

    def test_program_line_limit_counts_comments_and_implicit_final_newline(
        self,
    ) -> None:
        accepted_code = "a=b#" + "x" * 250
        rejected_code = accepted_code + "x"

        accepted = Executor(1).execute("a", accepted_code)
        rejected = Executor(1).execute("a", rejected_code)

        self.assertEqual(254, len(accepted_code))
        self.assertEqual(TerminationKind.NORMAL, accepted.termination)
        self.assertEqual("b", accepted.output)
        self.assertEqual(TerminationKind.INVALID_PROGRAM, rejected.termination)
        self.assertIn("serialized length 256", rejected.errors[0])

    def test_operating_string_limit_checks_initial_and_generated_states(self) -> None:
        executor = Executor(1)

        maximum = executor.execute("a" * 255, "z=y")
        oversized_input = executor.execute("a" * 256, "z=y")
        oversized_result = executor.execute("a" * 255, "a=aa", debug=True)

        self.assertEqual(TerminationKind.NORMAL, maximum.termination)
        self.assertEqual(TerminationKind.INVALID_PROGRAM, oversized_input.termination)
        self.assertEqual(0, oversized_input.steps)
        self.assertIn("initial input", oversized_input.errors[0])
        self.assertEqual(TerminationKind.INVALID_PROGRAM, oversized_result.termination)
        self.assertEqual(1, oversized_result.steps)
        self.assertIn("result of line 1", oversized_result.errors[0])
        self.assertEqual(1, len(oversized_result.observations))

    def test_length_limit_values_are_loaded_from_rules(self) -> None:
        rules = yaml.safe_load(DEFAULT_RULES_PATH.read_text(encoding="utf-8"))
        rules["limits"]["program_lines"]["maximum_characters"] = 5
        rules["limits"]["operating_string"]["maximum_characters"] = 3

        with TemporaryDirectory() as directory:
            rules_path = Path(directory) / "rules.yaml"
            rules_path.write_text(yaml.safe_dump(rules), encoding="utf-8")
            executor = Executor(1, rules_path=rules_path)

            accepted = executor.execute("aaa", "a=b#")
            long_line = executor.execute("a", "a=b#x")
            long_state = executor.execute("aaaa", "a=b")

        self.assertEqual(TerminationKind.NORMAL, accepted.termination)
        self.assertEqual(TerminationKind.INVALID_PROGRAM, long_line.termination)
        self.assertEqual(TerminationKind.INVALID_PROGRAM, long_state.termination)

    def test_repeated_state_is_detected_as_nontermination(self) -> None:
        result = Executor(1).execute("a", "a=a")

        self.assertEqual(TerminationKind.NONTERMINATION, result.termination)
        self.assertTrue(result.loop_detected)
        self.assertEqual(1, result.steps)

    def test_growing_nonterminating_program_is_stopped_by_step_limit(self) -> None:
        result = Executor(1, max_steps=3).execute("a", "=b")

        self.assertEqual(TerminationKind.NONTERMINATION, result.termination)
        self.assertFalse(result.loop_detected)
        self.assertEqual(3, result.steps)

    def test_debug_observations_do_not_change_execution_result(self) -> None:
        executor = Executor(3)
        normal = executor.execute("ab", "(start)a=(end)x")
        debug = executor.execute("ab", "(start)a=(end)x", debug=True)

        self.assertEqual(normal.output, debug.output)
        self.assertEqual(normal.termination, debug.termination)
        self.assertEqual(1, len(debug.observations))
        self.assertEqual("ab", debug.observations[0].before)
        self.assertEqual("bx", debug.observations[0].after)

        stream = StringIO()
        Executor.dump_observations(debug, stream)
        self.assertEqual("bx", json.loads(stream.getvalue())[0]["after"])


if __name__ == "__main__":
    unittest.main()
