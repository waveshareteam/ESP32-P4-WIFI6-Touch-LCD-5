#!/usr/bin/env python3
"""Synthetic tests for repository-specific component contracts."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("check_component_contracts.py").resolve()
SPEC = importlib.util.spec_from_file_location("component_contracts", SCRIPT)
assert SPEC and SPEC.loader
CONTRACTS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CONTRACTS
SPEC.loader.exec_module(CONTRACTS)

KCONFIG = """menu "Test"
    config ESP_BROOKESIA_ENABLE_AI_FRAMEWORK
        bool
        default n

    menuconfig ESP_BROOKESIA_ENABLE_GUI
        bool "GUI"
        default y
endmenu
"""
BROOKESIA_MANIFEST = """dependencies:
  espressif/esp-boost:
    matches:
      - if: "idf_version >= 6.0"
        version: "0.6.0"
      - if: "idf_version < 6.0"
        version: "0.3.*"
    public: true
"""
WIFI_MANIFEST = """dependencies:
  # Revisit with matching slave firmware.
  espressif/esp_wifi_remote:
    matches:
      - if: "idf_version >= 6.0"
        version: ">=1.6,<2.0"
      - if: "idf_version < 6.0"
        version: "0.14.*"
  espressif/esp_hosted:
    matches:
      - if: "idf_version >= 6.0"
        version: ">=2.12,<3.0"
      - if: "idf_version < 6.0"
        version: "1.4.*"
"""
MP4_AUDIO_MANIFEST = """dependencies:
  espressif/esp_audio_codec:
    version: "2.5.0"
"""
REVISION_DEFAULTS = """CONFIG_IDF_TARGET="esp32p4"
CONFIG_ESP32P4_SELECTS_REV_LESS_V3=y
CONFIG_ESP32P4_REV_MIN_100=y
"""
VIDEO_DEFAULTS = REVISION_DEFAULTS + """CONFIG_CAMERA_OV5647_MIPI_RAW8_800X1280_50FPS=y
CONFIG_CAMERA_OV5647_MIPI_DEFAULT_FMT_RAW8_800X1280_50FPS=y
"""
BROOKESIA_MAIN = """else if ((BSP_LCD_H_RES == 720) && (BSP_LCD_V_RES == 1280))
{
    stylesheet = new Stylesheet(STYLESHEET_720_1280_DARK);
}
"""
USB_DESCRIPTOR_HEADER = """#define USB_EXTEND_SCREEN_H_RES  720
#define USB_EXTEND_SCREEN_V_RES  1280
"""
USB_DESCRIPTOR_SOURCE = """TUD_HID_REPORT_DESC_TOUCH_SCREEN(
    REPORT_ID_TOUCH, USB_EXTEND_SCREEN_H_RES, USB_EXTEND_SCREEN_V_RES);
#define VENDOR_STR \\
    STRINGIFY(USB_EXTEND_SCREEN_H_RES) \\
    "x" \\
    STRINGIFY(USB_EXTEND_SCREEN_V_RES)
// array of pointer to string descriptors
"""
USB_APP_MAIN = """_Static_assert(USB_EXTEND_SCREEN_H_RES == BSP_LCD_H_RES, "width");
_Static_assert(USB_EXTEND_SCREEN_V_RES == BSP_LCD_V_RES, "height");
"""


def git_dependency(component: str, path: str, revision: str) -> str:
    return f"""  {component}:
    git: {CONTRACTS.COMPONENT_REPOSITORY}
    path: {path}
    version: "{revision}"
