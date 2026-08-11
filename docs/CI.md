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
hardware behavior or factory-firmware compatibility.

## Changed-file routing

The repository policy job runs on every pull request. Expensive example builds
are selected from one complete, rename-aware Git diff.

| Changed path kind | Example build selection |
| --- | --- |
| Root, docs, schematic, governance, or example Markdown | None |
| Lightweight policy/maintenance helper, its test, Markdown-audit config, or `.gitignore` | None; run the lightweight policy gate with `docs_only=false` |
| Source or configuration inside one first-party example | That example only |
| Shared build configuration or the build workflow/discovery helper | All 12 |
| Firmware documentation, source, binary, or archive | None; report firmware/release scope separately |
| Complete but unfamiliar non-document path | All 12 and report the path |
| Empty, missing, or unreadable diff | Fail the policy job |

Firmware routing never authorizes rebuilding, repackaging, or changing the
factory image. A binary or archive change requires an explicit release review.

## Manual selection

The workflow dispatch input accepts:

- all;
- a unique example directory name, such as 04_wifistation;
- a repository-relative example path.

## Stable results

Every build job checks out the exact pull-request head SHA reported by the
policy job. The final ESP-IDF examples job remains visible even when a
documentation-only change correctly selects no product builds. New commits in
the same pull request cancel obsolete runs without affecting other branches or
release workflows.

The routing and Markdown/component-policy helpers have synthetic tests covering
documentation, direct source, shared inputs, firmware, rename/deletion,
unfamiliar paths, and incomplete diff data.

## CI firmware bundles and manual hardware verification

Each required ESP-IDF build also creates one artifact named
`firmware-esp-idf-<project-slug>-<version>`. The 12 direct projects and two
ESP-IDF releases therefore create 24 independently traceable bundles. The
bundle is generated from that build's `flasher_args.json`; it preserves the
actual offsets rather than assuming fixed ESP32-P4 offsets, and includes
`bin/**`, `manifest.json`, `metadata/flasher_args.json`, `flash.sh`, and
`flash.bat`.
The package preserves the build's validated flash mode, size, frequency, reset,
and stub settings as structured manifest data and uses them in every generated
flash command; unknown or unsafe esptool arguments are rejected. The bundled
`flash.sh` and `flash.bat` require one explicit port argument (`PORT` or `COMx`)
and never choose a device automatically.

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
run for the final PR HEAD SHA and the exact artifact name, verifies the manifest
identity, checks every relative binary path, size, SHA-256, offset, overlap, and
32 MiB flash boundary, then requires both a successful esptool exit code and
`Hash of data verified`. After each flash, the user must manually inspect the
hardware and type `PASS`; progress is local application data and automatically
resets for a different final SHA or invalid saved state.

These CI bundles are test outputs, not the checked-in factory firmware. The CI
build and integrity gates do not perform physical testing; all 24 hardware
checks remain an explicit user action.
