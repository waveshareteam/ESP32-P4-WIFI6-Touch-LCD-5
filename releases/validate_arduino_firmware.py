#!/usr/bin/env python3
"""Independently validate one Arduino segmented archive for the LCD-5 board.

The archive and its manifest are untrusted. This validator rebuilds the release
contract from the clean Git checkout containing this script and the retained
arduino-cli build path, then compares every public byte that carries flashing
or build identity information. It accepts no caller-selected repository root.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import stat
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

PRODUCT = "ESP32-P4-WIFI6-Touch-LCD-5"
ARDUINO_CORE_VERSION = "3.3.11"
ARDUINO_TARGET = "esp32p4"
ARDUINO_FQBN = (
    "esp32:esp32:esp32p4:ChipVariant=prev3,PSRAM=enabled,FlashSize=32M,"
    "FlashMode=qio,FlashFreq=80,PartitionScheme=app13M_data7M_32MB,"
    "UploadMode=default,UploadSpeed=921600"
)
ARDUINO_FLASH_CAPACITY = 32 * 1024 * 1024
BSP_REPOSITORY = "waveshareteam/Waveshare-ESP32-components"
BSP_COMPONENT = "bsp/esp32_p4_wifi6_touch_lcd_5"
BSP_VERSION = "1.0.1"
BSP_SHA = "e2aff2b2f0d6d3ec93c4897690c64c635e603fca"
BSP_COMPONENT_HASH = "23953dd701e61444eae3ac6130ced62f712feaa4"
BSP_COMPONENT_HASH_KIND = "git-tree-sha1"
HX8394_TREE = "baa47aabbaee6cb34677ba498f8855ea5d3dbf86"
ARDUINO_FLASH_FLAGS = ("--flash-mode", "--flash-freq", "--flash-size")
FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
WHOLE_IMAGE_RE = re.compile(
    r"(?:^|[._-])(merged|combined|whole[-_]?flash|full[-_]?flash)(?:[._-]|$)", re.I
)
HOST_PATH_RE = re.compile(
    r"(?:^|[\s='\"(])/(?![./])(?:[A-Za-z0-9._~+@-]+(?:/[A-Za-z0-9._~+@-]+)*)|"
    r"(?:^|[^A-Za-z0-9])[A-Za-z]:[\\/]|\bfile:(?://)?[\\/]|"
    r"(?:^|[\s='\"])[\\/]{2}[A-Za-z0-9._~-]+[\\/]",
    re.I,
)
PRIVATE_PATH_RE = re.compile(
    r"(?:^|[^A-Za-z0-9])/(?:home|tmp|private/tmp|var/tmp|opt|srv)/", re.I
)


def git_output(repo: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=False, capture_output=True, text=True,
    )
    if completed.returncode != 0:
        raise ValueError("unable to verify trusted product repository")
    return completed.stdout.strip()


def git_output_bytes(repo: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=False, capture_output=True, text=False,
    )
    if completed.returncode != 0:
        raise ValueError("unable to verify trusted product repository")
    return completed.stdout


def derive_current_repo_root() -> Path:
    script = Path(__file__).resolve(strict=True)
    root = Path(git_output(script.parent, "rev-parse", "--show-toplevel")).resolve(strict=True)
    if script.parent != root / "releases":
        raise ValueError("validate_arduino_firmware.py must run from releases/ of the product repo")
    return root


CURRENT_REPO_ROOT = derive_current_repo_root()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def require_full_sha(value: str, label: str) -> str:
    if not FULL_SHA_RE.fullmatch(value or ""):
        raise ValueError(f"{label} must be a full 40-character hexadecimal SHA")
    return value.lower()


def parse_offset(value: str) -> int:
    try:
        offset = int(value, 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid flash offset: {value!r}") from exc
    return offset


def parse_size(value: str) -> int:
    match = re.fullmatch(r"([1-9][0-9]*)(K|KB|M|MB)?", value.strip(), re.I)
    if not match:
        raise ValueError(f"invalid flash size: {value!r}")
    size = int(match.group(1))
    unit = (match.group(2) or "").upper()
    if unit in {"K", "KB"}:
        size *= 1024
    elif unit in {"M", "MB"}:
        size *= 1024 * 1024
    return size


def ensure_public(data: bytes, label: str) -> None:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"public archive member is not UTF-8: {label}") from exc
    if label.endswith("flash.bat"):
        # strip built-in batch scaffolding before scanning
        text = text.replace("cd /d %~dp0\n", "").replace("  exit /b 2\n", "")
    if HOST_PATH_RE.search(text) or PRIVATE_PATH_RE.search(text):
        raise ValueError(f"private host path found in public archive member {label}")


def safe_relative(value: str, label: str) -> PurePosixPath:
    if not value or "\\" in value or value.startswith("/"):
        raise ValueError(f"unsafe {label}: {value!r}")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"unsafe {label}: {value!r}")
    return PurePosixPath(*parts)


def parse_real_flash_args(build_dir: Path, data: bytes) -> tuple[list[str], list[tuple[int, str, str, int, str]], int, str]:
    ensure_public(data, "real build-path flash_args")
    text = data.decode("utf-8")
    tokens = shlex.split(text, comments=False, posix=True)
    flags: list[str] = []
    values: dict[str, str] = {}
    cursor = 0
    while cursor < len(tokens) and tokens[cursor].startswith("--"):
        flag = tokens[cursor]
        if flag not in ARDUINO_FLASH_FLAGS or flag in values or cursor + 1 >= len(tokens):
            raise ValueError(f"invalid Arduino flash flag: {flag!r}")
        value = tokens[cursor + 1]
        if value.startswith("-") or not re.fullmatch(r"[A-Za-z0-9.+_-]+", value):
            raise ValueError(f"unsafe Arduino flash flag value: {value!r}")
        values[flag] = value
        flags.extend([flag, value])
        cursor += 2
    if set(values) != set(ARDUINO_FLASH_FLAGS):
        raise ValueError("incomplete Arduino flash flags")
    remainder = tokens[cursor:]
    if not remainder or len(remainder) % 2:
        raise ValueError("Arduino flash_args has incomplete offset/file pairs")
    build_root = build_dir.resolve(strict=True)
    segments: list[tuple[int, str, str, int, str]] = []
    for index in range(0, len(remainder), 2):
        offset = parse_offset(remainder[index])
        raw = remainder[index + 1]
        if raw.startswith("/") or "\\" in raw or ".." in raw.split("/"):
            raise ValueError(f"unsafe Arduino flash_args source: {raw!r}")
        source = (build_root / Path(*raw.split("/"))).resolve(strict=True)
        try:
            source.relative_to(build_root)
        except ValueError as exc:
            raise ValueError(f"Arduino segment escapes build directory: {raw!r}") from exc
        if not source.is_file():
            raise FileNotFoundError(f"missing Arduino segment: {raw}")
        segments.append((offset, raw, source.name, source.stat().st_size, sha256_file(source)))
    flash_size_text = values["--flash-size"]
    return flags, segments, parse_size(flash_size_text), flash_size_text


def slugify(value: str) -> str:
    value = value.strip().replace("\\", "/")
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value)
    return re.sub(r"-+", "-", value).strip("-") or "firmware"


def quote_shell(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def quote_batch(value: str) -> str:
    return '"' + value.replace('"', '\\"') + '"'


def expected_helpers(artifact_name: str, command: list[str]) -> dict[str, bytes]:
    shell_command = " ".join('"$PORT"' if part == "$PORT" else quote_shell(part) for part in command)
    batch_command = " ".join('"%PORT%"' if part == "$PORT" else quote_batch(part) for part in command)
    portable = " ".join("<PORT>" if part == "$PORT" else part for part in command)
    return {
        "flash.sh": f"""#!/usr/bin/env sh
