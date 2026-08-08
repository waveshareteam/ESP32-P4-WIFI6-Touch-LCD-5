[简体中文](CI_ZH.md) · [Documentation index](README.md)

# CI discovery and routing

The ESP-IDF workflow validates the 12 first-party projects directly below
[examples/esp-idf](../examples/esp-idf/). Embedded component test applications
and the checked-in factory firmware are inventoried separately and are not
silently promoted into the product-example matrix.

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
