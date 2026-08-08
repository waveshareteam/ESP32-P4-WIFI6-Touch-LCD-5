#!/usr/bin/env python3
"""Synthetic tests for the repository-specific Markdown policy."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("check_repository_policy.py").resolve()
SPEC = importlib.util.spec_from_file_location("repository_policy", SCRIPT)
assert SPEC and SPEC.loader
POLICY = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = POLICY
SPEC.loader.exec_module(POLICY)


ENGLISH_HOME = """<div align="center">
  <h1>Test Product</h1>
  <p><a href="README_ZH.md">中文</a> · <a href="docs/GUIDE.md">📚 Documentation</a></p>
  <img src="assets/product.png" alt="Test Product">
</div>

---

## ✨ Overview

See the [guide](docs/GUIDE.md#setup).
"""

CHINESE_HOME = """<div align="center">
  <h1>Test Product</h1>
  <p><a href="README.md">English</a> · <a href="docs/GUIDE_ZH.md">📚 文档</a></p>
  <img src="assets/product.png" alt="Test Product">
</div>

---

## ✨ 概述

请参阅[指南](docs/GUIDE_ZH.md#配置)。
"""


class PolicyRepository:
    def __init__(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.write("README.md", ENGLISH_HOME)
        self.write("README_ZH.md", CHINESE_HOME)
        self.write(
            "docs/GUIDE.md",
            "[中文](GUIDE_ZH.md)\n\n# Guide\n\n## Setup\n",
        )
        self.write(
            "docs/GUIDE_ZH.md",
            "[English](GUIDE.md)\n\n# 指南\n\n## 配置\n",
        )
        self.write("assets/product.png", b"png")

    def close(self) -> None:
        self.tempdir.cleanup()

    def write(self, relative: str, content: str | bytes) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")

    def findings(self) -> list[object]:
        return POLICY.run(self.root)


class RepositoryPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = PolicyRepository()

    def tearDown(self) -> None:
        self.repo.close()

    def codes(self) -> set[str]:
        return {finding.code for finding in self.repo.findings()}

    def test_valid_repository_passes_exact_cli_invocation(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=self.repo.root,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )

    def test_missing_companion_is_rejected(self) -> None:
        (self.repo.root / "docs/GUIDE_ZH.md").unlink()
        self.assertIn("BILINGUAL_COMPANION_MISSING", self.codes())

    def test_missing_reciprocal_language_link_is_rejected(self) -> None:
        self.repo.write("docs/GUIDE.md", "# Guide\n\n## Setup\n")
        self.assertIn("BILINGUAL_RECIPROCAL_LINK_MISSING", self.codes())

    def test_broken_relative_target_and_fragment_are_rejected(self) -> None:
        self.repo.write(
            "docs/GUIDE.md",
            "[中文](GUIDE_ZH.md)\n\n[Missing](NOPE.md)\n",
        )
        codes = self.codes()
        self.assertIn("RELATIVE_LINK_TARGET_MISSING", codes)
        self.repo.write("docs/GUIDE.md", "[中文](GUIDE_ZH.md#no-such-heading)\n")
        self.assertIn("RELATIVE_LINK_FRAGMENT_MISSING", self.codes())

    def test_wrong_language_internal_link_is_rejected(self) -> None:
        self.repo.write(
            "README_ZH.md",
            CHINESE_HOME.replace("docs/GUIDE_ZH.md#配置", "docs/GUIDE.md#setup"),
        )
        self.assertIn("WRONG_LANGUAGE_INTERNAL_LINK", self.codes())

    def test_public_machine_data_is_rejected_without_echoing_value(self) -> None:
        self.repo.write(
            "docs/GUIDE.md",
            "[中文](GUIDE_ZH.md)\n\nUse an actual COM42 port.\n",
        )
        self.assertIn("ACTUAL_SERIAL_PORT", self.codes())

    def test_homepage_structure_must_remain_symmetric(self) -> None:
        self.repo.write(
            "README_ZH.md",
            CHINESE_HOME.replace("## ✨ 概述", "## 概述"),
        )
        codes = self.codes()
        self.assertTrue(
            {"HOMEPAGE_H2_ICON_MISSING", "HOMEPAGE_H2_ASYMMETRY"} & codes
        )

    def test_homepage_quick_link_order_must_remain_symmetric(self) -> None:
        self.repo.write(
            "README.md",
            ENGLISH_HOME.replace(
                "📚 Documentation", "📚 Documentation · 📦 Components"
            ),
        )
        self.repo.write(
            "README_ZH.md",
            CHINESE_HOME.replace("📚 文档", "📦 组件 · 📚 文档"),
        )
        self.assertIn("HOMEPAGE_QUICK_LINK_ASYMMETRY", self.codes())


if __name__ == "__main__":
    unittest.main(verbosity=2)
