#!/usr/bin/env python3
"""Package one Arduino CI build of the Waveshare ESP32-P4-WIFI6-Touch-LCD-5.

Publishes only the real offset-addressed segments emitted by the retained
arduino-cli build metadata (flash_args). Merged/combined whole-flash images are
forbidden. The package carries full product/BSP/core provenance, a canonical
public build identity, and byte-exact POSIX/Windows/portable flash helpers.
ESP-IDF packaging continues to use releases/package_firmware.py (unchanged).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import shutil
import stat
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
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
BSP_SHA = "e2aff2b2f0d6d3ec93c4897690c64c635e603fca"  # BSP PR #192 head
BSP_COMPONENT_HASH = "23953dd701e61444eae3ac6130ced62f712feaa4"  # git tree sha1
BSP_COMPONENT_HASH_KIND = "git-tree-sha1"
HX8394_TREE = "baa47aabbaee6cb34677ba498f8855ea5d3dbf86"  # display/lcd/esp_lcd_hx8394
ARDUINO_FLASH_FLAGS = ("--flash-mode", "--flash-freq", "--flash-size")
ARDUINO_REQUIRED_ROLES = {"bootloader", "partition-table", "application"}
ARDUINO_SINGLETON_ROLES = ARDUINO_REQUIRED_ROLES | {"boot-app"}
ARDUINO_ALLOWED_ROLES = ARDUINO_SINGLETON_ROLES | {"toolchain-segment"}
FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
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
        raise ValueError("unable to verify trusted product repository: "
                         + (completed.stderr.strip() or "git failed"))
    return completed.stdout.strip()


def derive_current_repo_root() -> Path:
    script = Path(__file__).resolve(strict=True)
    root = Path(git_output(script.parent, "rev-parse", "--show-toplevel")).resolve(strict=True)
    if script.parent != root / "releases":
        raise ValueError("package_arduino_firmware.py must run from releases/ of the product repo")
    return root


CURRENT_REPO_ROOT = derive_current_repo_root()


def require_trusted_current_repo(expected_sha: str) -> Path:
    root = CURRENT_REPO_ROOT
    if Path(git_output(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise ValueError("trusted product repository is not its Git top-level")
    if git_output(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise ValueError("Arduino candidate packaging requires a clean trusted product Git tree")
    head = require_full_sha(git_output(root, "rev-parse", "HEAD"), "trusted product HEAD")
    if require_full_sha(expected_sha, "Arduino product SHA") != head:
        raise ValueError("Arduino product SHA does not match the trusted current repository HEAD")
    return root


def require_full_sha(value: str, label: str) -> str:
    if not FULL_SHA_RE.fullmatch(value or ""):
        raise ValueError(f"{label} must be a full 40-character hexadecimal SHA")
    return value.lower()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def parse_offset(value: str) -> int:
    try:
        offset = int(value, 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid flash offset: {value!r}") from exc
    if offset < 0:
        raise ValueError(f"flash offset must be non-negative: {value!r}")
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


def safe_build_file(build_dir: Path, value: str) -> tuple[Path, str]:
    if not value or "\\" in value or value.startswith("/"):
        raise ValueError(f"unsafe Arduino build path: {value!r}")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"unsafe Arduino build path: {value!r}")
    build_root = build_dir.resolve(strict=True)
    source = (build_root / Path(*parts)).resolve(strict=True)
    try:
        source.relative_to(build_root)
    except ValueError as exc:
        raise ValueError(f"Arduino build path escapes build directory: {value!r}") from exc
    if not source.is_file():
        raise FileNotFoundError(f"missing Arduino firmware file: {value}")
    return source, PurePosixPath(*parts).as_posix()


def reject_private_flash_source(value: str) -> None:
    parts = {part.lower() for part in value.replace("\\", "/").split("/")}
    private = {"home", "tmp", "users", "opt", "srv", "cache", "work", "workspace"}
    if HOST_PATH_RE.search(value) or PRIVATE_PATH_RE.search(value) or parts & private:
        raise ValueError(f"Arduino flash_args contains a private/cache/work path: {value!r}")


def arduino_role(source: str) -> str:
    lower = PurePosixPath(source).name.lower()
    if WHOLE_IMAGE_RE.search(lower):
        raise ValueError(f"Arduino whole-flash image is forbidden: {source}")
    if lower.endswith(".bootloader.bin"):
        return "bootloader"
    if lower.endswith(".partitions.bin"):
        return "partition-table"
    if lower == "boot_app0.bin" or lower.endswith(".boot_app0.bin"):
        return "boot-app"
    if lower.endswith(".ino.bin"):
        return "application"
    if lower.endswith(".bin"):
        return "toolchain-segment"
    raise ValueError(f"unsupported Arduino flash segment: {source}")


def parse_arduino_flash_args(path: Path) -> tuple[list[str], list[tuple[int, str]], int, str]:
    raw_text = path.read_text(encoding="utf-8")
    if HOST_PATH_RE.search(raw_text) or PRIVATE_PATH_RE.search(raw_text):
        raise ValueError(f"Arduino flash_args contains a host absolute path: {path}")
    try:
        tokens = shlex.split(raw_text, comments=False, posix=True)
    except ValueError as exc:
        raise ValueError(f"invalid Arduino flash_args syntax: {path}") from exc
    flags: list[str] = []
    values: dict[str, str] = {}
    cursor = 0
    while cursor < len(tokens) and tokens[cursor].startswith("--"):
        flag = tokens[cursor]
        if flag not in ARDUINO_FLASH_FLAGS or flag in values or cursor + 1 >= len(tokens):
            raise ValueError(f"missing/duplicate/unsupported Arduino flash flag: {flag!r}")
        value = tokens[cursor + 1]
        if value.startswith("-") or not re.fullmatch(r"[A-Za-z0-9.+_-]+", value):
            raise ValueError(f"unsafe Arduino flash flag value: {value!r}")
        values[flag] = value
        flags.extend([flag, value])
        cursor += 2
    if set(values) != set(ARDUINO_FLASH_FLAGS):
        raise ValueError("incomplete Arduino flash flags in flash_args")
    remainder = tokens[cursor:]
    if not remainder or len(remainder) % 2:
        raise ValueError("Arduino flash_args must contain offset/file pairs")
    pairs = [(parse_offset(remainder[i]), remainder[i + 1]) for i in range(0, len(remainder), 2)]
    flash_size_text = values["--flash-size"]
    return flags, pairs, parse_size(flash_size_text), flash_size_text


def trusted_project_path(project: str, repo: Path) -> tuple[Path, PurePosixPath]:
    if not project or "\\" in project or Path(project).is_absolute():
        raise ValueError("Arduino project must be a safe repo-relative path")
    parts = project.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Arduino project must be a safe repo-relative path")
    relative = PurePosixPath(*parts)
    root = repo.resolve(strict=True)
    resolved = (root / Path(*relative.parts)).resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Arduino project escapes the trusted product repository") from exc
    if not resolved.is_dir():
        raise ValueError(f"Arduino project is not a directory: {relative.as_posix()}")
    return resolved, relative


def quote_shell(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def quote_batch(value: str) -> str:
    return '"' + value.replace('"', '\\"') + '"'


def write_text(path: Path, content: str, executable: bool = False) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def slugify(value: str) -> str:
    value = value.strip().replace("\\", "/")
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value)
    return re.sub(r"-+", "-", value).strip("-") or "firmware"


def package(args: argparse.Namespace) -> Path:
    product_sha = require_full_sha(args.git_sha, "Arduino product SHA")
    repo = require_trusted_current_repo(product_sha)
    if args.framework_version != ARDUINO_CORE_VERSION:
        raise ValueError(f"Arduino framework version must exactly equal {ARDUINO_CORE_VERSION}")
    if args.target != ARDUINO_TARGET:
        raise ValueError(f"Arduino target must exactly equal {ARDUINO_TARGET}")
    requested_fqbn = getattr(args, "fqbn", None)
    if requested_fqbn is None or requested_fqbn != ARDUINO_FQBN:
        raise ValueError("requested Arduino FQBN must exactly equal the audited board FQBN")

    project, project_relative = trusted_project_path(args.project, repo)
    build_dir = Path(args.build_dir).resolve(strict=True)
    output_dir = Path(args.output_dir).resolve()

    flash_args_path, _ = safe_build_file(build_dir, "flash_args")
    options_path, _ = safe_build_file(build_dir, "build.options.json")
    try:
        build_options = json.loads(options_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid Arduino build metadata: {options_path}") from exc
    if not isinstance(build_options, dict) or not isinstance(build_options.get("fqbn"), str):
        raise ValueError("Arduino build metadata does not contain an FQBN")
    expanded_fqbn = build_options["fqbn"]
    if expanded_fqbn != ARDUINO_FQBN:
        raise ValueError(
            "expanded Arduino build FQBN must exactly equal the requested FQBN; "
            "additional board options may not be relabelled"
        )
    sketch_location = build_options.get("sketchLocation")
    if not isinstance(sketch_location, str) or not Path(sketch_location).is_absolute():
        raise ValueError("Arduino build.options.json is missing an absolute sketchLocation")
    if Path(sketch_location).resolve(strict=True) != project.resolve(strict=True):
        raise ValueError("Arduino build sketchLocation does not match the requested project")
    sketch_basename = f"{project.name}.ino"
    sketch_path = project / sketch_basename
    if not sketch_path.is_file():
        raise ValueError(f"Arduino project identity requires its canonical sketch {sketch_basename}")

    flash_flags, raw_pairs, flash_capacity, flash_size_text = parse_arduino_flash_args(flash_args_path)
    if flash_capacity != ARDUINO_FLASH_CAPACITY:
        raise ValueError(
            f"Arduino flash metadata capacity is {flash_capacity} bytes, expected {ARDUINO_FLASH_CAPACITY}"
        )

    selected: list[tuple[int, str, str, Path, int, str]] = []
    offsets: set[int] = set()
    roles: set[str] = set()
    for offset, source_value in raw_pairs:
        reject_private_flash_source(source_value)
        source_path, source = safe_build_file(build_dir, source_value)
        role = arduino_role(source)
        if offset in offsets:
            raise ValueError(f"duplicate Arduino flash offset: 0x{offset:x}")
        if role in ARDUINO_SINGLETON_ROLES and role in roles:
            raise ValueError(f"duplicate Arduino flash role: {role}")
        size = source_path.stat().st_size
        if size <= 0:
            raise ValueError(f"Arduino flash segment is empty: {source}")
        offsets.add(offset)
        roles.add(role)
        selected.append((offset, role, source, source_path, size, sha256_file(source_path)))
    if set(ARDUINO_REQUIRED_ROLES) - roles:
        raise ValueError("Arduino flash layout roles are incomplete")

    application = next(item for item in selected if item[1] == "application")
    if application[2] != f"{sketch_basename}.bin":
        raise ValueError(
            "Arduino application basename does not match the project sketch identity: "
            f"expected {sketch_basename}.bin, found {application[2]!r}"
        )

    ordered = sorted(selected, key=lambda item: item[0])
    cursor = 0
    for offset, role, source, _, size, _ in ordered:
        if offset == 0 and role != "bootloader":
            raise ValueError(f"only the Arduino bootloader may use offset 0x0: {source}")
        if offset < cursor:
            raise ValueError(f"Arduino flash regions overlap at 0x{offset:x}: {source}")
        if offset + size > flash_capacity:
            raise ValueError(f"Arduino flash segment exceeds flash capacity: {source}")
        cursor = offset + size

    artifact_name = slugify(
        f"{PRODUCT}-{project.name}-arduino-{ARDUINO_CORE_VERSION}"
    )
    if slugify(args.name or "") != artifact_name:
        raise ValueError(
            "Arduino artifact name must be derived from the canonical sketch identity: "
            f"expected {artifact_name!r}"
        )
    package_dir = output_dir / artifact_name
    firmware_dir = package_dir / "bin"
    metadata_dir = package_dir / "metadata"
    if package_dir.exists():
        shutil.rmtree(package_dir)
    firmware_dir.mkdir(parents=True)
    metadata_dir.mkdir(parents=True)

    files: list[dict[str, object]] = []
    command_pairs: list[str] = []
    for offset, role, source, source_path, size, digest in selected:
        offset_text = f"0x{offset:x}"
        packaged = firmware_dir / slugify(f"{offset_text}-{PurePosixPath(source).name}")
        if packaged.exists():
            raise ValueError(f"duplicate packaged firmware filename: {packaged.name}")
        shutil.copy2(source_path, packaged)
        files.append(
            {
                "offset": offset_text,
                "role": role,
                "file": f"bin/{packaged.name}",
                "source": source,
                "size": size,
                "sha256": digest,
            }
        )
        command_pairs.extend([offset_text, f"bin/{packaged.name}"])

    shutil.copy2(flash_args_path, metadata_dir / "flash_args")
    raw_flash_args = {
        "basename": "flash_args",
        "size": flash_args_path.stat().st_size,
        "sha256": sha256_file(flash_args_path),
    }
    raw_build_options = {
        "basename": "build.options.json",
        "size": options_path.stat().st_size,
        "sha256": sha256_file(options_path),
    }
    application_identity = {
        "basename": application[2],
        "size": application[4],
        "sha256": application[5],
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
        "path": project_relative.as_posix(),
        "directory_basename": project.name,
        "sketch_path": (project_relative / sketch_basename).as_posix(),
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
        "raw_build_options": raw_build_options,
        "raw_flash_args": raw_flash_args,
    }
    compile_identity = {"algorithm": "sha256", "sha256": canonical_sha256(compile_material)}
    identity = {
        "schema": 2,
        "fqbn": ARDUINO_FQBN,
        "target": ARDUINO_TARGET,
        "core": ARDUINO_CORE_VERSION,
        "bsp": bsp_identity,
        "product": {"git_sha": product_sha, "git_dirty": False},
        "project": project_identity,
        "application": application_identity,
        "compile_identity": compile_identity,
        "raw_build_options": raw_build_options,
        "raw_flash_args": raw_flash_args,
    }
    identity_path = metadata_dir / "build.options.identity.json"
    write_text(identity_path, json.dumps(identity, indent=2, sort_keys=True) + "\n")
    flash_args_metadata = {
        "role": "flash-args",
        "file": "metadata/flash_args",
        "source": "flash_args",
        "size": flash_args_path.stat().st_size,
        "sha256": sha256_file(flash_args_path),
    }
    identity_metadata = {
        "role": "build-options-identity",
        "file": "metadata/build.options.identity.json",
        "source": "build.options.json",
        "size": identity_path.stat().st_size,
        "sha256": sha256_file(identity_path),
        "raw": raw_build_options,
    }

    command = (
        ["python", "-m", "esptool", "--chip", ARDUINO_TARGET, "--port", "$PORT",
         "--before", "default_reset", "--after", "hard_reset", "write_flash"]
        + flash_flags
        + command_pairs
    )
    shell_command = " ".join('"$PORT"' if part == "$PORT" else quote_shell(part) for part in command)
    batch_command = " ".join('"%PORT%"' if part == "$PORT" else quote_batch(part) for part in command)
    portable_command = " ".join("<PORT>" if part == "$PORT" else part for part in command)
    write_text(package_dir / "flash.sh", f"""#!/usr/bin/env sh
