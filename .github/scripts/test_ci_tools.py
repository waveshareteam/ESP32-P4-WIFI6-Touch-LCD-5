from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


packager = load_module("p4_firmware_packager", REPO_ROOT / "releases/package_firmware.py")


class PackageTests(unittest.TestCase):
    def package(self, root: Path, files: dict[str, str], version: str = "v5.5.5", write_args: object | None = None, extra_args: object | None = None, sdkconfig: object | None = None, profile: str = "rev1_3") -> Path:
        project = Path("examples/esp-idf/01_Demo")
        build = project / "build"
        for relative, content in files.items():
            path = root / build / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode("utf-8"))
        flash_files = {"0x0": "bootloader/bootloader.bin", "0x10000": "demo.bin"}
        payload = {
            "flash_files": flash_files,
            "write_flash_args": ["--flash_mode", "dio", "--flash_size", "32MB", "--flash_freq", "80m"] if write_args is None else write_args,
            "extra_esptool_args": {"chip": "esp32p4", "before": "default_reset", "after": "hard_reset", "stub": False} if extra_args is None else extra_args,
        }
        (root / build / "flasher_args.json").write_text(json.dumps(payload), encoding="utf-8")
        config = root / build / "config"
        config.mkdir(parents=True, exist_ok=True)
        default_config = {"ESP32P4_SELECTS_REV_LESS_V3": profile == "rev1_3", "ESP32P4_REV_MIN_100": profile == "rev1_3", "ESP32P4_REV_MIN_300": profile == "rev3_x"}
        (config / "sdkconfig.json").write_text(json.dumps(default_config if sdkconfig is None else sdkconfig), encoding="utf-8")
        with mock.patch.dict(os.environ, {"PACKAGE_GIT_SHA": "a" * 40}, clear=False):
            old_cwd = Path.cwd()
            os.chdir(root)
            try:
                return packager.package_esp_idf(project, build, version, Path("out"), profile)
            finally:
                os.chdir(old_cwd)

    def test_bundle_has_required_members_identity_ranges_and_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = self.package(root, {"bootloader/bootloader.bin": "boot", "demo.bin": "application"})
            with zipfile.ZipFile(root / bundle) as archive:
                self.assertEqual(set(archive.namelist()), {"bin/bootloader.bin", "bin/demo.bin", "metadata/flasher_args.json", "manifest.json"})
                manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["board"], "ESP32-P4-WIFI6-Touch-LCD-5")
            self.assertEqual(manifest["chip"], "esp32p4")
            self.assertEqual(manifest["board_profile"], "rev1_3")
            self.assertEqual(manifest["chip_revision"], {"minimum": "1.0", "maximum_exclusive": "3.0"})
            self.assertFalse(manifest["c6_firmware_included"])
            self.assertEqual(manifest["source_project"], "examples/esp-idf/01_Demo")
            self.assertEqual(manifest["flash"]["flash_limit_bytes"], 32 * 1024 * 1024)
            self.assertEqual(manifest["flash"]["write_flash_args"], [{"option": "--flash_mode", "value": "dio"}, {"option": "--flash_size", "value": "32MB"}, {"option": "--flash_freq", "value": "80m"}])
            self.assertFalse(manifest["flash"]["extra_esptool_args"]["stub"])
            self.assertEqual([item["offset"] for item in manifest["files"]], ["0x0", "0x10000"])
            self.assertEqual(manifest["files"][1]["sha256"], hashlib.sha256(b"application").hexdigest())
            self.assertTrue(bundle.name.endswith("-rev1_3.zip"))

    def test_both_revision_profiles_have_distinct_manifest_ranges(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = self.package(root, {"bootloader/bootloader.bin": "boot", "demo.bin": "application"}, profile="rev3_x")
            with zipfile.ZipFile(root / bundle) as archive:
                manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["board_profile"], "rev3_x")
            self.assertEqual(manifest["chip_revision"], {"minimum": "3.0", "maximum_exclusive": "4.0"})
            self.assertTrue(bundle.name.endswith("-rev3_x.zip"))

    def test_requires_generated_rev1_3_config_and_accepts_text_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValueError):
                self.package(root, {"bootloader/bootloader.bin": "boot", "demo.bin": "application"}, sdkconfig={"ESP32P4_SELECTS_REV_LESS_V3": False, "ESP32P4_REV_MIN_100": True})
            with self.assertRaises(ValueError):
                self.package(root, {"bootloader/bootloader.bin": "boot", "demo.bin": "application"}, sdkconfig={})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = Path("examples/esp-idf/01_Demo"); build = project / "build"
            for relative in ("bootloader/bootloader.bin", "demo.bin"):
                path = root / build / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b"ok")
            (root / build / "flasher_args.json").write_text(json.dumps({"flash_files": {"0x0": "bootloader/bootloader.bin", "0x10000": "demo.bin"}, "write_flash_args": ["--flash_mode", "dio", "--flash_size", "32MB", "--flash_freq", "80m"], "extra_esptool_args": {"chip": "esp32p4", "before": "default_reset", "after": "hard_reset", "stub": False}}), encoding="utf-8")
            (root / build / "sdkconfig").write_text("CONFIG_ESP32P4_SELECTS_REV_LESS_V3=y\nCONFIG_ESP32P4_REV_MIN_100=y\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"PACKAGE_GIT_SHA": "a" * 40}, clear=False):
                old_cwd = Path.cwd(); os.chdir(root)
                try:
                    self.assertTrue(packager.package_esp_idf(project, build, "v5.5.5", Path("out"), "rev1_3").is_file())
                finally:
                    os.chdir(old_cwd)

    def test_hyphenated_idf6_write_args_are_preserved_without_flash_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = self.package(root, {"bootloader/bootloader.bin": "boot", "demo.bin": "application"}, "v6.0.2", {"--flash-mode": "qio", "--flash-size": "16MB", "--flash-freq": "40m"}, {"chip": "esp32p4", "before": "default-reset", "after": "hard-reset", "stub": False})
            with zipfile.ZipFile(root / bundle) as archive:
                manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual([entry["option"] for entry in manifest["flash"]["write_flash_args"]], ["--flash-mode", "--flash-size", "--flash-freq"])
            self.assertEqual(set(archive.namelist()) & {"flash.sh", "flash.bat"}, set())
            self.assertNotIn("command", manifest["flash"])

    def test_rejects_unknown_or_injected_flash_arguments(self) -> None:
        for write_args in (
            [],
            ["--flash_mode", "dio", "--flash_size", "32MB"],
            ["--flash_mode", "dio", "--flash_freq", "80m"],
            ["--flash_size", "32MB", "--flash_freq", "80m"],
            ["--flash_mode", "dio", "--erase-all", "1"],
            ["--flash-mode", "dio;rm -rf /"],
            ["--flash_mode", "dio", "--flash-mode", "qio"],
            ["--flash_mode"],
        ):
            with self.subTest(write_args=write_args), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                with self.assertRaises(ValueError):
                    self.package(root, {"bootloader/bootloader.bin": "boot", "demo.bin": "application"}, write_args=write_args)

    def test_rejects_non_generated_extra_esptool_reset_values(self) -> None:
        for before, after in (
            ("soft_reset", "hard_reset"),
            ("soft-reset", "hard-reset"),
            ("usb_reset", "hard_reset"),
            ("usb-reset", "hard-reset"),
            ("default_reset; injected", "hard_reset"),
            ("default-reset", "unknown"),
        ):
            with self.subTest(before=before, after=after), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                with self.assertRaises(ValueError):
                    self.package(root, {"bootloader/bootloader.bin": "boot", "demo.bin": "application"}, extra_args={"chip": "esp32p4", "before": before, "after": after, "stub": False})

    def test_rejects_escape_overlap_and_32mib_overflow(self) -> None:
        for flash_files, contents in (
            ({"0x0": "../escape.bin"}, {"demo.bin": "ok"}),
            ({"0x0": "boot.bin", "0x1": "app.bin"}, {"boot.bin": "xx", "app.bin": "xx"}),
            ({hex(32 * 1024 * 1024 - 1): "app.bin"}, {"app.bin": "xx"}),
        ):
            with self.subTest(flash_files=flash_files), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); project = Path("examples/esp-idf/01_Demo"); build = project / "build"
                for name, content in contents.items():
                    path = root / build / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content, encoding="utf-8")
                (root / build / "flasher_args.json").write_text(json.dumps({"flash_files": flash_files, "write_flash_args": [], "extra_esptool_args": {"chip": "esp32p4", "before": "default_reset", "after": "hard_reset", "stub": True}}), encoding="utf-8")
                with mock.patch.dict(os.environ, {"PACKAGE_GIT_SHA": "a" * 40}, clear=False):
                    old_cwd = Path.cwd(); os.chdir(root)
                    try:
                        with self.assertRaises((ValueError, FileNotFoundError)):
                            packager.package_esp_idf(project, build, "v5.5.5", Path("out"), "rev1_3")
                    finally:
                        os.chdir(old_cwd)

    def test_packager_refuses_incomplete_sha_and_absolute_project(self) -> None:
        with mock.patch.dict(os.environ, {"PACKAGE_GIT_SHA": "short"}, clear=False):
            with self.assertRaises(ValueError):
                packager.manifest_git_sha()
        with self.assertRaises(ValueError):
            packager.relative_source_project(Path("C:/not-a-repository-project"))


