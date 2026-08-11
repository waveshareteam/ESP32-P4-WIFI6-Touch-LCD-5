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
    def package(self, root: Path, files: dict[str, str], version: str = "v5.5.5", write_args: object | None = None) -> Path:
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
            "extra_esptool_args": {"chip": "esp32p4", "before": "default_reset", "after": "hard_reset", "stub": False},
        }
        (root / build / "flasher_args.json").write_text(json.dumps(payload), encoding="utf-8")
        with mock.patch.dict(os.environ, {"PACKAGE_GIT_SHA": "a" * 40}, clear=False):
            old_cwd = Path.cwd()
            os.chdir(root)
            try:
                return packager.package_esp_idf(project, build, version, Path("out"))
            finally:
                os.chdir(old_cwd)

    def test_bundle_has_required_members_identity_ranges_and_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = self.package(root, {"bootloader/bootloader.bin": "boot", "demo.bin": "application"})
            with zipfile.ZipFile(root / bundle) as archive:
                self.assertEqual(set(archive.namelist()), {"bin/bootloader.bin", "bin/demo.bin", "metadata/flasher_args.json", "manifest.json", "flash.sh", "flash.bat"})
                manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["board"], "ESP32-P4-WIFI6-Touch-LCD-5")
            self.assertEqual(manifest["chip"], "esp32p4")
            self.assertEqual(manifest["source_project"], "examples/esp-idf/01_Demo")
            self.assertEqual(manifest["flash"]["flash_limit_bytes"], 32 * 1024 * 1024)
            self.assertEqual(manifest["flash"]["write_flash_args"], [{"option": "--flash_mode", "value": "dio"}, {"option": "--flash_size", "value": "32MB"}, {"option": "--flash_freq", "value": "80m"}])
            self.assertFalse(manifest["flash"]["extra_esptool_args"]["stub"])
            self.assertEqual([item["offset"] for item in manifest["files"]], ["0x0", "0x10000"])
            self.assertEqual(manifest["files"][1]["sha256"], hashlib.sha256(b"application").hexdigest())

    def test_hyphenated_idf6_write_args_are_preserved_in_manifest_and_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = self.package(root, {"bootloader/bootloader.bin": "boot", "demo.bin": "application"}, "v6.0.2", {"--flash-mode": "qio", "--flash-size": "16MB", "--flash-freq": "40m"})
            with zipfile.ZipFile(root / bundle) as archive:
                manifest = json.loads(archive.read("manifest.json"))
                shell = archive.read("flash.sh").decode("utf-8")
                batch = archive.read("flash.bat").decode("utf-8")
            self.assertEqual([entry["option"] for entry in manifest["flash"]["write_flash_args"]], ["--flash-mode", "--flash-size", "--flash-freq"])
            for text in (manifest["flash"]["command"], shell, batch):
                self.assertIn("--before default_reset --after hard_reset --no-stub write_flash", text)
                self.assertIn("--flash-mode qio --flash-size 16MB --flash-freq 40m", text)
            self.assertIn("--port PORT", manifest["flash"]["command"])
            self.assertIn('Usage: $0 PORT', shell)
            self.assertIn('Usage: %~nx0 COMx', batch)

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
                            packager.package_esp_idf(project, build, "v5.5.5", Path("out"))
                    finally:
                        os.chdir(old_cwd)

    def test_packager_refuses_incomplete_sha_and_absolute_project(self) -> None:
        with mock.patch.dict(os.environ, {"PACKAGE_GIT_SHA": "short"}, clear=False):
            with self.assertRaises(ValueError):
                packager.manifest_git_sha()
        with self.assertRaises(ValueError):
            packager.relative_source_project(Path("C:/not-a-repository-project"))


class ContractTests(unittest.TestCase):
    def test_24_artifacts_match_direct_project_inventory(self) -> None:
        flasher = (REPO_ROOT / "scripts/Flash-CI-Firmware.ps1").read_text(encoding="utf-8")
        direct = sorted(path.name for path in (REPO_ROOT / "examples/esp-idf").iterdir() if (path / "CMakeLists.txt").is_file() and (path / "main").is_dir())
        self.assertEqual(len(direct), 12)
        self.assertIn('$Items.Count -ne 24', flasher)
        for project in direct:
            self.assertIn(f"'examples/esp-idf/{project}'", flasher)
        self.assertIn('Artifact = "firmware-esp-idf-$slug-$version"', flasher)
        self.assertIn("@('v5.5.5', 'v6.0.2')", flasher)
        workflow = (REPO_ROOT / ".github/workflows/esp-idf-examples.yml").read_text(encoding="utf-8")
        self.assertIn('actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a', workflow)
        self.assertIn('name: firmware-esp-idf-${{ matrix.project_slug }}-${{ matrix.idf_version }}', workflow)

    def test_flasher_static_safety_contract(self) -> None:
        flasher = (REPO_ROOT / "scripts/Flash-CI-Firmware.ps1").read_text(encoding="utf-8")
        self.assertIn('Port is required in normal mode', flasher)
        self.assertNotIn('Get-CimInstance', flasher)
        self.assertIn('status --porcelain=v1 --untracked-files=all', flasher)
        self.assertIn('symbolic-ref --quiet --short HEAD', flasher)
        self.assertIn('pr list --repo $Repo --head $Branch --state open', flasher)
        self.assertIn('--commit $FinalSha --status success', flasher)
        self.assertIn('run download $Run --repo $Repo --name $Item.Artifact', flasher)
        self.assertIn("Hash of data verified", flasher)
        self.assertIn("$FlashLimit = 32MB", flasher)
        self.assertIn("overlapping flash ranges", flasher)
        self.assertLess(flasher.index('if ($SelfTest)'), flasher.index('Resolve-Git'))
        self.assertLess(flasher.index('if ($ListOnly)'), flasher.index('Resolve-Git'))
        self.assertIn("state-v1.json", flasher)
        self.assertIn("Test-ManifestFlashArguments", flasher)
        self.assertIn("--no-stub", flasher)
        self.assertIn("Test-CompletedState", flasher)
        self.assertLess(flasher.index('if (Test-CompletedState $state)'), flasher.index('$Run = Resolve-ArtifactRun'))
        self.assertLess(flasher.index('if (Test-CompletedState $state)'), flasher.index('Invoke-CurrentFlash $item'))


if __name__ == "__main__":
    unittest.main()
