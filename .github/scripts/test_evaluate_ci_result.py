#!/usr/bin/env python3
"""Executable truth-table tests for the ESP-IDF aggregate result helper."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("evaluate_ci_result.py").resolve()
HEAD_SHA = "a" * 40


class EvaluateCiResultTests(unittest.TestCase):
    def evaluate(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *arguments],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def arguments(
        self,
        validate_result: str = "success",
        has_examples: str = "false",
        build_result: str = "skipped",
        release_review: str = "false",
        head_sha: str = HEAD_SHA,
    ) -> tuple[str, ...]:
        return (
            "--validate-result",
            validate_result,
            "--has-examples",
            has_examples,
            "--build-result",
            build_result,
            "--release-review",
            release_review,
            "--head-sha",
            head_sha,
        )

    def assert_result(
        self, expected_code: int, expected_stdout: str, expected_stderr: str, *arguments: str
    ) -> None:
        result = self.evaluate(*arguments)
        self.assertEqual(result.returncode, expected_code)
        self.assertEqual(result.stdout, expected_stdout)
        self.assertEqual(result.stderr, expected_stderr)

    def test_validate_failure_does_not_parse_empty_scope_outputs(self) -> None:
        for validate_result in ("failure", "cancelled", "skipped"):
            with self.subTest(validate_result=validate_result):
                self.assert_result(
                    1,
                    "",
                    "Repository policy validation did not pass.\n",
                    *self.arguments(
                        validate_result=validate_result,
                        has_examples="",
                        build_result="",
                        release_review="",
                        head_sha="",
                    ),
                )

    def test_success_with_empty_scope_outputs_fails_argument_validation(self) -> None:
        result = self.evaluate(*self.arguments(has_examples="", build_result="", release_review="", head_sha=""))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "invalid --has-examples: must be 'true' or 'false'\n")

    def test_release_review_fails_with_each_build_result(self) -> None:
        for build_result in ("skipped", "success", "failure"):
            with self.subTest(build_result=build_result):
                self.assert_result(
                    1,
                    "",
                    "Immutable artifact changes require an independent protected release process.\n",
                    *self.arguments(build_result=build_result, release_review="true"),
                )

    def test_docs_only_skipped_build_passes_without_release_review(self) -> None:
        self.assert_result(
            0,
            f"Required validation passed for {HEAD_SHA}.\n",
            "",
            *self.arguments(),
        )

    def test_examples_require_a_successful_build(self) -> None:
        for build_result, expected_code in (
            ("success", 0),
            ("failure", 1),
            ("cancelled", 1),
            ("skipped", 1),
        ):
            with self.subTest(build_result=build_result):
                if expected_code == 0:
                    self.assert_result(
                        0,
                        f"Required validation passed for {HEAD_SHA}.\n",
                        "",
                        *self.arguments(has_examples="true", build_result=build_result),
                    )
                else:
                    self.assert_result(
                        1,
                        "",
                        "One or more required ESP-IDF matrix builds did not pass.\n",
                        *self.arguments(has_examples="true", build_result=build_result),
                    )

    def test_malformed_arguments_fail_with_a_stable_message(self) -> None:
        for arguments, expected_message in (
            (self.arguments(validate_result="pending"), "must be one of: success, failure, cancelled, skipped"),
            (self.arguments(has_examples="True"), "must be 'true' or 'false'"),
            (self.arguments(head_sha="not-a-sha"), "must be a 40-character lowercase Git SHA"),
        ):
            with self.subTest(arguments=arguments):
                result = self.evaluate(*arguments)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn(expected_message, result.stderr)
                self.assertNotIn(str(SCRIPT), result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