class ContractTests(unittest.TestCase):
    def test_release_review_gate_invokes_the_executable_helper_without_bypass(self) -> None:
        workflow = (REPO_ROOT / ".github/workflows/esp-idf-examples.yml").read_text(encoding="utf-8")
        self.assertIn("python .github/scripts/test_evaluate_ci_result.py", workflow)
        self.assertIn("python .github/scripts/evaluate_ci_result.py", workflow)
        self.assertIn('--validate-result "$VALIDATE_RESULT"', workflow)
        self.assertIn('--has-examples "$HAS_EXAMPLES"', workflow)
        self.assertIn('--build-result "$BUILD_RESULT"', workflow)
        self.assertIn("RELEASE_REVIEW: ${{ needs.validate.outputs.release_review }}", workflow)
        self.assertIn('--release-review "$RELEASE_REVIEW"', workflow)
        self.assertIn('--head-sha "$VALIDATED_HEAD_SHA"', workflow)
        self.assertIn("if: ${{ always() }}", workflow)
        self.assertIn(
            "name: ${{ github.event_name == 'workflow_dispatch' && 'ESP-IDF examples (manual)' || 'ESP-IDF examples' }}",
            workflow,
        )
        self.assertIn("  result:\n", workflow)
        self.assertIn("    needs:\n      - validate\n      - build\n", workflow)
        result_job = workflow[workflow.index("  result:\n") :]
        checkout_step = """      - name: Checkout validated head for result evaluation
        if: ${{ needs.validate.result == 'success' }}
        uses: actions/checkout@v4
        with:
          ref: ${{ needs.validate.outputs.head_sha }}
          persist-credentials: false
"""
        helper_step = """      - name: Require the selected validation
        if: ${{ always() }}
"""
        self.assertIn(checkout_step, result_job)
        self.assertIn(helper_step, result_job)
        self.assertLess(result_job.index(checkout_step), result_job.index(helper_step))
        self.assertNotIn("release_update", workflow)
        self.assertNotIn("release_authorization", workflow)
        self.assertNotIn("github.event.pull_request.labels", workflow)
        self.assertNotIn("requested_reviewers", workflow)
        self.assertNotIn("github.token", workflow)

    def test_48_artifacts_match_direct_project_inventory(self) -> None:
        flasher = (REPO_ROOT / "scripts/Flash-CI-Firmware.ps1").read_text(encoding="utf-8")
        direct = sorted(path.name for path in (REPO_ROOT / "examples/esp-idf").iterdir() if (path / "CMakeLists.txt").is_file() and (path / "main").is_dir())
        self.assertEqual(len(direct), 12)
        self.assertIn('$Items.Count -ne 48', flasher)
        for project in direct:
            self.assertIn(f"'examples/esp-idf/{project}'", flasher)
        self.assertIn("@('v5.5.5', 'v6.0.2')", flasher)
        workflow = (REPO_ROOT / ".github/workflows/esp-idf-examples.yml").read_text(encoding="utf-8")
        self.assertIn('actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a', workflow)
        self.assertIn('Artifact = "firmware-esp-idf-$slug-$version-$profile"', flasher)
        self.assertIn("@('rev1_3', 'rev3_x')", flasher)
        self.assertIn("rev3_x = [pscustomobject]@{ Minimum = '3.0'; MaximumExclusive = '4.0' }", flasher)
        self.assertIn('--board-profile "${{ matrix.profile }}"', workflow)
        self.assertIn('name: firmware-esp-idf-${{ matrix.project_slug }}-${{ matrix.idf_version }}-${{ matrix.profile }}', workflow)

    def test_flasher_static_safety_contract(self) -> None:
        flasher = (REPO_ROOT / "scripts/Flash-CI-Firmware.ps1").read_text(encoding="utf-8")
        self.assertIn('Port is required in normal mode', flasher)
        self.assertNotIn('Get-CimInstance', flasher)
        self.assertIn('status --porcelain=v1 --untracked-files=all', flasher)
        self.assertIn('symbolic-ref --quiet --short HEAD', flasher)
        self.assertIn('pr list --repo $Repo --head $Branch --state open', flasher)
        self.assertIn('--commit $FinalSha --status success', flasher)
        self.assertIn('run download $Run --repo $Repo --name $Item.Artifact', flasher)
        self.assertIn('chip_id', flasher)
        self.assertIn('chip-id', flasher)
        self.assertIn('ConvertFrom-EsptoolProbe', flasher)
        self.assertIn('Silicon revision does not replace PCB/electrical revision confirmation.', flasher)
        self.assertIn('board_profile -ne $Item.Profile', flasher)
        self.assertIn('c6_firmware_included', flasher)
        self.assertIn("Hash of data verified", flasher)
        self.assertIn("$FlashLimit = 32MB", flasher)
        self.assertIn("overlapping flash ranges", flasher)
        self.assertLess(flasher.index('if ($SelfTest)'), flasher.index('Resolve-Git'))
        self.assertLess(flasher.index('if ($ListOnly)'), flasher.index('Resolve-Git'))
        self.assertIn("state-v3-$Profile.json", flasher)
        self.assertIn("SchemaVersion = 3", flasher)
        self.assertIn("Get-StateForArtifactRun", flasher)
        self.assertIn("[string]$Saved.RunId -ne $RunId", flasher)
        self.assertIn("ConvertFrom-StateJson", flasher)
        self.assertIn("Get-StateTempPath", flasher)
        self.assertIn("[System.IO.File]::Replace($temporaryPath, $StatePath, $null)", flasher)
        self.assertIn("[System.IO.File]::Move($temporaryPath, $StatePath)", flasher)
        self.assertIn("Remove-Item -LiteralPath $temporaryPath -Force", flasher)
        self.assertIn("Test-ArtifactInventory", flasher)
        self.assertIn("$expected.Count -ne 48", flasher)
        self.assertIn('$GhExe api --method GET "repos/$Repo/actions/runs/$($run.databaseId)/artifacts?per_page=100"', flasher)
        self.assertIn("repos/$Repo/actions/runs/$($run.databaseId)/artifacts?per_page=100", flasher)
        self.assertIn("exactly the 48 expected unique, unexpired firmware artifacts", flasher)
        self.assertIn("Test-ManifestFlashArguments", flasher)
        self.assertIn("--no-stub", flasher)
        self.assertIn("Test-CompletedState", flasher)
        self.assertIn("$ProfileItems = @($Items | Where-Object { $_.Profile -eq $DetectedProfile })", flasher)
        self.assertIn("$ProfileItems.Count -ne 24", flasher)
        self.assertLess(flasher.index('$Run = Resolve-ArtifactRun'), flasher.index('$state = Read-State $FinalSha $DetectedProfile $Run'))
        self.assertLess(flasher.index('$state = Read-State $FinalSha $DetectedProfile $Run'), flasher.index('if (Test-CompletedState $state $ProfileItems.Count)'))
        self.assertLess(flasher.index('if (Test-CompletedState $state $ProfileItems.Count)'), flasher.index('Invoke-CurrentFlash $item'))
        self.assertLess(flasher.index('Invoke-EsptoolProbe $PythonExe $Port'), flasher.index('Resolve-ArtifactRun $GhExe $FinalSha'))
        self.assertLess(flasher.index('Invoke-EsptoolProbe $PythonExe $Port', flasher.index('function Invoke-CurrentFlash')), flasher.index('run download $Run --repo $Repo --name $Item.Artifact'))
        self.assertNotIn('erase_flash', flasher)
        for document in (REPO_ROOT / "docs/CI.md", REPO_ROOT / "docs/CI_ZH.md"):
            text = document.read_text(encoding="utf-8")
            self.assertNotIn("flash.sh", text)
            self.assertNotIn("flash.bat", text)
            self.assertIn("Flash-CI-Firmware.cmd", text)
        cmd_wrapper = (REPO_ROOT / 'Flash-CI-Firmware.cmd').read_text(encoding='utf-8')
        self.assertIn(r'%~dp0scripts\Flash-CI-Firmware.ps1', cmd_wrapper)


if __name__ == "__main__":
    unittest.main()
