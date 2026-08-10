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
  # v2.6.0 requires ESP32-P4 revision >= 3.
  espressif/esp_audio_codec:
    version: "2.5.0"
    public: true
"""

PRODUCT_BSP_MANIFEST = """dependencies:
  # The bundled/product-reviewed v1.0.3 contract differs from registry v2 APIs and initialization.
  # Re-evaluate only after both IDF lines and hardware validation.
  waveshare/esp_lcd_hx8394: '^1.0.3'
"""

HX_SOURCE = """#include "esp_idf_version.h"
#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(6, 0, 0)
switch (panel_dev_config->rgb_ele_order) {}
#else
switch (panel_dev_config->color_space) {}
#endif
// i2c_bus_write_bytes(device, 0, 0, data);
"""


class ContractRepository:
    def __init__(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.write(
            "examples/esp-idf/11_esp_brookesia_phone/components/"
            "brookesia_core/Kconfig",
            KCONFIG,
        )
        self.write(
            "examples/esp-idf/11_esp_brookesia_phone/components/"
            "brookesia_core/idf_component.yml",
            BROOKESIA_MANIFEST,
        )
        self.write(
            "examples/esp-idf/11_esp_brookesia_phone/components/"
            "brookesia_core/systems/speaker/idf_component.yml",
            BROOKESIA_MANIFEST,
        )
        self.write(
            "examples/esp-idf/04_wifistation/main/idf_component.yml",
            WIFI_MANIFEST,
        )
        self.write(
            "examples/esp-idf/10_mp4_player/main/idf_component.yml",
            MP4_AUDIO_MANIFEST,
        )
        for name in ("07_a", "08_b", "09_c", "10_d", "11_e", "12_f"):
            root = f"examples/esp-idf/{name}/components/esp_lcd_hx8394"
            self.write(f"{root}/esp_lcd_hx8394.c", HX_SOURCE)
            self.write(
                f"{root}/include/esp_lcd_hx8394.h",
                "#define HX8394_DPI_COLOR_FIELD pixel_format\n",
            )
            self.write(f"{root}/idf_component.yml", "version: 1.0.3\n")
            self.write(f"{root}/license.txt", "MIT\n")
            self.write(f"{root}/README.md", "# HX8394\n")
        for relative in CONTRACTS.PRODUCT_BSP_HX8394_MANIFESTS:
            self.write(relative.as_posix(), PRODUCT_BSP_MANIFEST)

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
        self.repo.write(
            "examples/esp-idf/11_esp_brookesia_phone/components/"
            "brookesia_core/Kconfig",
            KCONFIG.replace("bool\n", 'bool "AI Framework"\n', 1),
        )
        self.assertIn("BROOKESIA_AI_OPTION_EXPOSED", self.repo.codes())

    def test_unbounded_boost_is_rejected(self) -> None:
        self.repo.write(
            "examples/esp-idf/11_esp_brookesia_phone/components/"
            "brookesia_core/idf_component.yml",
            BROOKESIA_MANIFEST.replace('"0.3.*"', '"*"'),
        )
        self.assertIn("BROOKESIA_BOOST_RANGE", self.repo.codes())

    def test_missing_idf6_boost_bridge_is_rejected(self) -> None:
        self.repo.write(
            "examples/esp-idf/11_esp_brookesia_phone/components/"
            "brookesia_core/systems/speaker/idf_component.yml",
            BROOKESIA_MANIFEST.replace('"0.6.0"', '"0.3.*"'),
        )
        self.assertIn("BROOKESIA_BOOST_RANGE", self.repo.codes())

    def test_copy_drift_is_rejected(self) -> None:
        self.repo.write(
            "examples/esp-idf/12_f/components/esp_lcd_hx8394/"
            "include/esp_lcd_hx8394.h",
            "#define HX8394_DPI_COLOR_FIELD in_color_format\n",
        )
        self.assertIn("HX8394_COPY_DRIFT", self.repo.codes())

    def test_shared_file_missing_from_every_copy_is_rejected(self) -> None:
        for name in ("07_a", "08_b", "09_c", "10_d", "11_e", "12_f"):
            (
                self.repo.root
                / f"examples/esp-idf/{name}/components/esp_lcd_hx8394/README.md"
            ).unlink()
        self.assertIn("HX8394_SHARED_FILE_MISSING", self.repo.codes())

    def test_active_i2c_side_effect_is_rejected(self) -> None:
        changed = HX_SOURCE.replace(
            "// i2c_bus_write_bytes", "i2c_bus_write_bytes"
        )
        for name in ("07_a", "08_b", "09_c", "10_d", "11_e", "12_f"):
            self.repo.write(
                f"examples/esp-idf/{name}/components/esp_lcd_hx8394/"
                "esp_lcd_hx8394.c",
                changed,
            )
        self.assertIn("HX8394_UNSCOPED_I2C_SIDE_EFFECT", self.repo.codes())

    def test_floating_mp4_audio_codec_is_rejected(self) -> None:
        self.repo.write(
            "examples/esp-idf/10_mp4_player/main/idf_component.yml",
            MP4_AUDIO_MANIFEST.replace('"2.5.0"', '"^2.3.0"'),
        )
        self.assertIn("MP4_AUDIO_CODEC_VERSION", self.repo.codes())

    def test_floating_product_bsp_hx8394_dependency_is_rejected(self) -> None:
        relative = CONTRACTS.PRODUCT_BSP_HX8394_MANIFESTS[0]
        self.repo.write(
            relative.as_posix(),
            PRODUCT_BSP_MANIFEST.replace("'^1.0.3'", "'*'"),
        )
        self.assertIn("HX8394_PRODUCT_BSP_VERSION", self.repo.codes())

    def test_missing_product_bsp_hx8394_dependency_is_rejected(self) -> None:
        relative = CONTRACTS.PRODUCT_BSP_HX8394_MANIFESTS[0]
        self.repo.write(relative.as_posix(), "dependencies:\n  idf: '>=5.4'\n")
        self.assertIn("HX8394_PRODUCT_BSP_DEPENDENCY_MISSING", self.repo.codes())


if __name__ == "__main__":
    unittest.main(verbosity=2)