"""


class ContractRepository:
    def __init__(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.write("examples/esp-idf/11_esp_brookesia_phone/components/brookesia_core/Kconfig", KCONFIG)
        self.write("examples/esp-idf/11_esp_brookesia_phone/components/brookesia_core/idf_component.yml", BROOKESIA_MANIFEST)
        self.write("examples/esp-idf/11_esp_brookesia_phone/components/brookesia_core/systems/speaker/idf_component.yml", BROOKESIA_MANIFEST)
        self.write(CONTRACTS.WIFI_MANIFEST.as_posix(), WIFI_MANIFEST)
        self.write(CONTRACTS.MP4_AUDIO_MANIFEST.as_posix(), MP4_AUDIO_MANIFEST)
        for project in CONTRACTS.ALL_PROJECTS[:6]:
            self.write(
                f"examples/esp-idf/{project}/sdkconfig.defaults",
                REVISION_DEFAULTS,
            )
        for project, manifest in zip(CONTRACTS.DISPLAY_PROJECTS, CONTRACTS.MAIN_MANIFESTS):
            dependencies = (
                "dependencies:\n"
                + git_dependency(CONTRACTS.BSP_COMPONENT, CONTRACTS.BSP_PATH, CONTRACTS.BSP_COMPONENT_REVISION)
                + git_dependency(CONTRACTS.HX8394_COMPONENT, CONTRACTS.HX8394_PATH, CONTRACTS.HX8394_COMPONENT_REVISION)
            )
            if project == "10_mp4_player":
                dependencies += "  espressif/esp_audio_codec:\n    version: \"2.5.0\"\n"
            self.write(manifest.as_posix(), dependencies)
            self.write(f"examples/esp-idf/{project}/sdkconfig.defaults", REVISION_DEFAULTS)
        self.write("examples/esp-idf/07_Displaycolorbar/sdkconfig.defaults.esp32p4", "CONFIG_COMPILER_OPTIMIZATION_PERF=y\n")
        self.write("examples/esp-idf/12_usb_extend_screen/sdkconfig.defaults.esp32p4", REVISION_DEFAULTS)
        self.write(CONTRACTS.VIDEO_DEFAULTS.as_posix(), VIDEO_DEFAULTS)
        self.write(CONTRACTS.BROOKESIA_MAIN.as_posix(), BROOKESIA_MAIN)
        self.write(CONTRACTS.BROOKESIA_DEFAULTS.as_posix(), REVISION_DEFAULTS)
        self.write(CONTRACTS.USB_DESCRIPTOR_HEADER.as_posix(), USB_DESCRIPTOR_HEADER)
        self.write(CONTRACTS.USB_DESCRIPTOR_SOURCE.as_posix(), USB_DESCRIPTOR_SOURCE)
        self.write(CONTRACTS.USB_APP_MAIN.as_posix(), USB_APP_MAIN)
        for relative in CONTRACTS.BSP_EXTRA_MANIFESTS:
            self.write(
                relative.as_posix(),
                "dependencies:\n"
                + git_dependency(
                    CONTRACTS.BSP_COMPONENT,
                    CONTRACTS.BSP_PATH,
                    CONTRACTS.BSP_COMPONENT_REVISION,
                ),
            )

    def close(self) -> None:
        self.tempdir.cleanup()

    def write(self, relative: str, content: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def codes(self) -> set[str]:
        return {finding.code for finding in CONTRACTS.run(self.root)}


class ComponentContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = ContractRepository()

    def tearDown(self) -> None:
        self.repo.close()

    def test_valid_contract_passes(self) -> None:
        self.assertEqual(self.repo.codes(), set())

    def test_exposed_ai_option_is_rejected(self) -> None:
        self.repo.write("examples/esp-idf/11_esp_brookesia_phone/components/brookesia_core/Kconfig", KCONFIG.replace("bool\n", 'bool "AI Framework"\n', 1))
        self.assertIn("BROOKESIA_AI_OPTION_EXPOSED", self.repo.codes())

    def test_unbounded_boost_is_rejected(self) -> None:
        self.repo.write("examples/esp-idf/11_esp_brookesia_phone/components/brookesia_core/idf_component.yml", BROOKESIA_MANIFEST.replace('"0.3.*"', '"*"'))
        self.assertIn("BROOKESIA_BOOST_RANGE", self.repo.codes())

    def test_legacy_shared_git_pin_is_rejected(self) -> None:
        relative = CONTRACTS.MAIN_MANIFESTS[0]
        legacy_revision = "7580ddc989c526678bd7364ece19bfdf1a2745c9"
        self.repo.write(relative.as_posix(), "dependencies:\n" + git_dependency(CONTRACTS.BSP_COMPONENT, CONTRACTS.BSP_PATH, legacy_revision) + git_dependency(CONTRACTS.HX8394_COMPONENT, CONTRACTS.HX8394_PATH, legacy_revision))
        self.assertIn("MANAGED_COMPONENT_GIT_PIN", self.repo.codes())

    def test_swapped_git_pins_are_rejected(self) -> None:
        relative = CONTRACTS.MAIN_MANIFESTS[0]
        self.repo.write(relative.as_posix(), "dependencies:\n" + git_dependency(CONTRACTS.BSP_COMPONENT, CONTRACTS.BSP_PATH, CONTRACTS.HX8394_COMPONENT_REVISION) + git_dependency(CONTRACTS.HX8394_COMPONENT, CONTRACTS.HX8394_PATH, CONTRACTS.BSP_COMPONENT_REVISION))
        self.assertIn("MANAGED_COMPONENT_GIT_PIN", self.repo.codes())

    def test_git_override_is_rejected(self) -> None:
        relative = CONTRACTS.MAIN_MANIFESTS[0]
        self.repo.write(relative.as_posix(), "dependencies:\n" + git_dependency(CONTRACTS.BSP_COMPONENT, CONTRACTS.BSP_PATH, CONTRACTS.BSP_COMPONENT_REVISION) + "    override_path: ../replacement\n" + git_dependency(CONTRACTS.HX8394_COMPONENT, CONTRACTS.HX8394_PATH, CONTRACTS.HX8394_COMPONENT_REVISION))
        self.assertIn("MANAGED_COMPONENT_OVERRIDE", self.repo.codes())

    def test_local_component_is_rejected(self) -> None:
        path = self.repo.root / "examples/esp-idf/07_Displaycolorbar/components/esp_lcd_hx8394"
        path.mkdir(parents=True)
        self.assertIn("LOCAL_MANAGED_COMPONENT_REMAINS", self.repo.codes())

    def test_bsp_extra_registry_dependency_is_rejected(self) -> None:
        relative = CONTRACTS.BSP_EXTRA_MANIFESTS[0]
        self.repo.write(relative.as_posix(), "dependencies:\n  waveshare/esp32_p4_wifi6_touch_lcd_5:\n    version: \"^1.0.1\"\n")
        self.assertIn("MANAGED_COMPONENT_GIT_PIN", self.repo.codes())

    def test_obsolete_revision_symbol_is_rejected(self) -> None:
        relative = "examples/esp-idf/07_Displaycolorbar/sdkconfig.defaults"
        self.repo.write(relative, REVISION_DEFAULTS.replace("REV_MIN_100", "REV_MIN_1"))
        self.assertIn("P4_REVISION_ONE_SYMBOL", self.repo.codes())

    def test_missing_pre_v3_default_is_rejected(self) -> None:
        relative = "examples/esp-idf/12_usb_extend_screen/sdkconfig.defaults.esp32p4"
        self.repo.write(relative, "CONFIG_IDF_TARGET=\"esp32p4\"\n")
        self.assertIn("P4_PRE_V3_REVISION_DEFAULT", self.repo.codes())

    def test_floating_mp4_audio_codec_is_rejected(self) -> None:
        self.repo.write(CONTRACTS.MP4_AUDIO_MANIFEST.as_posix(), MP4_AUDIO_MANIFEST.replace('"2.5.0"', '"^2.3.0"'))
        self.assertIn("MP4_AUDIO_CODEC_VERSION", self.repo.codes())

    def test_ov5647_portrait_default_is_required(self) -> None:
        support = "CONFIG_CAMERA_OV5647_MIPI_RAW8_800X1280_50FPS=y\n"
        default = "CONFIG_CAMERA_OV5647_MIPI_DEFAULT_FMT_RAW8_800X1280_50FPS=y\n"
        cases = {
            "missing support": VIDEO_DEFAULTS.replace(support, ""),
            "missing default": VIDEO_DEFAULTS.replace(default, ""),
            "commented support": VIDEO_DEFAULTS.replace(support, f"# {support}"),
            "commented default": VIDEO_DEFAULTS.replace(default, f"# {default}"),
            "competing default": VIDEO_DEFAULTS + "CONFIG_CAMERA_OV5647_MIPI_DEFAULT_FMT_RAW8_800X800_50FPS=y\n",
        }
        for name, invalid in cases.items():
            with self.subTest(name=name):
                self.repo.write(CONTRACTS.VIDEO_DEFAULTS.as_posix(), invalid)
                self.assertIn("OV5647_PORTRAIT_DEFAULT", self.repo.codes())
        self.repo.write(CONTRACTS.VIDEO_DEFAULTS.as_posix(), VIDEO_DEFAULTS)

    def test_ov5647_legacy_alias_is_rejected(self) -> None:
        self.repo.write(
            CONTRACTS.VIDEO_DEFAULTS.as_posix(),
            VIDEO_DEFAULTS + "CONFIG_CAMERA_OV5647_MIPI_RAW8_800x1280_50FPS=y\n",
        )
        self.assertIn("OV5647_LEGACY_FORMAT_SYMBOL", self.repo.codes())

    def test_brookesia_720x1280_stylesheet_is_required(self) -> None:
        self.repo.write(
            CONTRACTS.BROOKESIA_MAIN.as_posix(),
            BROOKESIA_MAIN.replace("STYLESHEET_720_1280_DARK", "STYLESHEET_800_1280_DARK"),
        )
        self.assertIn("BROOKESIA_720_1280_STYLESHEET", self.repo.codes())

    def test_stale_brookesia_lcd_profile_is_rejected(self) -> None:
        self.repo.write(
            CONTRACTS.BROOKESIA_DEFAULTS.as_posix(),
            REVISION_DEFAULTS + "CONFIG_BSP_LCD_TYPE_720_1280_7_INCH_A=y\n",
        )
        self.assertIn("BROOKESIA_STALE_LCD_PROFILE", self.repo.codes())

    def test_usb_display_resolution_contract_is_required(self) -> None:
        cases = (
            (CONTRACTS.USB_DESCRIPTOR_HEADER, USB_DESCRIPTOR_HEADER, USB_DESCRIPTOR_HEADER.replace("1280", "800")),
            (CONTRACTS.USB_DESCRIPTOR_SOURCE, USB_DESCRIPTOR_SOURCE, USB_DESCRIPTOR_SOURCE.replace("USB_EXTEND_SCREEN_H_RES, USB_EXTEND_SCREEN_V_RES", "USB_EXTEND_SCREEN_V_RES, USB_EXTEND_SCREEN_H_RES", 1)),
            (CONTRACTS.USB_APP_MAIN, USB_APP_MAIN, USB_APP_MAIN.replace("_Static_assert(USB_EXTEND_SCREEN_H_RES == BSP_LCD_H_RES, \"width\");\n", "")),
        )
        for relative, valid, invalid in cases:
            with self.subTest(relative=relative.as_posix()):
                self.repo.write(relative.as_posix(), invalid)
                self.assertIn("USB_DISPLAY_RESOLUTION", self.repo.codes())
                self.repo.write(relative.as_posix(), valid)


if __name__ == "__main__":
    unittest.main(verbosity=2)
