[简体中文](CI_ZH.md) · [Documentation index](README.md)

# CI discovery and routing

The ESP-IDF workflow validates the 12 first-party projects directly below
[examples/esp-idf](../examples/esp-idf/). Embedded component test applications
and the checked-in factory firmware are inventoried separately and are not
silently promoted into the product-example matrix.

Only direct children of `examples/esp-idf` are first-party matrix entries.
Nested `components/**/test_apps` remain component tests, are not discoverable as
product examples, and cannot be selected through manual workflow dispatch.

## Required build matrix

| Framework line | Exact CI release | First-party projects | Build jobs |
| --- | --- | ---: | ---: |
| ESP-IDF 5.5 | v5.5.5 | 12 | 24 (12 × 2 profiles) |
| ESP-IDF 6.0 | v6.0.2 | 12 | 24 (12 × 2 profiles) |

The exact tags are reviewed when the workflow is updated. A successful build
proves compile compatibility for the checked-out commit; it does not prove
hardware behavior or factory-firmware compatibility. HIL on the target board is
required for display, touch, audio, camera, wireless, and flashing behavior.

## Changed-file routing

The repository policy job runs on every pull request. Expensive example builds
are selected from one complete, rename-aware Git diff.

| Changed path kind | Example build selection |
| --- | --- |
| Root, docs, schematic, governance, or example Markdown | None |
| Lightweight policy/maintenance helper, its test, Markdown-audit config, or `.gitignore` | None; run the lightweight policy gate with `docs_only=false` |
| Source or configuration inside one first-party example | That example only |
| Shared build configuration or the build workflow/discovery helper | All 12 |
| Firmware documentation or source | None; report firmware/release scope separately |
| Firmware `.bin` or `.zip` artifact, including a rename or deletion | None; set `release_review=true` and fail the stable example-CI result |
| Complete but unfamiliar non-document path | All 12 and report the path |
| Empty, missing, or unreadable diff | Fail the policy job |

Firmware routing never authorizes rebuilding, repackaging, or changing the
factory image. This example CI provides no artifact-release bypass: every
computed `release_review=true` fails the stable `ESP-IDF examples` result, even
when no example build is selected. A controlled release update requires a
separate protected process with explicit maintainer scope; this repository does
not define that process.

## Manual selection

The workflow dispatch input accepts:

- all;
- a unique example directory name, such as 04_wifistation;
- a repository-relative example path.

Its aggregate job is named `ESP-IDF examples (manual)` for manual dispatches;
pull requests and pushes retain `ESP-IDF examples`, so the same SHA cannot get
indistinguishable aggregate check contexts.

## Stable results

Every build job checks out the exact pull-request head SHA reported by the
policy job. The final ESP-IDF examples aggregate job remains visible even when a
documentation-only change correctly selects no product builds. New commits in
the same pull request cancel obsolete runs without affecting other branches or
release workflows.

The routing and Markdown/component-policy helpers have synthetic tests covering
documentation, direct source, shared inputs, firmware, rename/deletion,
unfamiliar paths, and incomplete diff data.

## Managed component versions

Display examples 07–12 resolve the LCD5 BSP `^1.0.3` and the HX8394 driver
`^2.1.0` from the ESP Component Registry (waveshare namespace). Their default
source configuration selects rev3.x. Independent product-firmware revision jobs
remain outside this example CI change.

## ESP32-P4 silicon revision profiles

`rev1_3` and `rev3_x` identify **ESP32-P4 silicon revisions** reported by an
ESP32-P4 chip probe. They do not identify the Waveshare PCB or product hardware
revision. Do not select a profile from the PCB silkscreen alone; confirm the chip
revision with the flasher's read-only probe or other authoritative chip evidence.

| Profile | Supported ESP32-P4 silicon | Revision configuration | PSRAM configuration | Repository role |
| --- | --- | --- | --- | --- |
| `rev3_x` | `[3.0, 4.0)` | `CONFIG_ESP32P4_SELECTS_REV_LESS_V3=n` and `CONFIG_ESP32P4_REV_MIN_300=y` | `CONFIG_SPIRAM_SPEED_250M=y` and 250 MHz | Default for all 12 first-party examples and the explicit current-silicon CI profile |
| `rev1_3` | `[1.0, 2.0)` (rev1.x, including rev1.3) | `CONFIG_ESP32P4_SELECTS_REV_LESS_V3=y` and `CONFIG_ESP32P4_REV_MIN_100=y` | `CONFIG_SPIRAM_SPEED_200M=y` and 200 MHz | Compatibility profile; use only for confirmed rev1.x silicon |

