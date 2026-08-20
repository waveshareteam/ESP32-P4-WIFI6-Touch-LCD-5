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

## Managed component versions

The six display-capable examples no longer carry local
`esp32_p4_wifi6_touch_lcd_5` BSP or `esp_lcd_hx8394` driver directories. Their
main manifests resolve both components from the ESP Component Registry
(waveshare namespace):

- BSP [`esp32_p4_wifi6_touch_lcd_5`](https://components.espressif.com/components/waveshare/esp32_p4_wifi6_touch_lcd_5) `^1.0.3`.
- HX8394 driver [`esp_lcd_hx8394`](https://components.espressif.com/components/waveshare/esp_lcd_hx8394) `^2.1.0`.

The `bsp_extra` wrappers in examples 08 and 12 use the same BSP range `^1.0.3`;
they do not override the direct example dependency.

## HX8394 initialization boundary

The HX8394 driver's standalone default sends its I2C command sequence. The
LCD5 BSP selects the skip behavior for this board integration. This source-level
contract does not prove panel behavior: HIL validation on the target board is
required before changing or promoting either version.

## ESP32-P4 revision defaults

All 12 first-party example defaults target ESP32-P4 rev3.x silicon with the
`CONFIG_ESP32P4_REV_MIN_300` symbol and 250 MHz PSRAM. The USB extended-screen
ESP32-P4 overlay carries the same default. The explicit `rev1_3` profile remains
available for rev1.x compatibility with 200 MHz PSRAM; CI builds and publishes
both profiles, and the firmware flasher selects the matching profile after its
read-only silicon probe.

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
later require ESP32-P4 revision 3 or newer, while the explicit `rev1_3` profile
retains rev1.x support. Changing this pin requires hardware-revision evidence
and a successful complete IDF matrix.

## Review rules

- Do not edit embedded upstream documentation or license files as product-local translations.
- Component manifests intended for Registry publication must depend only on already published Registry versions; do not ship temporary Git or path dependencies.
- Treat source-level initialization selection and successful CI as compile evidence only; require HIL for display behavior.
- Keep version-range rationale and its revisit condition beside the manifest.
