[简体中文](COMPONENTS_ZH.md) · [Documentation index](README.md)

# Component ownership and dependency policy

Directories named components are classified by behavior and ownership before
any migration decision. Their location alone does not make them removable.

## Retained local surfaces

| Surface | Classification | Why it remains local |
| --- | --- | --- |
| sd_card in 05_sdmmc | Example test support | Performs board-specific SD pin, pull-up, voltage, and crosstalk checks |
| bsp_extra in 08 and 12 | Product board glue | Composes board audio, file iteration, playback, and recording behavior |
| esp_extractor in 10 | Precompiled media adapter | Carries a target-specific static library and format registration; replacement requires ABI, source, and license evidence |
| brookesia_app_squareline_demo | Product demo feature | Implements the checked-in Brookesia application rather than reusable board support |
| brookesia_core | Embedded upstream integration | Uses the release/v0.6 architecture with repository compatibility changes |
| esp32_p4_wifi6_touch_lcd_5 | Example-local product BSP | No semantically equivalent managed product BSP was confirmed |

The two bsp_extra copies are candidates for a future deduplication, but only
after their call sites and USB/audio behavior are proven equivalent.

## HX8394 driver boundary

Six display-capable examples carry the same product-reviewed HX8394 driver
source, public header, manifest, license, and upstream README. The copies remain
local because the current managed v2.0.0 component is not behaviorally
equivalent to this integration:

- the local code retains ESP-IDF 5.5 and 6.0 color-field compatibility;
- the managed version enables additional board-specific I2C writes during panel
  creation, while this product integration intentionally leaves them disabled;
- the managed version changes DMA2D initialization behavior on ESP-IDF 6.

The default HX8394 vendor command sequence matches, but that alone is not enough
to prove full hardware equivalence. Revisit the managed migration only when a
side-effect-free release supports both required IDF lines and is validated on
this board. The repository policy job detects drift in the shared local driver
files.

## HX8394 product BSP dependency contract

The six display-capable product BSP manifests require
`waveshare/esp_lcd_hx8394: '^1.0.3'`. This preserves the bundled,
product-reviewed v1.0.3 contract: registry v2 has different APIs and panel
initialization behavior. Reassess the constraint only after both required ESP-IDF
lines and the target hardware have been validated; do not change embedded
upstream HX8394 content as part of that reassessment.

## Brookesia dependency contract

The checked-in Brookesia core identifies itself as release/v0.6 integration.
Its esp-boost dependency uses 0.3.* on ESP-IDF 5, matching the API line used by
the vendored source. ESP-IDF 6 uses exact version 0.6.0: that is the first
esp-boost release with IDF 6 support and the compatibility bridge proven by this
repository's matrix. This bridge is product-local evidence, not a claim that
upstream Brookesia release/v0.6 officially supports IDF 6. LVGL remains fixed at
9.5.0 because the repository's ESP-IDF 6 compatibility changes target that
version.

The legacy AI framework is intentionally hidden and disabled. Its release/v0.6
dependency stack is not included in this product integration, so exposing the
option would create a configuration that cannot resolve. Re-enabling it requires
an explicit Brookesia architecture upgrade and a successful complete IDF
matrix; it is not a menuconfig-only change.

## MP4 audio codec boundary

The MP4 example fixes `espressif/esp_audio_codec` at 2.5.0. Version 2.6.0 and
later require ESP32-P4 revision 3 or newer, while this repository deliberately
retains revision 1/2 support. Version 2.5.0 is the last release before that
hardware gate and explicitly supports ESP-IDF 6 builds. Changing the pin
requires hardware-revision evidence and a successful complete IDF matrix.

## Review rules

- Do not edit embedded upstream documentation or license files as product-local
  translations.
- Do not replace a local component until API, target, IDF-version, initialization
  sequence, and hardware behavior are equivalent.
- Keep version-range rationale and its revisit condition beside the manifest.
- Changes to shared driver behavior require schematic review and both required
  Actions matrix lines.