set -eu
PORT="${{1:-}}"
if [ -z "$PORT" ]; then
    echo "Usage: $0 PORT"
    exit 2
fi
cd "$(dirname "$0")"
{shell_command}
""", executable=True)
    write_text(package_dir / "flash.bat", f"""@echo off
set "PORT=%~1"
if "%PORT%"=="" (
  echo Usage: %~nx0 COMx
  exit /b 2
)
cd /d %~dp0
{batch_command}
""")
    write_text(package_dir / "flash_args.txt", portable_command + "\n")
    write_text(package_dir / "README.md", f"""# {artifact_name}

This Arduino package contains only the offset-addressed images emitted by the
real arduino-cli build metadata. It intentionally contains no merged, combined,
or whole-flash image.

Install esptool if needed:

```bash
python -m pip install esptool
```

Flash all segments from this directory:

```bash
./flash.sh PORT
```

On Windows:

```bat
flash.bat COMx
```

The exact metadata-derived command is recorded in `flash_args.txt`. Do not mix
segments from different packages.
""")

    segmented_payload_total = sum(int(entry["size"]) for entry in files)
    manifest = {
        "schema_version": 3,
        "name": artifact_name,
        "framework": "arduino",
        "framework_version": ARDUINO_CORE_VERSION,
        "target": ARDUINO_TARGET,
        "fqbn": ARDUINO_FQBN,
        "project": project_identity["path"],
        "application": application_identity,
        "compile_identity": compile_identity,
        "git_sha": product_sha,
        "product_sha": product_sha,
        "git_dirty": False,
        "bsp": bsp_identity,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baud": None,
        "flash_flags": flash_flags,
        "flash_size": flash_size_text,
        "flash_capacity_bytes": flash_capacity,
        "segmented_payload_total": segmented_payload_total,
        "files": files,
        "flash_command": portable_command,
        "build_metadata": [flash_args_metadata, identity_metadata],
    }
    write_text(package_dir / "manifest.json", json.dumps(manifest, indent=2) + "\n")

    zip_name = f"{artifact_name}-segments.zip"
    zip_path = output_dir / zip_name
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(package_dir.rglob("*"), key=lambda item: item.as_posix()):
            if path.is_file():
                archive.write(path, path.relative_to(package_dir.parent).as_posix())
    return zip_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--output-dir", default="release-artifacts")
    parser.add_argument("--name", required=True)
    parser.add_argument("--framework-version", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--fqbn", required=True)
    parser.add_argument("--git-sha", required=True)
    args = parser.parse_args()
    try:
        zip_path = package(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(zip_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
