#!/usr/bin/env python3
"""Synthetic end-to-end tests for CI changed-file routing."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("discover_esp_idf_examples.py").resolve()


class SyntheticRepository:
    def __init__(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.git("init", "-q")
        self.git("config", "user.email", "ci@example.invalid")
        self.git("config", "user.name", "CI Test")
        self.write("README.md", "# Test repository\n")
        for name in ("alpha", "beta"):
            self.write(f"examples/esp-idf/{name}/CMakeLists.txt", "# project\n")
            self.write(f"examples/esp-idf/{name}/main/app.c", "void app_main(void) {}\n")
            self.write(f"examples/esp-idf/{name}/main/keep.c", "/* keep */\n")
        self.write(
            "examples/esp-idf/alpha/components/dependency/test_apps/nested/"
            "CMakeLists.txt",
            "# nested test app\n",
        )
        self.write(
            "examples/esp-idf/alpha/components/dependency/test_apps/nested/"
            "main/app.c",
            "void app_main(void) {}\n",
        )
        self.commit("baseline")
        self.base = self.rev()

    def close(self) -> None:
        self.tempdir.cleanup()

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def write(self, relative: str, content: str | bytes) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")

    def remove(self, relative: str) -> None:
        (self.root / relative).unlink()

    def rename(self, old: str, new: str) -> None:
        destination = self.root / new
        destination.parent.mkdir(parents=True, exist_ok=True)
        (self.root / old).rename(destination)

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def rev(self) -> str:
        return self.git("rev-parse", "HEAD").stdout.strip()

    def route(
        self,
        *args: str,
        expected_code: int = 0,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object] | None]:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=self.root,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self_test = unittest.TestCase()
        self_test.assertEqual(
            result.returncode,
            expected_code,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        payload = json.loads(result.stdout) if result.returncode == 0 else None
        return result, payload

    def route_diff(self) -> dict[str, object]:
        _, payload = self.route(
            "--base-ref",
            self.base,
            "--head-ref",
            self.rev(),
        )
        assert payload is not None
        return payload


class RoutingContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = SyntheticRepository()

    def tearDown(self) -> None:
        self.repo.close()

    def test_manual_all_name_and_path_use_current_matrix(self) -> None:
        for value, expected_examples in (
            ("all", ["examples/esp-idf/alpha", "examples/esp-idf/beta"]),
            ("alpha", ["examples/esp-idf/alpha"]),
            ("examples/esp-idf/beta", ["examples/esp-idf/beta"]),
        ):
            with self.subTest(value=value):
                _, payload = self.repo.route("--example", value)
                assert payload is not None
                self.assertEqual(payload["examples"], expected_examples)
                self.assertEqual(payload["idf_versions"], ["v5.5.5", "v6.0.2"])
                self.assertEqual(
                    len(payload["matrix"]["include"]),
                    len(expected_examples) * 2,
                )

    def test_nested_component_test_app_is_not_first_party_or_manually_selectable(self) -> None:
        _, payload = self.repo.route("--example", "all")
        assert payload is not None
        self.assertEqual(
            payload["examples"],
            ["examples/esp-idf/alpha", "examples/esp-idf/beta"],
        )
        self.repo.route(
            "--example",
            "examples/esp-idf/alpha/components/dependency/test_apps/nested",
            expected_code=1,
        )

    def test_root_markdown_selects_no_examples(self) -> None:
        self.repo.write("README.md", "# Updated\n")
        self.repo.commit("docs")
        payload = self.repo.route_diff()
        self.assertEqual(payload["examples"], [])
        self.assertTrue(payload["docs_only"])

    def test_markdown_inside_example_selects_no_examples(self) -> None:
        self.repo.write("examples/esp-idf/alpha/README.md", "# Alpha\n")
        self.repo.commit("example docs")
        payload = self.repo.route_diff()
        self.assertEqual(payload["examples"], [])
        self.assertTrue(payload["docs_only"])

    def test_direct_source_selects_only_affected_example(self) -> None:
        self.repo.write(
            "examples/esp-idf/alpha/main/app.c",
            "void app_main(void) { int changed = 1; }\n",
        )
        self.repo.commit("source")
        payload = self.repo.route_diff()
        self.assertEqual(payload["examples"], ["examples/esp-idf/alpha"])
        self.assertFalse(payload["docs_only"])

    def test_shared_build_input_selects_all_examples(self) -> None:
        self.repo.write("config/sdkconfig.defaults", "CONFIG_TEST=y\n")
        self.repo.commit("shared")
        payload = self.repo.route_diff()
        self.assertEqual(
            payload["examples"],
            ["examples/esp-idf/alpha", "examples/esp-idf/beta"],
        )

    def test_workflow_helper_change_selects_all_examples(self) -> None:
        self.repo.write(
            ".github/scripts/discover_esp_idf_examples.py",
            "# changed helper\n",
        )
        self.repo.commit("helper")
        payload = self.repo.route_diff()
        self.assertEqual(len(payload["examples"]), 2)

    def test_lightweight_policy_paths_select_no_examples_without_docs_only_or_unknown(self) -> None:
        scope = self.repo.root / "policy-scope.txt"
        scope.write_text(
            "\n".join(
                (
                    "M\t.github/scripts/check_repository_policy.py",
                    "M\t.github/scripts/test_repository_policy.py",
                    "M\t.github/scripts/check_component_contracts.py",
                    "M\t.github/scripts/test_component_contracts.py",
                    "M\tconfig/markdown-audit.json",
                    "M\t.gitignore",
                )
            )
            + "\n",
            encoding="utf-8",
        )
        _, payload = self.repo.route("--changed-files-from", str(scope))
        assert payload is not None
        self.assertEqual(payload["examples"], [])
        self.assertFalse(payload["docs_only"])
        self.assertEqual(payload["unknown_paths"], [])

    def test_firmware_markdown_is_docs_only_and_never_builds_examples(self) -> None:
        self.repo.write("firmware/README.md", "# Delivery notes\n")
        self.repo.commit("firmware docs")
        payload = self.repo.route_diff()
        self.assertEqual(payload["examples"], [])
        self.assertTrue(payload["docs_only"])
        self.assertTrue(payload["firmware_changed"])
        self.assertFalse(payload["release_review"])

    def test_firmware_binary_requires_release_review_but_no_example_build(self) -> None:
        self.repo.write("firmware/factory.bin", b"\x00\x01")
        self.repo.commit("firmware image")
        payload = self.repo.route_diff()
        self.assertEqual(payload["examples"], [])
        self.assertFalse(payload["docs_only"])
        self.assertTrue(payload["firmware_changed"])
        self.assertTrue(payload["release_review"])

    def test_mixed_firmware_source_config_and_archive_require_release_review_without_builds(self) -> None:
        scope = self.repo.root / "firmware-scope.txt"
        scope.write_text(
            "\n".join(
                (
                    "M\tfirmware/project/main/app.c",
                    "M\tfirmware/project/sdkconfig.defaults",
                    "M\tfirmware/delivery.zip",
                )
            )
            + "\n",
            encoding="utf-8",
        )
        _, payload = self.repo.route("--changed-files-from", str(scope))
        assert payload is not None
        self.assertEqual(payload["examples"], [])
        self.assertFalse(payload["docs_only"])
        self.assertTrue(payload["firmware_changed"])
        self.assertTrue(payload["release_review"])
        self.assertEqual(payload["unknown_paths"], [])

    def test_rename_and_deletion_preserve_project_impact(self) -> None:
        self.repo.rename(
            "examples/esp-idf/alpha/main/app.c",
            "examples/esp-idf/alpha/main/application.c",
        )
        self.repo.remove("examples/esp-idf/beta/main/app.c")
        self.repo.commit("rename and delete")
        payload = self.repo.route_diff()
        self.assertEqual(
            payload["examples"],
            ["examples/esp-idf/alpha", "examples/esp-idf/beta"],
        )

    def test_unknown_non_document_path_selects_all_and_remains_visible(self) -> None:
        self.repo.write("tools/new_policy.dat", "unknown\n")
        self.repo.commit("unknown")
        payload = self.repo.route_diff()
        self.assertEqual(len(payload["examples"]), 2)
        self.assertEqual(payload["unknown_paths"], ["tools/new_policy.dat"])

    def test_empty_changed_file_scope_fails_closed(self) -> None:
        scope = self.repo.root / "empty-scope.txt"
        scope.write_text("", encoding="utf-8")
        self.repo.route(
            "--changed-files-from",
            str(scope),
            expected_code=2,
        )

    def test_changed_file_scope_preserves_trailing_space(self) -> None:
        scope = self.repo.root / "spaced-scope.txt"
        scope.write_text("M\tnotes.md \n", encoding="utf-8")
        _, payload = self.repo.route("--changed-files-from", str(scope))
        assert payload is not None
        self.assertEqual(
            payload["examples"],
            ["examples/esp-idf/alpha", "examples/esp-idf/beta"],
        )
        self.assertEqual(payload["unknown_paths"], ["notes.md "])
        self.assertFalse(payload["docs_only"])

    def test_docs_only_expectations_are_active(self) -> None:
        self.repo.write("README.md", "# Updated\n")
        self.repo.commit("docs")
        self.repo.route(
            "--base-ref",
            self.repo.base,
            "--head-ref",
            self.repo.rev(),
            "--expect-docs-only",
            "--expect-no-example-builds",
        )

    def test_exact_git_diff_invocation_rejects_bad_ref(self) -> None:
        self.repo.route(
            "--base-ref",
            "refs/heads/does-not-exist",
            "--head-ref",
            "HEAD",
            expected_code=2,
        )

    def test_manual_input_with_control_character_fails_closed(self) -> None:
        self.repo.route(
            "--example",
            "alpha\nbeta",
            expected_code=2,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
