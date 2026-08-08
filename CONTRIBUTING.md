[简体中文](CONTRIBUTING_ZH.md) · [Repository home](README.md)

# Contributing

Contributions that preserve the product's evidenced hardware and framework
scope are welcome.

## Before opening a pull request

1. Start from the current default branch and keep unrelated work out of the
   change.
2. Identify every affected first-party example and framework line.
3. Do not add an Arduino surface, firmware build, or hardware feature that is
   not present in this repository.
4. Treat the checked-in factory binary as immutable unless the change is an
   explicitly reviewed release update.
5. Use local schematics or product hardware references for pin, BSP, display,
   touch, audio, SD, USB, camera, or hosted-transport changes.
6. Keep product-owned human-readable documentation paired in English and
   Simplified Chinese. Do not rewrite embedded upstream documentation.
7. Remove credentials, account data, actual device identifiers, and
   machine-specific paths from logs and public text.

## Static checks

Run the repository's lightweight checks before submitting:

~~~text
python .github/scripts/test_discover_esp_idf_examples.py
python .github/scripts/test_repository_policy.py
python .github/scripts/test_component_contracts.py
python .github/scripts/check_repository_policy.py
python .github/scripts/check_component_contracts.py
~~~

The required ESP-IDF product builds run in GitHub Actions against the exact pull
request head. The matrix covers every first-party example on the two versions
documented in [the CI contract](docs/CI.md).

## Pull request description

State:

- the problem and intended outcome;
- affected examples, components, and documentation;
- expected ESP-IDF matrix coverage;
- hardware/schematic evidence when hardware-facing behavior changes;
- factory-firmware or release-artifact impact;
- any compatibility range and the condition for revisiting it.

Use the repository pull request template and keep unresolved, evidence-backed
limitations visible.
