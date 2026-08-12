[简体中文](COMPONENTS_ZH.md) · [Documentation index](README.md)

# Component ownership and dependency policy

Directories named `components` are classified by behavior and ownership before
any migration decision. Their location alone does not make them removable.

## Retained local surfaces

| Surface | Classification | Why it remains local |
| --- | --- | --- |
| `sd_card` in 05_sdmmc | Example test support | Performs board-specific SD pin, pull-up, voltage, and crosstalk checks |
| `bsp_extra` in 08 and 12 | Product board glue | Composes board audio, file iteration, playback, and recording behavior |
| `esp_extractor` in 10 | Precompiled media adapter | Carries a target-specific static library and format registration; replacement requires ABI, source, and license evidence |
| `brookesia_app_squareline_demo` | Product demo feature | Implements the checked-in Brookesia application rather than reusable board support |
| `brookesia_core` | Embedded upstream integration | Uses the release/v0.6 architecture with repository compatibility changes |

The two `bsp_extra` copies are candidates for a future deduplication, but only
after their call sites and USB/audio behavior are proven equivalent.

## Temporary managed-component pins

The six display-capable examples no longer carry local
`esp32_p4_wifi6_touch_lcd_5` BSP or `esp_lcd_hx8394` driver directories. Their
main manifests temporarily pin the BSP validation head and HX8394 component
source from the Waveshare component repository, reviewed in upstream
PR [#192](https://github.com/waveshareteam/Waveshare-ESP32-components/pull/192):

- BSP validation head [`d9a93c0`](https://github.com/waveshareteam/Waveshare-ESP32-components/commit/d9a93c0cf44bc8c39eced92462297262dd93d645), path: `bsp/esp32_p4_wifi6_touch_lcd_5`.
- HX8394 source [`fc6e6d2`](https://github.com/waveshareteam/Waveshare-ESP32-components/commit/fc6e6d2d63aa314cdcec2e8912614aacff2fbd6d), path: `display/lcd/esp_lcd_hx8394`.

These exact source pins remain temporary until their respective registry
releases. The `bsp_extra` wrappers in examples 08 and 12 retain their compatible
BSP range `^1.0.1`; they do not override the direct example pin.

## HX8394 initialization boundary

The pinned HX8394 source's standalone default sends its I2C command
sequence. The LCD5 BSP selects the skip behavior for this board integration.
This source-level contract does not prove panel behavior: HIL validation on the
target board is required before changing or promoting either pin.

## ESP32-P4 revision defaults

All 12 first-party example defaults target ESP32-P4 pre-v3 silicon with the
revision-1.0 minimum symbol; the product's default example profile is revision
1.3/pre-v3. The USB extended-screen ESP32-P4 profile carries the same default.
No maintained revision-3 product firmware source is present in this repository,
so revision-specific product-firmware jobs, artifacts, and flasher probes are
outside this example migration.

## Brookesia dependency contract

The checked-in Brookesia core identifies itself as release/v0.6 integration.
Its esp-boost dependency uses 0.3.* on ESP-IDF 5 and exact version 0.6.0 on
ESP-IDF 6. LVGL remains fixed at 9.5.0 because the repository's ESP-IDF 6
compatibility changes target that version.

The legacy AI framework is intentionally hidden and disabled because its
dependency stack is not included in this product integration. Re-enabling it
requires an explicit Brookesia architecture upgrade and a successful complete
IDF matrix; it is not a menuconfig-only change.

## MP4 audio codec boundary

The MP4 example fixes `espressif/esp_audio_codec` at 2.5.0. Version 2.6.0 and
later require ESP32-P4 revision 3 or newer, while the example defaults retain
pre-v3 support. Changing this pin requires hardware-revision evidence and a
successful complete IDF matrix.

## Review rules

- Do not edit embedded upstream documentation or license files as product-local translations.
- Keep the exact temporary source pin until a separately reviewed replacement is available.
- Treat source-level initialization selection and successful CI as compile evidence only; require HIL for display behavior.
- Keep version-range rationale and its revisit condition beside the manifest.