Despite the historical `SELECTS_REV_LESS_V3` symbol name, both supported IDF
lines generate `CONFIG_ESP32P4_REV_MAX_FULL=199` for this profile. Therefore a
2.x revision is not covered by `rev1_3`.

The example bundles are built and published for both explicit profiles: `rev1_3`
and `rev3_x`. With no explicit profile overlay, each top-level
`sdkconfig.defaults` selects the `rev3_x` row above. The named overlays make both
profiles explicit for CI and reproducible local builds.

When switching profiles locally, run from the selected example directory and
isolate both the build directory and generated `sdkconfig`:

```bash
profile=rev3_x  # or rev1_3
idf.py -B "build/$profile" \
  -D "SDKCONFIG=$PWD/build/$profile/sdkconfig" \
  -D "SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.defaults.$profile" \
  build
idf.py -B "build/$profile" -p PORT flash monitor
```

A previously generated project-level `sdkconfig` takes precedence over defaults
in an ordinary build. Do not reuse it when changing profiles. The command above
avoids that ambiguity by assigning each profile its own generated configuration.

## CI firmware bundles and manual hardware verification

Each required ESP-IDF build creates one artifact per profile named
`firmware-esp-idf-<project-slug>-<version>-<profile>`. The 12 direct projects, two
ESP-IDF releases, and two profiles therefore create 48 independently traceable
bundles. The
bundle is generated from that build's `flasher_args.json`; it preserves the
actual offsets rather than assuming fixed ESP32-P4 offsets, and includes
`bin/**`, `manifest.json`, and `metadata/flasher_args.json`.
The package preserves the build's validated flash mode, size, frequency, reset,
and stub settings as structured manifest data; unknown or unsafe esptool
arguments are rejected. The bundle does not contain a direct flashing helper or
command: use only the root `Flash-CI-Firmware.cmd` entry point, which delegates
to the checked-in PowerShell orchestrator and requires an explicit `COMx` port.
Packaging requires the actual generated build configuration (`build/config/sdkconfig.json`,
or generated `build/sdkconfig` fallback) to contain
the symbols for the selected profile (`rev1_3`: `SELECTS_REV_LESS_V3=y` and
`REV_MIN_100=y`; `rev3_x`: `SELECTS_REV_LESS_V3=n` and `REV_MIN_300=y`); source
defaults are not accepted as evidence. The inner ZIP name and manifest carry the
selected profile and its revision range, plus `c6_firmware_included: false`.

Before manually testing, install GitHub CLI and Python with esptool, then sign
in with `gh auth login`. From a clean, non-detached branch with exactly one
open non-draft PR, use the stable Windows entry point:

```text
Flash-CI-Firmware.cmd -SelfTest
Flash-CI-Firmware.cmd -ListOnly
Flash-CI-Firmware.cmd -Port COMx [-Baud N]
```

`-SelfTest` and `-ListOnly` are offline checks: they do not access GitHub,
serial devices, or artifacts. Normal mode requires the explicit placeholder
`COMx`; it never guesses a serial device. It accepts only a successful workflow
run for the final PR HEAD SHA that reports exactly the complete set of 48 unique,
unexpired expected firmware artifacts; partial dispatch runs are rejected. It
then downloads only the selected exact artifact, verifies the manifest identity,
checks every relative binary path, size, SHA-256, offset, overlap, and 32 MiB
flash boundary, then requires both a successful esptool exit code and
`Hash of data verified`. Before any artifact download or flash, it performs the
read-only `esptool chip_id` ESP32-P4 probe (using `chip-id` only as a compatibility
fallback), parses the silicon revision, and selects `rev1_3` for `[1.0, 2.0)` or
`rev3_x` for `[3.0, 4.0)`. Revisions outside those ranges, including 0.x, 2.x,
and 4.x or newer, are rejected before artifact lookup, download, or flashing;
the manifest range check then rejects any profile mismatch.
The silicon check does not replace PCB/electrical revision
confirmation. After each flash, the user must manually inspect the hardware and
type `PASS`; progress is profile-isolated local application data and resets for
a different final SHA, selected workflow run, profile, malformed/truncated
saved state, or legacy state schema. State writes use a same-directory temporary
file followed by an atomic replace or move.

These CI bundles are test outputs, not the checked-in factory firmware. The CI
build and integrity gates do not perform physical testing. A board runs the 24
checks matching its detected profile; validating both profiles requires 48
explicit hardware checks across suitable boards.