set -eu
PORT="${{1:-}}"
if [ -z "$PORT" ]; then
    echo "Usage: $0 PORT"
    exit 2
fi
cd "$(dirname "$0")"
{shell_command}
""".encode(),
        "flash.bat": f"""@echo off
set "PORT=%~1"
if "%PORT%"=="" (
  echo Usage: %~nx0 COMx
  exit /b 2
)
cd /d %~dp0
{batch_command}
""".encode(),
        "flash_args.txt": (portable + "\n").encode(),
    }


def validate_archive(args: argparse.Namespace) -> dict[str, object]:
    if hasattr(args, "repo") or hasattr(args, "repo_root"):
        raise ValueError("the validator trusts only its own checkout; caller repo selection is forbidden")
    repo = CURRENT_REPO_ROOT
    if Path(git_output(repo, "rev-parse", "--show-toplevel")).resolve() != repo:
        raise ValueError("validator Git top-level changed after trusted-root discovery")
    if git_output(repo, "status", "--porcelain=v1", "--untracked-files=all"):
        raise ValueError("product checkout is not clean; its firmware cannot be bound to HEAD")

    product_sha = require_full_sha(args.git_sha, "product Git SHA")
    if git_output(repo, "rev-parse", "HEAD") != product_sha:
        raise ValueError("product Git SHA does not match checkout HEAD")
    if args.framework_version != ARDUINO_CORE_VERSION:
        raise ValueError("--framework-version does not match the audited Arduino core")
    if args.target != ARDUINO_TARGET:
        raise ValueError("--target does not match the audited board target")
    if args.fqbn != ARDUINO_FQBN:
        raise ValueError("--fqbn does not match the audited board FQBN")

    archive_path = Path(args.archive).resolve()
    if not archive_path.is_file() or archive_path.is_symlink():
        raise ValueError("--archive must be a regular ZIP file")
    build_dir = Path(args.build_dir).resolve()
    if not build_dir.is_dir() or build_dir.is_symlink():
        raise ValueError("--build-dir must be a retained Arduino CLI build directory")

    project_value = args.project
    project = (repo / Path(*safe_relative(project_value, "project").parts)).resolve(strict=True)
    if not project.is_dir():
        raise ValueError("Arduino project must be a real directory")
    sketch_basename = f"{project.name}.ino"
    sketch_path = project / sketch_basename
    if not sketch_path.is_file():
        raise ValueError("Arduino project has no canonical primary sketch")
    head_sketch = git_output_bytes(
        repo, "show", f"{product_sha}:{(PurePosixPath(project_value) / sketch_basename).as_posix()}"
    )
    if head_sketch != sketch_path.read_bytes():
        raise ValueError("primary sketch bytes do not match the declared product Git SHA")

    artifact_name = slugify(f"{PRODUCT}-{project.name}-arduino-{ARDUINO_CORE_VERSION}")
    if slugify(args.name) != artifact_name:
        raise ValueError(f"artifact name does not match project identity: {artifact_name}")
    if archive_path.name != f"{artifact_name}-segments.zip":
        raise ValueError("Arduino ZIP filename does not match its externally anchored identity")

    options_path = build_dir / "build.options.json"
    flash_args_path = build_dir / "flash_args"
    if not options_path.is_file() or not flash_args_path.is_file():
        raise FileNotFoundError("retained build path is missing build.options.json or flash_args")
    raw_options = options_path.read_bytes()
    raw_flash_args = flash_args_path.read_bytes()
    try:
        build_options = json.loads(raw_options.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid real build.options.json") from exc
    if build_options.get("fqbn") != ARDUINO_FQBN:
        raise ValueError("real build.options FQBN does not match the audited FQBN")
    sketch_location = build_options.get("sketchLocation")
    if not isinstance(sketch_location, str) or Path(sketch_location).resolve(strict=True) != project:
        raise ValueError("real build.options sketchLocation does not resolve to the trusted project")

    flags, real_segments, flash_capacity, flash_size_text = parse_real_flash_args(build_dir, raw_flash_args)
    if flash_capacity != ARDUINO_FLASH_CAPACITY:
        raise ValueError("real flash capacity does not match the audited board capacity")

    role_of = []
    expected_entries: list[dict[str, object]] = []
    command_pairs: list[str] = []
    seen_offsets: set[int] = set()
    seen_roles: set[str] = set()
    for offset, raw, basename, size, digest in real_segments:
        lower = basename.lower()
        if WHOLE_IMAGE_RE.search(lower):
            raise ValueError(f"whole-flash image in real build path: {raw}")
        if lower.endswith(".bootloader.bin"):
            role = "bootloader"
        elif lower.endswith(".partitions.bin"):
            role = "partition-table"
        elif lower == "boot_app0.bin" or lower.endswith(".boot_app0.bin"):
            role = "boot-app"
        elif lower.endswith(".ino.bin"):
            role = "application"
        elif lower.endswith(".bin"):
            role = "toolchain-segment"
        else:
            raise ValueError(f"unsupported real Arduino segment: {raw}")
        if offset in seen_offsets:
            raise ValueError(f"duplicate real Arduino offset: 0x{offset:x}")
        if role in {"bootloader", "partition-table", "application", "boot-app"} and role in seen_roles:
            raise ValueError(f"duplicate real Arduino role: {role}")
        seen_offsets.add(offset)
        seen_roles.add(role)
        role_of.append(role)
        offset_text = f"0x{offset:x}"
        packaged = f"bin/{slugify(f'{offset_text}-{basename}')}"
        expected_entries.append(
            {"offset": offset_text, "role": role, "file": packaged, "source": raw,
             "size": size, "sha256": digest}
        )
        command_pairs.extend([offset_text, packaged])
    if not ({"bootloader", "partition-table", "application"} <= seen_roles):
        raise ValueError("real flash metadata roles are incomplete")

    application_basename = next(
        e["source"] for e, r in zip(expected_entries, role_of) if r == "application"
    )
    if application_basename != f"{sketch_basename}.bin":
        raise ValueError("real application basename does not match the trusted sketch identity")

    raw_flash_identity = {"basename": "flash_args", "size": len(raw_flash_args), "sha256": sha256_bytes(raw_flash_args)}
    raw_options_identity = {"basename": "build.options.json", "size": len(raw_options), "sha256": sha256_bytes(raw_options)}
    application_identity = {
        "basename": application_basename,
        "size": next(e["size"] for e, r in zip(expected_entries, role_of) if r == "application"),
        "sha256": next(e["sha256"] for e, r in zip(expected_entries, role_of) if r == "application"),
    }
    bsp_identity = {
        "repository": BSP_REPOSITORY,
        "component": BSP_COMPONENT,
        "version": BSP_VERSION,
        "sha": BSP_SHA,
        "component_hash": BSP_COMPONENT_HASH,
        "component_hash_kind": BSP_COMPONENT_HASH_KIND,
        "display_driver_tree": HX8394_TREE,
        "linked": False,
    }
    project_identity = {
        "path": project_value,
        "directory_basename": project.name,
        "sketch_path": f"{project_value}/{sketch_basename}",
        "sketch_basename": sketch_basename,
        "sketch_size": sketch_path.stat().st_size,
        "sketch_sha256": sha256_file(sketch_path),
    }
    compile_material = {
        "core": ARDUINO_CORE_VERSION,
        "fqbn": ARDUINO_FQBN,
        "target": ARDUINO_TARGET,
        "product_sha": product_sha,
        "project": project_identity,
        "application": application_identity,
        "raw_build_options": raw_options_identity,
        "raw_flash_args": raw_flash_identity,
    }
    compile_identity = {"algorithm": "sha256", "sha256": canonical_sha256(compile_material)}
    canonical_identity = {
        "schema": 2,
        "fqbn": ARDUINO_FQBN,
        "target": ARDUINO_TARGET,
        "core": ARDUINO_CORE_VERSION,
        "bsp": bsp_identity,
        "product": {"git_sha": product_sha, "git_dirty": False},
        "project": project_identity,
        "application": application_identity,
        "compile_identity": compile_identity,
        "raw_build_options": raw_options_identity,
        "raw_flash_args": raw_flash_identity,
    }
    command = (
        ["python", "-m", "esptool", "--chip", ARDUINO_TARGET, "--port", "$PORT",
         "--before", "default_reset", "--after", "hard_reset", "write_flash"]
        + flags + command_pairs
    )
    portable_command = " ".join("<PORT>" if part == "$PORT" else part for part in command)
    helpers = expected_helpers(artifact_name, command)

    with zipfile.ZipFile(archive_path) as archive:
        members: dict[str, zipfile.ZipInfo] = {}
        for info in archive.infolist():
            safe_relative(info.filename, "ZIP member")
            mode = info.external_attr >> 16
            if mode and stat.S_ISLNK(mode):
                raise ValueError(f"symbolic-link ZIP member is forbidden: {info.filename}")
            if info.is_dir():
                continue
            if info.filename in members:
                raise ValueError(f"duplicate ZIP member: {info.filename}")
            members[info.filename] = info
        root = PurePosixPath(artifact_name)
        manifest_name = (root / "manifest.json").as_posix()
        if manifest_name not in members:
            raise ValueError("missing firmware member manifest.json")
        manifest_bytes = archive.read(manifest_name)
        ensure_public(manifest_bytes, "manifest.json")
        try:
            manifest = json.loads(manifest_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid manifest JSON") from exc

        if manifest.get("schema_version") != 3:
            raise ValueError("unsupported Arduino manifest schema")
        expected_scalars = {
            "name": artifact_name, "framework": "arduino",
            "framework_version": ARDUINO_CORE_VERSION, "target": ARDUINO_TARGET,
            "fqbn": ARDUINO_FQBN, "project": project_value,
            "git_sha": product_sha, "product_sha": product_sha,
            "git_dirty": False, "flash_size": flash_size_text,
            "flash_capacity_bytes": flash_capacity,
        }
        for field, expected in expected_scalars.items():
            if manifest.get(field) != expected:
                raise ValueError(f"Arduino manifest {field} does not match external evidence")
        if manifest.get("bsp") != bsp_identity:
            raise ValueError("Arduino manifest BSP identity does not match external evidence")
        if manifest.get("application") != application_identity:
            raise ValueError("Arduino manifest application identity does not match real build evidence")
        if manifest.get("compile_identity") != compile_identity:
            raise ValueError("Arduino manifest compile identity does not match real build evidence")
        if manifest.get("flash_flags") != flags:
            raise ValueError("Arduino manifest flash options do not match real flash_args")
        if manifest.get("segmented_payload_total") != sum(e["size"] for e in expected_entries):
            raise ValueError("Arduino manifest segmented_payload_total is not the exact segment sum")
        if manifest.get("flash_command") != portable_command:
            raise ValueError("Arduino manifest portable command does not match real build evidence")
        if manifest.get("files") != expected_entries:
            raise ValueError("Arduino manifest files do not exactly match real flash_args")

        metadata = manifest.get("build_metadata")
        if not isinstance(metadata, list) or len(metadata) != 2:
            raise ValueError("Arduino manifest build_metadata shape is invalid")
        flash_record = next((m for m in metadata if m.get("role") == "flash-args"), None)
        identity_record = next((m for m in metadata if m.get("role") == "build-options-identity"), None)
        if flash_record is None or identity_record is None:
            raise ValueError("Arduino manifest build_metadata roles are missing")
        packaged_flash_name = (root / "metadata/flash_args").as_posix()
        if packaged_flash_name not in members:
            raise ValueError("missing firmware member metadata/flash_args")
        packaged_flash = archive.read(packaged_flash_name)
        if packaged_flash != raw_flash_args:
            raise ValueError("packaged flash_args is not byte-identical to the real build metadata")
        if flash_record.get("size") != len(packaged_flash) or flash_record.get("sha256") != sha256_bytes(packaged_flash):
            raise ValueError("manifest flash_args evidence does not match the retained build path")

        identity_name = (root / "metadata/build.options.identity.json").as_posix()
        if identity_name not in members:
            raise ValueError("missing firmware member metadata/build.options.identity.json")
        identity_bytes = archive.read(identity_name)
        ensure_public(identity_bytes, "build.options.identity.json")
        try:
            identity = json.loads(identity_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid canonical identity JSON") from exc
        if identity != canonical_identity:
            raise ValueError("canonical public build identity does not match raw external evidence")
        if identity_record.get("size") != len(identity_bytes) or identity_record.get("sha256") != sha256_bytes(identity_bytes):
            raise ValueError("canonical identity size/SHA evidence is incorrect")
        if identity_record.get("raw") != raw_options_identity:
            raise ValueError("manifest/raw build.options identity mismatch")

        for entry in expected_entries:
            member = (root / str(entry["file"])).as_posix()
            if member not in members:
                raise ValueError(f"missing firmware member {entry['file']}")
            data = archive.read(member)
            if len(data) != entry["size"] or sha256_bytes(data) != entry["sha256"]:
                raise ValueError(f"firmware checksum mismatch for {entry['file']}")
            source_file = build_dir / str(entry["source"])
            if data != source_file.read_bytes():
                raise ValueError(f"packaged segment differs from real build output: {entry['source']}")

        for helper, expected_bytes in helpers.items():
            member = (root / helper).as_posix()
            if member not in members:
                raise ValueError(f"missing firmware member {helper}")
            if archive.read(member) != expected_bytes:
                raise ValueError(f"{helper} does not exactly encode every real option and segment")
        shell_mode = members[(root / "flash.sh").as_posix()].external_attr >> 16
        if not shell_mode & 0o111:
            raise ValueError("flash.sh is not executable")

        expected_members = {
            manifest_name,
            (root / "metadata/flash_args").as_posix(),
            (root / "metadata/build.options.identity.json").as_posix(),
            (root / "flash_args.txt").as_posix(),
            (root / "flash.sh").as_posix(),
            (root / "flash.bat").as_posix(),
            (root / "README.md").as_posix(),
            *((root / str(e["file"])).as_posix() for e in expected_entries),
        }
        if set(members) != expected_members:
            missing = sorted(expected_members - set(members))
            extra = sorted(set(members) - expected_members)
            raise ValueError(f"Arduino ZIP strict member set mismatch; missing={missing}, extra={extra}")
        for member_name in members:
            lowered = PurePosixPath(member_name).name.lower()
            if lowered == "build.options.json" or lowered.endswith(".merged.bin") or lowered.endswith("-combined.bin"):
                raise ValueError(f"forbidden raw/whole-flash member: {member_name}")
            if PurePosixPath(member_name).suffix.lower() != ".bin":
                ensure_public(archive.read(members[member_name]), member_name)

    return {
        "archive": archive_path.name,
        "name": artifact_name,
        "product_git_sha": product_sha,
        "project": project_value,
        "target": ARDUINO_TARGET,
        "fqbn": ARDUINO_FQBN,
        "framework_version": ARDUINO_CORE_VERSION,
        "bsp": bsp_identity,
        "segment_count": len(expected_entries),
        "segmented_payload_total": sum(e["size"] for e in expected_entries),
        "flash_size": flash_capacity,
        "flash_command": portable_command,
        "validation": "external-build-evidence-reconstructed",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--framework-version", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--fqbn", required=True)
    parser.add_argument("--git-sha", required=True)
    args = parser.parse_args()
    try:
        summary = validate_archive(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
