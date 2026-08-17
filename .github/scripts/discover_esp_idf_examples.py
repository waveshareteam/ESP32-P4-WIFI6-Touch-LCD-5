#!/usr/bin/env python3
"""Classify a complete Git diff and select first-party ESP-IDF examples."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


DEFAULT_IDF_VERSIONS = ("v5.5.5", "v6.0.2")
EXAMPLE_ROOT = "examples/esp-idf"
FIRMWARE_ROOTS = ("firmware", "Firmware", "FirmWare")

# These inputs can change how every first-party example is built.
GLOBAL_BUILD_PATTERNS = (
    ".github/workflows/esp-idf-examples.yml",
    ".github/scripts/discover_esp_idf_examples.py",
    ".github/scripts/test_discover_esp_idf_examples.py",
    "config/**",
    "components/**",
    "CMakeLists.txt",
    "dependencies.lock",
    "idf_component.yml",
)

# These repository-policy inputs are checked by the always-visible lightweight
# job. They must not schedule product builds or be hidden as unknown paths.
LIGHTWEIGHT_POLICY_PATTERNS = (
    ".github/scripts/check_repository_policy.py",
    ".github/scripts/test_repository_policy.py",
    ".github/scripts/check_component_contracts.py",
    ".github/scripts/test_component_contracts.py",
    ".github/scripts/evaluate_ci_result.py",
    ".github/scripts/test_evaluate_ci_result.py",
    "config/markdown-audit.json",
    ".gitignore",
)

# File-kind rules intentionally run before directory ownership rules.
DOCUMENTATION_PATTERNS = (
    "*.md",
    "**/*.md",
    "README*",
    "LICENSE*",
    "COPYING*",
    "CONTRIBUTING*",
    "SUPPORT*",
    "docs/**",
    "assets/**",
    "schematic/**",
    "schematics/**",
    "hardware/**",
    ".github/ISSUE_TEMPLATE/**",
    ".github/PULL_REQUEST_TEMPLATE/**",
    ".github/pull_request_template*",
)

RELEASE_ARTIFACT_SUFFIXES = (".bin", ".zip")


class ScopeError(RuntimeError):
    """The changed-file scope could not be established completely."""


@dataclass(frozen=True)
class ChangedRecord:
    status: str
    paths: tuple[str, ...]


@dataclass
class Route:
    selected: set[str]
    changed_paths: list[str]
    docs_only: bool = True
    firmware_changed: bool = False
    release_review: bool = False
    unknown_paths: list[str] | None = None

    def __post_init__(self) -> None:
        if self.unknown_paths is None:
            self.unknown_paths = []


def normalize_path(value: str) -> str:
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ScopeError("repository paths must not contain control characters")
    return value.replace("\\", "/").strip("/")


def matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def is_documentation(path: str) -> bool:
    return matches(path, DOCUMENTATION_PATTERNS)


def is_project(path: Path) -> bool:
    return (path / "CMakeLists.txt").is_file() and (path / "main").is_dir()


def list_examples(repo: Path = Path(".")) -> list[str]:
    root = repo / EXAMPLE_ROOT
    if not root.is_dir():
        return []

    examples: list[str] = []
    for path in root.iterdir():
        if not path.is_dir() or not is_project(path):
            continue
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", path.name):
            raise ScopeError(
                "unsafe first-party example directory name: "
                + path.relative_to(repo).as_posix()
            )
        examples.append(path.relative_to(repo).as_posix())
    return sorted(examples)


def run_git_bytes(args: list[str]) -> bytes:
    result = subprocess.run(
        ["git", *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ScopeError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def run_git_text(args: list[str]) -> str:
    return run_git_bytes(args).decode("utf-8", errors="strict").strip()


def parse_name_status_z(raw: bytes) -> list[ChangedRecord]:
    tokens = raw.split(b"\0")
    if tokens and tokens[-1] == b"":
        tokens.pop()

    records: list[ChangedRecord] = []
    index = 0
    while index < len(tokens):
        status = tokens[index].decode("utf-8", errors="strict")
        index += 1
        if not status:
            raise ScopeError("empty Git status in changed-file data")

        path_count = 2 if status[0] in {"R", "C"} else 1
        if index + path_count > len(tokens):
            raise ScopeError(f"incomplete Git record for status {status}")
        paths = tuple(
            normalize_path(tokens[index + offset].decode("utf-8", errors="strict"))
            for offset in range(path_count)
        )
        index += path_count
        if any(not path for path in paths):
            raise ScopeError(f"empty path in Git record for status {status}")
        records.append(ChangedRecord(status=status, paths=paths))
    return records


def parse_changed_files_file(path: Path) -> list[ChangedRecord]:
    if not path.is_file():
        raise ScopeError(f"changed-file input does not exist: {path}")

    records: list[ChangedRecord] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line
        if line == "":
            continue
        fields = line.split("\t")
        if len(fields) == 1:
            records.append(ChangedRecord(status="M", paths=(normalize_path(fields[0]),)))
            continue

        status = fields[0]
        expected = 3 if status and status[0] in {"R", "C"} else 2
        if len(fields) != expected:
            raise ScopeError(
                f"invalid changed-file record on line {line_number}: {raw_line}"
            )
        records.append(
            ChangedRecord(
                status=status,
                paths=tuple(normalize_path(value) for value in fields[1:]),
            )
        )
    return records


def changed_records(base_ref: str | None, head_ref: str) -> list[ChangedRecord]:
    if base_ref:
        raw = run_git_bytes(
            [
                "diff",
                "--name-status",
                "-z",
                "--find-renames",
                f"{base_ref}...{head_ref}",
            ]
        )
    else:
        raw = run_git_bytes(
            [
                "diff-tree",
                "--root",
                "--no-commit-id",
                "--name-status",
                "-r",
                "-z",
                "--find-renames",
                head_ref,
            ]
        )
    return parse_name_status_z(raw)


def example_for_path(path: str, known_examples: set[str]) -> str | None:
    for example in sorted(known_examples):
        if path == example or path.startswith(example + "/"):
            return example
    return None


def classify_records(
    records: list[ChangedRecord], known_examples: set[str]
) -> Route:
    if not records:
        raise ScopeError(
            "changed-file scope is empty; refusing to guess or silently pass"
        )

    route = Route(selected=set(), changed_paths=[])
    seen_paths: set[str] = set()

    for record in records:
        for raw_path in record.paths:
            path = normalize_path(raw_path)
            if path in seen_paths:
                continue
            seen_paths.add(path)
            route.changed_paths.append(path)

            if matches(path, LIGHTWEIGHT_POLICY_PATTERNS):
                route.docs_only = False
                continue

            if matches(path, GLOBAL_BUILD_PATTERNS):
                route.docs_only = False
                route.selected.update(known_examples)
                continue

            firmware_root = next(
                (
                    root
                    for root in FIRMWARE_ROOTS
                    if path == root or path.startswith(root + "/")
                ),
                None,
            )
            if firmware_root:
                route.firmware_changed = True
                if PurePosixPath(path).suffix.lower() in RELEASE_ARTIFACT_SUFFIXES:
                    route.release_review = True
                if not is_documentation(path):
                    route.docs_only = False
                # Delivery firmware is maintained separately and never enters the
                # default first-party example matrix.
                continue

            if is_documentation(path):
                continue

            route.docs_only = False
            example = example_for_path(path, known_examples)
            if example:
                route.selected.add(example)
                continue

            if path == EXAMPLE_ROOT or path.startswith(EXAMPLE_ROOT + "/"):
                # Shared input, renamed/deleted project, or an unfamiliar path below
                # the first-party root: validate all remaining examples and report it.
                route.selected.update(known_examples)
                route.unknown_paths.append(path)
                continue

            # A complete but unfamiliar non-document path is conservatively routed
            # to every framework entry. Missing diff data is handled separately.
            route.selected.update(known_examples)
            route.unknown_paths.append(path)

    return route


def normalize_example(value: str, known_examples: set[str]) -> str:
    value = normalize_path(value)
    if not value or value == "all":
        return value
    if value in known_examples:
        return value

    matches_by_name = [
        example for example in known_examples if PurePosixPath(example).name == value
    ]
    if len(matches_by_name) == 1:
        return matches_by_name[0]
    return value


def build_matrix(selected: list[str]) -> dict[str, list[dict[str, str]]]:
    return {
        "include": [
            {
                "example": example,
                "project_slug": re.sub(r"[^a-z0-9]+", "-", Path(example).name.lower()).strip("-"),
                "idf_version": idf_version,
            }
            for example in selected
            for idf_version in DEFAULT_IDF_VERSIONS
        ]
    }


def github_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as output:
        output.write(f"{name}={value}\n")


def emit_result(
    route: Route,
    selected: list[str],
    head_ref: str,
    mode: str,
) -> dict[str, object]:
    matrix = build_matrix(selected)
    head_sha = run_git_text(["rev-parse", head_ref])
    result: dict[str, object] = {
        "mode": mode,
        "head_sha": head_sha,
        "idf_versions": list(DEFAULT_IDF_VERSIONS),
        "examples": selected,
        "matrix": matrix,
        "docs_only": route.docs_only,
        "firmware_changed": route.firmware_changed,
        "release_review": route.release_review,
        "unknown_paths": sorted(set(route.unknown_paths or [])),
        "changed_paths": route.changed_paths,
    }

    github_output("matrix", json.dumps(matrix, separators=(",", ":")))
    github_output("has_examples", "true" if selected else "false")
    github_output("examples", ",".join(selected))
    github_output("docs_only", str(route.docs_only).lower())
    github_output("firmware_changed", str(route.firmware_changed).lower())
    github_output("release_review", str(route.release_review).lower())
    github_output(
        "unknown_paths",
        json.dumps(result["unknown_paths"], separators=(",", ":")),
    )
    github_output(
        "changed_paths",
        json.dumps(route.changed_paths, separators=(",", ":")),
    )
    github_output("head_sha", head_sha)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select first-party ESP-IDF examples from a complete Git diff."
    )
    parser.add_argument("--base-ref")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--changed-files-from", type=Path)
    parser.add_argument(
        "--example",
        default="",
        help="Manual selection: all, one example directory name, or its path.",
    )
    parser.add_argument("--expect-docs-only", action="store_true")
    parser.add_argument("--expect-no-example-builds", action="store_true")
    parser.add_argument("--strict-unknown", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        known_examples = set(list_examples())
        if not known_examples:
            raise ScopeError(f"no first-party projects found below {EXAMPLE_ROOT}")

        requested = normalize_example(args.example, known_examples)
        if requested:
            if requested == "all":
                selected = sorted(known_examples)
            elif requested in known_examples:
                selected = [requested]
            else:
                print(f"Unknown ESP-IDF example: {args.example}", file=sys.stderr)
                print("Known examples:", file=sys.stderr)
                for example in sorted(known_examples):
                    print(f"  {example}", file=sys.stderr)
                return 1
            route = Route(
                selected=set(selected),
                changed_paths=[],
                docs_only=False,
            )
            mode = "manual"
        else:
            if args.changed_files_from and args.base_ref:
                raise ScopeError(
                    "--changed-files-from and --base-ref are mutually exclusive"
                )
            if args.changed_files_from:
                records = parse_changed_files_file(args.changed_files_from)
                mode = "changed-files"
            else:
                records = changed_records(args.base_ref, args.head_ref)
                mode = "git-diff"
            route = classify_records(records, known_examples)
            selected = sorted(route.selected)

        if args.expect_docs_only and not route.docs_only:
            print("expected a documentation-only scope", file=sys.stderr)
            return 1
        if args.expect_no_example_builds and selected:
            print(
                "expected zero example builds, selected: " + ", ".join(selected),
                file=sys.stderr,
            )
            return 1
        if args.strict_unknown and route.unknown_paths:
            print(
                "unclassified non-document paths: "
                + ", ".join(sorted(set(route.unknown_paths))),
                file=sys.stderr,
            )
            return 1

        result = emit_result(route, selected, args.head_ref, mode)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except ScopeError as error:
        print(f"scope error: {error}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError, ValueError) as error:
        print(f"scope error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
