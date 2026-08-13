#!/usr/bin/env python3
"""Fail-closed aggregate result evaluation for the ESP-IDF examples workflow."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import re
import sys


WORKFLOW_RESULTS = ("success", "failure", "cancelled", "skipped")


def workflow_result(value: str) -> str:
    if value not in WORKFLOW_RESULTS:
        raise argparse.ArgumentTypeError(
            "must be one of: " + ", ".join(WORKFLOW_RESULTS)
        )
    return value


def boolean(value: str) -> bool:
    if value not in ("true", "false"):
        raise argparse.ArgumentTypeError("must be 'true' or 'false'")
    return value == "true"


def head_sha(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise argparse.ArgumentTypeError("must be a 40-character lowercase Git SHA")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="evaluate_ci_result.py",
        description="Evaluate the fail-closed ESP-IDF examples aggregate result.",
    )
    # Keep these as raw strings so a failed validation job can be reported even
    # when its scope-dependent outputs are unavailable.
    parser.add_argument("--validate-result", required=True)
    parser.add_argument("--has-examples", required=True)
    parser.add_argument("--build-result", required=True)
    parser.add_argument("--release-review", required=True)
    parser.add_argument("--head-sha", required=True)
    return parser.parse_args()


def parse_option(
    name: str, value: str, validator: Callable[[str], str | bool]
) -> str | bool | None:
    try:
        return validator(value)
    except argparse.ArgumentTypeError as error:
        print(f"invalid --{name}: {error}", file=sys.stderr)
        return None


def main() -> int:
    args = parse_args()
    validate_result = parse_option("validate-result", args.validate_result, workflow_result)
    if validate_result is None:
        return 2
    if validate_result != "success":
        print("Repository policy validation did not pass.", file=sys.stderr)
        return 1

    has_examples = parse_option("has-examples", args.has_examples, boolean)
    if has_examples is None:
        return 2
    build_result = parse_option("build-result", args.build_result, workflow_result)
    if build_result is None:
        return 2
    release_review = parse_option("release-review", args.release_review, boolean)
    if release_review is None:
        return 2
    validated_head_sha = parse_option("head-sha", args.head_sha, head_sha)
    if validated_head_sha is None:
        return 2

    if release_review:
        print(
            "Immutable artifact changes require an independent protected release process.",
            file=sys.stderr,
        )
        return 1
    if has_examples and build_result != "success":
        print("One or more required ESP-IDF matrix builds did not pass.", file=sys.stderr)
        return 1
    print(f"Required validation passed for {validated_head_sha}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
