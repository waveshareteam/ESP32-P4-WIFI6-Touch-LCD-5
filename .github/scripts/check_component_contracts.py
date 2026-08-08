#!/usr/bin/env python3
"""Static compatibility contracts that are easy for default builds to miss."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path


BROOKESIA_ROOT = Path(
    "examples/esp-idf/11_esp_brookesia_phone/components/brookesia_core"
)
BROOKESIA_SPEAKER_MANIFEST = BROOKESIA_ROOT / "systems/speaker/idf_component.yml"
WIFI_MANIFEST = Path("examples/esp-idf/04_wifistation/main/idf_component.yml")
MP4_AUDIO_MANIFEST = Path("examples/esp-idf/10_mp4_player/main/idf_component.yml")
HX8394_GLOB = "examples/esp-idf/*/components/esp_lcd_hx8394"
HX8394_SHARED_FILES = (
    "esp_lcd_hx8394.c",
    "include/esp_lcd_hx8394.h",
    "idf_component.yml",
    "license.txt",
    "README.md",
)


@dataclass(frozen=True, order=True)
class Finding:
    path: str
    code: str
    message: str


def read(repo: Path, relative: Path) -> str:
    path = repo / relative
    if not path.is_file():
        raise OSError(f"required compatibility file is missing: {relative.as_posix()}")
    return path.read_text(encoding="utf-8")


def check_brookesia(repo: Path) -> list[Finding]:
    findings: list[Finding] = []
    kconfig_path = BROOKESIA_ROOT / "Kconfig"
    manifest_path = BROOKESIA_ROOT / "idf_component.yml"
    kconfig = read(repo, kconfig_path)
    manifest = read(repo, manifest_path)

    symbol = re.search(
        r"(?ms)^\s*config ESP_BROOKESIA_ENABLE_AI_FRAMEWORK\s*$"
        r"(.*?)(?=^\s*(?:config|menuconfig) [A-Z0-9_]+\s*$)",
        kconfig,
    )
    if not symbol:
        findings.append(
            Finding(
                kconfig_path.as_posix(),
                "BROOKESIA_AI_SYMBOL_MISSING",
                "keep the disabled compatibility symbol explicit",
            )
        )
    else:
        block = symbol.group(1)
        if not re.search(r"(?m)^\s+bool\s*$", block):
            findings.append(
                Finding(
                    kconfig_path.as_posix(),
                    "BROOKESIA_AI_OPTION_EXPOSED",
                    "legacy AI support must remain hidden while its dependencies are omitted",
                )
            )
        if not re.search(r"(?m)^\s+default n\s*$", block):
            findings.append(
                Finding(
                    kconfig_path.as_posix(),
                    "BROOKESIA_AI_DEFAULT_ENABLED",
                    "legacy AI support must remain disabled",
                )
            )
    if 'rsource "ai_framework/Kconfig"' in kconfig:
        findings.append(
            Finding(
                kconfig_path.as_posix(),
                "BROOKESIA_AI_KCONFIG_REACHABLE",
                "legacy AI sub-options must not be reachable without the dependency stack",
            )
        )

    boost_contract = (
        'if: "idf_version >= 6.0"',
        'version: "0.6.0"',
        'if: "idf_version < 6.0"',
        'version: "0.3.*"',
    )
    for boost_manifest_path in (manifest_path, BROOKESIA_SPEAKER_MANIFEST):
        boost_manifest = read(repo, boost_manifest_path)
        boost = re.search(
            r"(?ms)^  espressif/esp-boost:\s*$"
            r"(.*?)(?=^  [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+:\s*$|"
            r"^  #[^\n]*$|\Z)",
            boost_manifest,
        )
        if not boost or any(marker not in boost.group(1) for marker in boost_contract):
            findings.append(
                Finding(
                    boost_manifest_path.as_posix(),
                    "BROOKESIA_BOOST_RANGE",
                    "require esp-boost 0.3.* on IDF 5 and exact 0.6.0 on IDF 6",
                )
            )

    omitted_ai_dependencies = (
        "esp_coze",
        "gmf_core",
        "gmf_ai_audio",
        "gmf_io",
        "gmf_misc",
        "gmf_audio",
        "esp_audio_simple_player",
        "esp_websocket_client",
    )
    for dependency in omitted_ai_dependencies:
        if re.search(rf"(?m)^\s+espressif/{re.escape(dependency)}:\s*$", manifest):
            findings.append(
                Finding(
                    manifest_path.as_posix(),
                    "BROOKESIA_AI_DEPENDENCY_WITH_DISABLED_FEATURE",
                    f"unexpected disabled AI dependency espressif/{dependency}",
                )
            )
    return findings


def component_digest(root: Path) -> tuple[str, dict[str, str]]:
    file_digests: dict[str, str] = {}
    aggregate = hashlib.sha256()
    for relative in HX8394_SHARED_FILES:
        path = root / relative
        if not path.is_file():
            digest = "<missing>"
        else:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        file_digests[relative] = digest
        aggregate.update(relative.encode("utf-8"))
        aggregate.update(b"\0")
        aggregate.update(digest.encode("ascii"))
        aggregate.update(b"\0")
    return aggregate.hexdigest(), file_digests


def check_hx8394(repo: Path) -> list[Finding]:
    findings: list[Finding] = []
    components = sorted(path for path in repo.glob(HX8394_GLOB) if path.is_dir())
    if len(components) != 6:
        findings.append(
            Finding(
                "examples/esp-idf",
                "HX8394_COPY_COUNT",
                f"expected six example-local HX8394 integrations, found {len(components)}",
            )
        )
    if not components:
        return findings

    baseline_digest, baseline_files = component_digest(components[0])
    for relative, digest in baseline_files.items():
        if digest == "<missing>":
            findings.append(
                Finding(
                    components[0].relative_to(repo).as_posix(),
                    "HX8394_SHARED_FILE_MISSING",
                    f"missing required shared driver file {relative}",
                )
            )
    for component in components[1:]:
        digest, files = component_digest(component)
        for relative, file_digest in files.items():
            if file_digest == "<missing>":
                findings.append(
                    Finding(
                        component.relative_to(repo).as_posix(),
                        "HX8394_SHARED_FILE_MISSING",
                        f"missing required shared driver file {relative}",
                    )
                )
        if digest != baseline_digest:
            differing = sorted(
                path
                for path in set(baseline_files) | set(files)
                if baseline_files.get(path) != files.get(path)
            )
            findings.append(
                Finding(
                    component.relative_to(repo).as_posix(),
                    "HX8394_COPY_DRIFT",
                    "shared driver files differ: " + ", ".join(differing[:8]),
                )
            )

    source_relative = components[0].relative_to(repo) / "esp_lcd_hx8394.c"
    header_relative = components[0].relative_to(repo) / "include/esp_lcd_hx8394.h"
    source = read(repo, source_relative)
    header = read(repo, header_relative)
    required_guards = (
        "ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(6, 0, 0)",
        "panel_dev_config->rgb_ele_order",
        "panel_dev_config->color_space",
    )
    for marker in required_guards:
        if marker not in source:
            findings.append(
                Finding(
                    source_relative.as_posix(),
                    "HX8394_IDF_COMPATIBILITY_GUARD",
                    f"missing IDF 5/6 compatibility marker {marker}",
                )
            )
    if "HX8394_DPI_COLOR_FIELD" not in header:
        findings.append(
            Finding(
                header_relative.as_posix(),
                "HX8394_DPI_COMPATIBILITY_GUARD",
                "missing the IDF 5/6 DPI color-field compatibility guard",
            )
        )
    for line_number, line in enumerate(source.splitlines(), start=1):
        if "i2c_bus_write_bytes(" in line and not line.lstrip().startswith("//"):
            findings.append(
                Finding(
                    source_relative.as_posix(),
                    "HX8394_UNSCOPED_I2C_SIDE_EFFECT",
                    f"line {line_number} enables a board-specific I2C side effect",
                )
            )
    return findings


def check_hosted_wifi(repo: Path) -> list[Finding]:
    manifest = read(repo, WIFI_MANIFEST)
    findings: list[Finding] = []
    required_ranges = (
        'version: ">=1.6,<2.0"',
        'version: "0.14.*"',
        'version: ">=2.12,<3.0"',
        'version: "1.4.*"',
    )
    for value in required_ranges:
        if value not in manifest:
            findings.append(
                Finding(
                    WIFI_MANIFEST.as_posix(),
                    "HOSTED_WIFI_RANGE",
                    f"missing compatibility range {value}",
                )
            )
    if "matching slave" not in manifest:
        findings.append(
            Finding(
                WIFI_MANIFEST.as_posix(),
                "HOSTED_WIFI_RANGE_RATIONALE",
                "component ranges need a slave-firmware revisit condition",
            )
        )
    return findings


def check_mp4_audio_codec(repo: Path) -> list[Finding]:
    manifest = read(repo, MP4_AUDIO_MANIFEST)
    dependency = re.search(
        r"(?ms)^  espressif/esp_audio_codec:\s*$"
        r"(.*?)(?=^  [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+:\s*$|\Z)",
        manifest,
    )
    if not dependency or 'version: "2.5.0"' not in dependency.group(1):
        return [
            Finding(
                MP4_AUDIO_MANIFEST.as_posix(),
                "MP4_AUDIO_CODEC_VERSION",
                "ESP32-P4 revision 1/2 compatibility requires esp_audio_codec 2.5.0",
            )
        ]
    return []


def run(repo: Path) -> list[Finding]:
    repo = repo.resolve()
    return sorted(
        {
            *check_brookesia(repo),
            *check_hx8394(repo),
            *check_hosted_wifi(repo),
            *check_mp4_audio_codec(repo),
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check repository-specific static component contracts."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    try:
        findings = run(args.root)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"component contract error: {error}", file=sys.stderr)
        return 2

    if findings:
        for finding in findings:
            print(f"{finding.path}: {finding.code}: {finding.message}")
        print(f"{len(findings)} component contract finding(s)", file=sys.stderr)
        return 1
    print("Component contract check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
