#!/usr/bin/env python3
"""Static compatibility contracts that are easy for default builds to miss."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


BROOKESIA_ROOT = Path("examples/esp-idf/11_esp_brookesia_phone/components/brookesia_core")
BROOKESIA_SPEAKER_MANIFEST = BROOKESIA_ROOT / "systems/speaker/idf_component.yml"
WIFI_MANIFEST = Path("examples/esp-idf/04_wifistation/main/idf_component.yml")
MP4_AUDIO_MANIFEST = Path("examples/esp-idf/10_mp4_player/main/idf_component.yml")
COMPONENT_REPOSITORY = "https://github.com/waveshareteam/Waveshare-ESP32-components.git"
BSP_COMPONENT = "waveshare/esp32_p4_wifi6_touch_lcd_5"
BSP_PATH = "bsp/esp32_p4_wifi6_touch_lcd_5"
BSP_COMPONENT_REVISION = "d9a93c0cf44bc8c39eced92462297262dd93d645"
HX8394_COMPONENT = "waveshare/esp_lcd_hx8394"
HX8394_PATH = "display/lcd/esp_lcd_hx8394"
HX8394_COMPONENT_REVISION = "fc6e6d2d63aa314cdcec2e8912614aacff2fbd6d"
DISPLAY_PROJECTS = (
    "07_Displaycolorbar",
    "08_lvgl_demo_v9",
    "09_video_lcd_display",
    "10_mp4_player",
    "11_esp_brookesia_phone",
    "12_usb_extend_screen",
)
ALL_PROJECTS = (
    "01_HowToCreateProject",
    "02_HelloWorld",
    "03_i2c_tools",
    "04_wifistation",
    "05_sdmmc",
    "06_I2SCodec",
    *DISPLAY_PROJECTS,
)
MAIN_MANIFESTS = tuple(
    Path(f"examples/esp-idf/{project}/main/idf_component.yml")
    for project in DISPLAY_PROJECTS
)
BSP_EXTRA_MANIFESTS = tuple(
    Path(f"examples/esp-idf/{project}/components/bsp_extra/idf_component.yml")
    for project in ("08_lvgl_demo_v9", "12_usb_extend_screen")
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


def dependency_block(manifest: str, component: str) -> str | None:
    match = re.search(
        rf"(?ms)^  {re.escape(component)}:\s*$"
        r"(.*?)(?=^  [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+:\s*$|\Z)",
        manifest,
    )
    return match.group(1) if match else None


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
        findings.append(Finding(kconfig_path.as_posix(), "BROOKESIA_AI_SYMBOL_MISSING", "keep the disabled compatibility symbol explicit"))
    else:
        block = symbol.group(1)
        if not re.search(r"(?m)^\s+bool\s*$", block):
            findings.append(Finding(kconfig_path.as_posix(), "BROOKESIA_AI_OPTION_EXPOSED", "legacy AI support must remain hidden while its dependencies are omitted"))
        if not re.search(r"(?m)^\s+default n\s*$", block):
            findings.append(Finding(kconfig_path.as_posix(), "BROOKESIA_AI_DEFAULT_ENABLED", "legacy AI support must remain disabled"))
    if 'rsource "ai_framework/Kconfig"' in kconfig:
        findings.append(Finding(kconfig_path.as_posix(), "BROOKESIA_AI_KCONFIG_REACHABLE", "legacy AI sub-options must not be reachable without the dependency stack"))

    boost_contract = ('if: "idf_version >= 6.0"', 'version: "0.6.0"', 'if: "idf_version < 6.0"', 'version: "0.3.*"')
    for boost_manifest_path in (manifest_path, BROOKESIA_SPEAKER_MANIFEST):
        boost = dependency_block(read(repo, boost_manifest_path), "espressif/esp-boost")
        if not boost or any(marker not in boost for marker in boost_contract):
            findings.append(Finding(boost_manifest_path.as_posix(), "BROOKESIA_BOOST_RANGE", "require esp-boost 0.3.* on IDF 5 and exact 0.6.0 on IDF 6"))
    for dependency in ("esp_coze", "gmf_core", "gmf_ai_audio", "gmf_io", "gmf_misc", "gmf_audio", "esp_audio_simple_player", "esp_websocket_client"):
        if re.search(rf"(?m)^\s+espressif/{re.escape(dependency)}:\s*$", manifest):
            findings.append(Finding(manifest_path.as_posix(), "BROOKESIA_AI_DEPENDENCY_WITH_DISABLED_FEATURE", f"unexpected disabled AI dependency espressif/{dependency}"))
    return findings


def check_git_dependency(relative: Path, manifest: str, component: str, path: str, revision: str) -> list[Finding]:
    findings: list[Finding] = []
    blocks = re.findall(
        rf"(?ms)^  {re.escape(component)}:\s*$"
        r"(.*?)(?=^  [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+:\s*$|\Z)",
        manifest,
    )
    if len(blocks) != 1:
        return [Finding(relative.as_posix(), "MANAGED_COMPONENT_DEPENDENCY_COUNT", f"require exactly one {component} dependency")]
    block = blocks[0]
    required = (f"git: {COMPONENT_REPOSITORY}", f"path: {path}", f'version: "{revision}"')
    if any(marker not in block for marker in required):
        findings.append(Finding(relative.as_posix(), "MANAGED_COMPONENT_GIT_PIN", f"require {component} at the exact upstream Git revision"))
    if re.search(r"(?m)^\s*(?:override|override_path):", block):
        findings.append(Finding(relative.as_posix(), "MANAGED_COMPONENT_OVERRIDE", "managed component dependency must not use an override"))
    if re.search(r"(?m)^\s*path:\s*(?:\.?/?components/|\.)", block):
        findings.append(Finding(relative.as_posix(), "MANAGED_COMPONENT_LOCAL_REFERENCE", "managed component dependency must not use a local path"))
    if re.search(r"(?m)^\s*version:\s*['\"]?\*", block):
        findings.append(Finding(relative.as_posix(), "MANAGED_COMPONENT_WILDCARD", "managed component dependency must not use a wildcard version"))
    return findings


def check_managed_components(repo: Path) -> list[Finding]:
    findings: list[Finding] = []
    for project, relative in zip(DISPLAY_PROJECTS, MAIN_MANIFESTS):
        for component in (BSP_COMPONENT, HX8394_COMPONENT):
            local = Path(f"examples/esp-idf/{project}/components/{component.split('/', 1)[1]}")
            if (repo / local).exists():
                findings.append(Finding(local.as_posix(), "LOCAL_MANAGED_COMPONENT_REMAINS", "remove the replaced example-local component directory"))
        manifest = read(repo, relative)
        findings.extend(check_git_dependency(relative, manifest, BSP_COMPONENT, BSP_PATH, BSP_COMPONENT_REVISION))
        findings.extend(check_git_dependency(relative, manifest, HX8394_COMPONENT, HX8394_PATH, HX8394_COMPONENT_REVISION))
    for relative in BSP_EXTRA_MANIFESTS:
        findings.extend(
            check_git_dependency(
                relative,
                read(repo, relative),
                BSP_COMPONENT,
                BSP_PATH,
                BSP_COMPONENT_REVISION,
            )
        )
    return findings


def check_revision_defaults(repo: Path) -> list[Finding]:
    findings: list[Finding] = []
    required = ('CONFIG_IDF_TARGET="esp32p4"', "CONFIG_ESP32P4_SELECTS_REV_LESS_V3=y", "CONFIG_ESP32P4_REV_MIN_100=y")
    for project in ALL_PROJECTS:
        relative = Path(f"examples/esp-idf/{project}/sdkconfig.defaults")
        content = read(repo, relative)
        if any(marker not in content for marker in required):
            findings.append(Finding(relative.as_posix(), "P4_PRE_V3_REVISION_DEFAULT", "require esp32p4, pre-v3 selection, and revision 1.0 default"))
    alternate = Path("examples/esp-idf/12_usb_extend_screen/sdkconfig.defaults.esp32p4")
    content = read(repo, alternate)
    if any(marker not in content for marker in required):
        findings.append(Finding(alternate.as_posix(), "P4_PRE_V3_REVISION_DEFAULT", "require the same pre-v3 revision default as the top-level profile"))
    for path in repo.glob("examples/esp-idf/*/sdkconfig.defaults*"):
        if path.is_file() and re.search(r"(?m)^CONFIG_ESP32P4_REV_MIN_1=y\s*$", path.read_text(encoding="utf-8")):
            findings.append(Finding(path.relative_to(repo).as_posix(), "P4_REVISION_ONE_SYMBOL", "use CONFIG_ESP32P4_REV_MIN_100=y, not the obsolete revision symbol"))
    return findings


def check_hosted_wifi(repo: Path) -> list[Finding]:
    manifest = read(repo, WIFI_MANIFEST)
    required_ranges = ('version: ">=1.6,<2.0"', 'version: "0.14.*"', 'version: ">=2.12,<3.0"', 'version: "1.4.*"')
    if all(value in manifest for value in required_ranges) and "matching slave" in manifest:
        return []
    return [Finding(WIFI_MANIFEST.as_posix(), "HOSTED_WIFI_RANGE", "keep the matching-slave compatibility ranges and revisit condition")]


def check_mp4_audio_codec(repo: Path) -> list[Finding]:
    dependency = dependency_block(read(repo, MP4_AUDIO_MANIFEST), "espressif/esp_audio_codec")
    if dependency and 'version: "2.5.0"' in dependency:
        return []
    return [Finding(MP4_AUDIO_MANIFEST.as_posix(), "MP4_AUDIO_CODEC_VERSION", "ESP32-P4 revision 1/2 compatibility requires esp_audio_codec 2.5.0")]


def run(repo: Path) -> list[Finding]:
    repo = repo.resolve()
    return sorted({*check_brookesia(repo), *check_managed_components(repo), *check_revision_defaults(repo), *check_hosted_wifi(repo), *check_mp4_audio_codec(repo)})


def main() -> int:
    parser = argparse.ArgumentParser(description="Check repository-specific static component contracts.")
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
