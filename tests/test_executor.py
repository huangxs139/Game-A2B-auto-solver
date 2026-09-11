"""Verification for the Rules-driven A=B Executor."""

from io import StringIO
import json
import unittest

from src.executor import Executor, TerminationKind


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
