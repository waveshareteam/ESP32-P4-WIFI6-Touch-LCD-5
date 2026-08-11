#!/usr/bin/env python3
"""Package one ESP-IDF CI build as a verified ESP32-P4 flash bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
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
SAFE_BEFORE = {"default_reset", "no_reset"}
SAFE_AFTER = {"hard_reset", "soft_reset", "no_reset"}


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


def write_text(archive: zipfile.ZipFile, name: str, text: str, executable: bool = False) -> None:
    info = zipfile.ZipInfo(name)
    info.external_attr = (0o755 if executable else 0o644) << 16
    archive.writestr(info, text.encode("utf-8"))


def make_scripts(files: list[dict[str, object]], extra: dict[str, object], write_args: list[dict[str, str]]) -> tuple[str, str, str]:
    pairs = [(str(item["offset"]), str(item["archive_path"])) for item in files]
    global_args = ["--chip", CHIP, "--baud", str(DEFAULT_BAUD), "--before", str(extra["before"]), "--after", str(extra["after"])]
    if not bool(extra["stub"]):
        global_args.append("--no-stub")
    write_tokens = [token for item in write_args for token in (item["option"], item["value"])]
    display = "python -m esptool --port PORT " + " ".join(global_args) + " write_flash " + " ".join(write_tokens) + " " + " ".join(
        f"{offset} {shlex.quote(path)}" for offset, path in pairs
    )
    shell_pairs = " ".join(f'{offset} "$SCRIPT_DIR/{path}"' for offset, path in pairs)
    batch_pairs = " ".join(f'{offset} "%~dp0{path.replace("/", chr(92))}"' for offset, path in pairs)
    shell = "#!/usr/bin/env sh\nset -eu\nif [ \"$#\" -ne 1 ]; then echo \"Usage: $0 PORT\" >&2; exit 2; fi\nPORT=$1\nSCRIPT_DIR=$(CDPATH= cd -- \"$(dirname -- \"$0\")\" && pwd)\n" + "python -m esptool --port \"$PORT\" " + " ".join(global_args) + " write_flash " + " ".join(write_tokens) + f" {shell_pairs}\n"
    batch = "@echo off\r\nif \"%~1\"==\"\" (echo Usage: %~nx0 COMx & exit /b 2)\r\necho %~1| findstr /r /i /x \"COM[0-9][0-9]*\" >nul || (echo Usage: %~nx0 COMx & exit /b 2)\r\nset \"PORT=%~1\"\r\n" + "python -m esptool --port \"%PORT%\" " + " ".join(global_args) + " write_flash " + " ".join(write_tokens) + f" {batch_pairs}\r\nif errorlevel 1 exit /b %errorlevel%\r\n"
    return display, shell, batch


def package_esp_idf(project: Path, build_dir: Path, framework_version: str, output_dir: Path) -> Path:
    source_project = relative_source_project(project)
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
    display, shell, batch = make_scripts(records, extra_args, write_args)
    for record in records:
        record.pop("offset_value")
    manifest = {
        "schema_version": 1,
        "board": BOARD,
        "chip": CHIP,
        "framework": "esp-idf",
        "framework_version": framework_version,
        "source_project": source_project,
        "git_sha": manifest_git_sha(),
        "flash": {"baud": DEFAULT_BAUD, "flash_limit_bytes": FLASH_LIMIT_BYTES, "extra_esptool_args": extra_args, "write_flash_args": write_args, "command": display, "require_hash_verification": True},
        "files": records,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"firmware-{slugify(source_project.split('/')[-1])}-{slugify(framework_version)}.zip"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source, name in sources:
            archive.write(source, name)
        archive.write(args_path, "metadata/flasher_args.json")
        write_text(archive, "manifest.json", json.dumps(manifest, indent=2) + "\n")
        write_text(archive, "flash.sh", shell, executable=True)
        write_text(archive, "flash.bat", batch)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--framework-version", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(package_esp_idf(args.project, args.build_dir, args.framework_version, args.output_dir).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
