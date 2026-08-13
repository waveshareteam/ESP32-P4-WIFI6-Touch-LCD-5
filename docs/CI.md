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
| ESP-IDF 5.5 | v5.5.5 | 12 | 12 |
| ESP-IDF 6.0 | v6.0.2 | 12 | 12 |

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

## Managed component pin and revision defaults

Display examples 07–12 use temporary exact Git pins for the LCD5 BSP validation
head `d9a93c0` and HX8394 component source `fc6e6d2` (reviewed in upstream
PR #192). Both pins remain temporary until their respective registry releases.
Their defaults select the revision-1.3/pre-v3 product profile; product-firmware
revision jobs are not included because this repository has no maintained product
firmware source.

The example bundles default to the `rev1_3` (pre-v3) profile. A `rev3_x` product
artifact is intentionally absent: no maintained product-firmware source has
been designated in this repository.

## CI firmware bundles and manual hardware verification

Each required ESP-IDF build also creates one artifact named
`firmware-esp-idf-<project-slug>-<version>-rev1_3`. The 12 direct projects and two
ESP-IDF releases therefore create 24 independently traceable bundles. The
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
`CONFIG_ESP32P4_SELECTS_REV_LESS_V3=y` and `CONFIG_ESP32P4_REV_MIN_100=y`; source
defaults are not accepted as evidence. The inner ZIP name and manifest also carry
`board_profile: rev1_3`, revision range `[1.0, 3.0)`, and
`c6_firmware_included: false`.

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
run for the final PR HEAD SHA that reports exactly the complete set of 24 unique,
unexpired expected firmware artifacts; partial dispatch runs are rejected. It
then downloads only the selected exact artifact, verifies the manifest identity,
checks every relative binary path, size, SHA-256, offset, overlap, and 32 MiB
flash boundary, then requires both a successful esptool exit code and
`Hash of data verified`. Before any artifact download or flash, it performs the
read-only `esptool chip_id` ESP32-P4 probe (using `chip-id` only as a compatibility
fallback), parses the silicon revision, and accepts only `< 3.0` for `rev1_3`.
Silicon `>= 3.0` maps to `rev3_x` and is refused because that product artifact is
not available. The silicon check does not replace PCB/electrical revision
confirmation. After each flash, the user must manually inspect the hardware and
type `PASS`; progress is profile-isolated local application data and resets for
a different final SHA, selected workflow run, profile, malformed/truncated
saved state, or legacy state schema. State writes use a same-directory temporary
file followed by an atomic replace or move.

These CI bundles are test outputs, not the checked-in factory firmware. The CI
build and integrity gates do not perform physical testing; all 24 hardware
checks remain an explicit user action.
