#!/usr/bin/env python3
"""Package one ESP-IDF CI build as a verified ESP32-P4 flash bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import zipfile
from pathlib import Path, PurePath, PureWindowsPath


BOARD = "ESP32-P4-WIFI6-Touch-LCD-5"
CHIP = "esp32p4"
DEFAULT_BAUD = 460800
FLASH_LIMIT_BYTES = 32 * 1024 * 1024
WRITE_FLASH_OPTIONS = {
    "--flash_mode": ("mode", {"qio", "qout", "dio", "dout", "keep"}),
    "--flash-mode": ("mode", {"qio", "qout", "dio", "dout", "keep"}),
    "--flash_size": ("size", {"keep", "detect", "1MB", "2MB", "4MB", "8MB", "16MB", "32MB"}),
    "--flash-size": ("size", {"keep", "detect", "1MB", "2MB", "4MB", "8MB", "16MB", "32MB"}),
    "--flash_freq": ("freq", {"keep", "20m", "26m", "40m", "80m"}),
    "--flash-freq": ("freq", {"keep", "20m", "26m", "40m", "80m"}),
}
SAFE_BEFORE = {"default_reset", "no_reset", "default-reset", "no-reset"}
SAFE_AFTER = {"hard_reset", "no_reset", "hard-reset", "no-reset"}
BOARD_PROFILES = {
    "rev1_3": {
        "minimum": "1.0",
        "maximum_exclusive": "3.0",
        "symbols": {
            "CONFIG_ESP32P4_SELECTS_REV_LESS_V3": "y",
            "CONFIG_ESP32P4_REV_MIN_100": "y",
        },
    },
    "rev3_x": {
        "minimum": "3.0",
        "maximum_exclusive": "4.0",
        "symbols": {
            "CONFIG_ESP32P4_SELECTS_REV_LESS_V3": "n",
            "CONFIG_ESP32P4_REV_MIN_300": "y",
        },
    },
}


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "firmware"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_offset(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("flash offset must be an integer")
    try:
        offset = int(str(value), 0)
    except ValueError as error:
        raise ValueError(f"invalid flash offset: {value!r}") from error
    if offset < 0:
        raise ValueError("flash offset must not be negative")
    return offset


def relative_source_project(project: Path) -> str:
    value = project.as_posix()
    windows = PureWindowsPath(value)
    if project.is_absolute() or windows.is_absolute() or ".." in PurePath(value).parts or ".." in windows.parts:
        raise ValueError("project must be a repository-relative path")
    return value


def contained_binary(build_dir: Path, raw_path: object) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("flasher binary path must be a non-empty string")
    windows = PureWindowsPath(raw_path)
    if Path(raw_path).is_absolute() or windows.is_absolute() or windows.root or ".." in PurePath(raw_path).parts or ".." in windows.parts:
        raise ValueError(f"flasher binary path must be relative: {raw_path!r}")
    candidate = (build_dir / raw_path).resolve()
    root = build_dir.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError(f"flasher binary resolves outside build directory: {raw_path!r}") from error
    return candidate


def validate_ranges(records: list[dict[str, object]]) -> None:
    ordered = sorted(records, key=lambda item: int(item["offset_value"]))
    for previous, current in zip(ordered, ordered[1:]):
        if int(previous["offset_value"]) + int(previous["size"]) > int(current["offset_value"]):
            raise ValueError("flasher binary ranges overlap")


def manifest_git_sha() -> str:
    value = os.environ.get("PACKAGE_GIT_SHA") or os.environ.get("GITHUB_SHA", "")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", value):
        raise ValueError("packaging requires a complete 40-character PACKAGE_GIT_SHA or GITHUB_SHA")
    return value.lower()


def board_profile(value: str) -> str:
    if value not in BOARD_PROFILES:
        raise ValueError(f"unsupported board profile: {value}")
    return value


def sdkconfig_values(build_dir: Path) -> dict[str, str]:
    """Read generated ESP-IDF configuration, never source defaults."""
    json_path = build_dir / "config" / "sdkconfig.json"
    if json_path.is_file():
        raw = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("generated sdkconfig.json must contain an object")
        return {
            str(key) if str(key).startswith("CONFIG_") else f"CONFIG_{key}": "y" if value is True else "n" if value is False else str(value)
            for key, value in raw.items()
        }
    for candidate in (build_dir / "sdkconfig", build_dir / "config" / "sdkconfig"):
        if candidate.is_file():
            values: dict[str, str] = {}
            for line in candidate.read_text(encoding="utf-8").splitlines():
                if line.startswith("# CONFIG_") and line.endswith(" is not set"):
                    values[line[2:-11]] = "n"
                elif line.startswith("CONFIG_") and "=" in line:
                    key, value = line.split("=", 1)
                    values[key] = value
            return values
    raise ValueError("ESP-IDF build configuration is missing (expected config/sdkconfig.json or sdkconfig)")


def validate_idf_profile(build_dir: Path, profile: str) -> None:
    values = sdkconfig_values(build_dir)
    for symbol, expected in BOARD_PROFILES[profile]["symbols"].items():
        if values.get(symbol) != expected:
            raise ValueError(f"ESP-IDF build configuration does not match {profile}: {symbol}={expected}")


def archive_name(source: Path, used: set[str]) -> str:
    if source.suffix.lower() != ".bin":
        raise ValueError("ESP-IDF flasher binary must use a .bin suffix")
    stem, counter = slugify(source.stem), 1
    while True:
        name = f"bin/{stem}{'' if counter == 1 else '-' + str(counter)}.bin"
        if name not in used:
            used.add(name)
            return name
        counter += 1


def artifact_name(source_project: str, framework_version: str, profile: str) -> str:
    """Return the schema-v1 artifact identity shared by CI and local tools."""
    prefix = "examples/esp-idf/"
    if source_project.startswith(prefix):
        relative = source_project[len(prefix):]
        match = re.fullmatch(r"([0-9]{1,3})_([A-Za-z0-9._~-]+)", relative)
        if not match:
            raise ValueError(f"unsupported ESP-IDF example project: {source_project}")
        number, label = match.groups()
        normalized = label.casefold().replace("_", "-")
        return f"firmware-{number}-{normalized}-{framework_version.replace('.', '-')}-{profile}"
    if source_project == "firmware/brookesia":
        return f"firmware-brookesia-{framework_version.replace('.', '-')}-{profile}"
    raise ValueError(f"unsupported ESP-IDF source project: {source_project}")


def parse_write_flash_args(raw: object) -> list[dict[str, str]]:
    if isinstance(raw, dict):
        pairs = list(raw.items())
    elif isinstance(raw, list) and len(raw) % 2 == 0:
        pairs = list(zip(raw[::2], raw[1::2]))
    else:
        raise ValueError("write_flash_args must be an even argument list or object")
    result: list[dict[str, str]] = []
    used_groups: set[str] = set()
    for raw_option, value in pairs:
        if not isinstance(raw_option, str) or not isinstance(value, str):
            raise ValueError("write_flash_args options and values must be strings")
        option = raw_option if raw_option.startswith("--") else f"--{raw_option}"
        rule = WRITE_FLASH_OPTIONS.get(option)
        if rule is None:
            raise ValueError(f"unsafe write_flash argument: {raw_option!r}")
        group, allowed_values = rule
        if group in used_groups or value not in allowed_values:
            raise ValueError(f"unsafe or duplicate write_flash argument: {raw_option!r}")
        used_groups.add(group)
        result.append({"option": option, "value": value})
    if used_groups != {"mode", "size", "freq"}:
        raise ValueError("write_flash_args must contain exactly mode, size, and freq")
    return result


def parse_extra_esptool_args(raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise ValueError("extra_esptool_args must be an object")
    normalized = {str(key).lstrip("-").replace("-", "_"): value for key, value in raw.items()}
    if set(normalized) != {"chip", "before", "after", "stub"}:
        raise ValueError("extra_esptool_args must contain only chip, before, after, and stub")
    if normalized["chip"] != CHIP or normalized["before"] not in SAFE_BEFORE or normalized["after"] not in SAFE_AFTER or not isinstance(normalized["stub"], bool):
        raise ValueError("extra_esptool_args contains unsafe ESP-IDF settings")
    return {"chip": CHIP, "before": normalized["before"], "after": normalized["after"], "stub": normalized["stub"]}


def package_esp_idf(project: Path, build_dir: Path, framework_version: str, output_dir: Path, profile: str) -> Path:
    source_project = relative_source_project(project)
    profile = board_profile(profile)
    validate_idf_profile(build_dir, profile)
    args_path = build_dir / "flasher_args.json"
    if not args_path.is_file():
        raise FileNotFoundError(f"ESP-IDF flasher arguments not found: {args_path}")
    payload = json.loads(args_path.read_text(encoding="utf-8"))
    flash_files = payload.get("flash_files")
    if not isinstance(flash_files, dict) or not flash_files:
        raise ValueError("flasher_args.json must contain a non-empty flash_files map")
    write_args = parse_write_flash_args(payload.get("write_flash_args"))
    extra_args = parse_extra_esptool_args(payload.get("extra_esptool_args"))

    used_offsets: set[int] = set()
    used_names: set[str] = set()
    records: list[dict[str, object]] = []
    sources: list[tuple[Path, str]] = []
    for raw_offset, raw_path in flash_files.items():
        if isinstance(raw_path, str) and "esp32c6" in raw_path.casefold():
            raise ValueError("ESP32-P4 CI packages cannot include an ESP32-C6 flash image")
        offset = parse_offset(raw_offset)
        if offset in used_offsets:
            raise ValueError("flasher_args.json contains duplicate flash offsets")
        source = contained_binary(build_dir, raw_path)
        if not source.is_file():
            raise FileNotFoundError(f"referenced ESP-IDF binary not found: {source}")
        size = source.stat().st_size
        if size <= 0 or offset + size > FLASH_LIMIT_BYTES:
            raise ValueError("flasher binary falls outside the 32 MiB flash boundary")
        used_offsets.add(offset)
        name = archive_name(source, used_names)
        records.append({"offset": f"0x{offset:x}", "offset_value": offset, "archive_path": name, "size": size, "sha256": sha256(source)})
        sources.append((source, name))
    validate_ranges(records)
    records.sort(key=lambda item: int(item["offset_value"]))
    for record in records:
        record.pop("offset_value")
    manifest = {
        "schema_version": 1,
        "board": BOARD,
        "chip": CHIP,
        "board_profile": profile,
        "chip_revision": {
            "minimum": BOARD_PROFILES[profile]["minimum"],
            "maximum_exclusive": BOARD_PROFILES[profile]["maximum_exclusive"],
        },
        "c6_firmware_included": False,
        "framework": "esp-idf",
        "framework_version": framework_version,
        "source_project": source_project,
        "git_sha": manifest_git_sha(),
        "flash": {"baud": DEFAULT_BAUD, "flash_limit_bytes": FLASH_LIMIT_BYTES, "extra_esptool_args": extra_args, "write_flash_args": write_args, "require_hash_verification": True},
        "files": records,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{artifact_name(source_project, framework_version, profile)}.zip"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source, name in sources:
            archive.write(source, name)
        archive.write(args_path, "metadata/flasher_args.json")
        archive.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--framework-version", required=True)
    parser.add_argument("--board-profile", choices=tuple(BOARD_PROFILES), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(package_esp_idf(args.project, args.build_dir, args.framework_version, args.output_dir, args.board_profile).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
