from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_SHA = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
FQBN = (
    "esp32:esp32:esp32p4:ChipVariant=postv3,PSRAM=enabled,FlashSize=32M,"
    "FlashMode=qio,FlashFreq=80,PartitionScheme=app13M_data7M_32MB,"
    "UploadMode=default,UploadSpeed=921600"
)
ARTIFACT = "ESP32-P4-WIFI6-Touch-LCD-5-01_HelloWorld-arduino-3.3.11"

import importlib.util  # noqa: E402


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


packager = load_module("lcd5_arduino_packager", ROOT / "releases" / "package_arduino_firmware.py")
validator = load_module("lcd5_arduino_validator", ROOT / "releases" / "validate_arduino_firmware.py")


class ArduinoFirmwarePackagingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.build = self.root / "build"
        self.output = self.root / "output"
        self.project = ROOT / "examples" / "arduino" / "examples" / "01_HelloWorld"
        self.write_build()

    def write_build(self) -> None:
        if self.build.exists():
            shutil.rmtree(self.build)
        self.build.mkdir(parents=True)
        payloads = {
            "01_HelloWorld.ino.bootloader.bin": b"B" * 64,
            "01_HelloWorld.ino.partitions.bin": b"P" * 32,
            "boot_app0.bin": b"O" * 48,
            "01_HelloWorld.ino.bin": b"A" * 128,
        }
        for name, payload in payloads.items():
            (self.build / name).write_bytes(payload)
        (self.build / "flash_args").write_text(
            "--flash-mode dio --flash-freq 80m --flash-size 32MB\n"
            "0x2000 01_HelloWorld.ino.bootloader.bin\n"
            "0x8000 01_HelloWorld.ino.partitions.bin\n"
            "0xe000 boot_app0.bin\n"
            "0x10000 01_HelloWorld.ino.bin\n",
            encoding="utf-8",
        )
        (self.build / "build.options.json").write_text(
            json.dumps({"fqbn": FQBN, "sketchLocation": str(self.project)}, separators=(",", ":")),
            encoding="utf-8",
        )

    def args(self, **overrides: object) -> argparse.Namespace:
        values: dict[str, object] = {
            "project": "examples/arduino/examples/01_HelloWorld",
            "build_dir": str(self.build),
            "output_dir": str(self.output),
            "name": ARTIFACT,
            "framework_version": "3.3.11",
            "target": "esp32p4",
            "fqbn": FQBN,
            "git_sha": PRODUCT_SHA,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def package(self, **overrides: object) -> Path:
        with mock.patch.object(packager, "require_trusted_current_repo", return_value=ROOT):
            return packager.package(self.args(**overrides))

    def validate(self, archive: Path, **overrides: object) -> dict[str, object]:
        args = argparse.Namespace(
            archive=str(archive),
            project="examples/arduino/examples/01_HelloWorld",
            build_dir=str(self.build),
            name=ARTIFACT,
            framework_version="3.3.11",
            target="esp32p4",
            fqbn=FQBN,
            git_sha=PRODUCT_SHA,
        )
        for key, value in overrides.items():
            setattr(args, key, value)
        with mock.patch.object(validator, "CURRENT_REPO_ROOT", ROOT):
            with mock.patch.object(validator, "derive_current_repo_root", return_value=ROOT):
                return validator.validate_archive(args)

    def members(self, archive: Path) -> dict[str, bytes]:
        with zipfile.ZipFile(archive) as zf:
            return {info.filename: zf.read(info) for info in zf.infolist() if not info.is_dir()}

    def rewrite(self, archive: Path, mutations: dict[str, bytes], name: str) -> Path:
        members = self.members(archive)
        for member, data in mutations.items():
            members[member] = data
        target = self.root / name / archive.name
        target.parent.mkdir(parents=True)
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for member, data in members.items():
                info = zipfile.ZipInfo(member)
                if member.endswith(".sh"):
                    info.create_system = 3
                    info.external_attr = (stat.S_IFREG | 0o755) << 16
                zf.writestr(info, data)
        return target

    def manifest_member(self, archive: Path) -> str:
        return next(name for name in self.members(archive) if name.endswith("/manifest.json"))

    def test_package_and_independent_validation_roundtrip(self) -> None:
        archive = self.package()
        self.assertTrue(archive.name.endswith("-segments.zip"))
        summary = self.validate(archive)
        self.assertEqual("external-build-evidence-reconstructed", summary["validation"])
        self.assertEqual(PRODUCT_SHA, summary["product_git_sha"])
        self.assertEqual(4, summary["segment_count"])
        members = self.members(archive)
        self.assertFalse(any("merged" in name.lower() or "combined" in name.lower() for name in members))
        self.assertFalse(any(name.endswith("build.options.json") for name in members))
        manifest = json.loads(members[self.manifest_member(archive)])
        self.assertFalse(manifest["bsp"]["linked"])
        self.assertEqual("e2aff2b2f0d6d3ec93c4897690c64c635e603fca", manifest["bsp"]["sha"])

    def test_packager_rejects_missing_metadata_and_fqbn_mismatch(self) -> None:
        (self.build / "flash_args").unlink()
        with self.assertRaises(FileNotFoundError):
            self.package()
        self.write_build()
        options = json.loads((self.build / "build.options.json").read_text())
        options["fqbn"] = FQBN + ",DebugLevel=verbose"
        (self.build / "build.options.json").write_text(json.dumps(options))
        with self.assertRaisesRegex(ValueError, "exactly equal"):
            self.package()

    def test_packager_rejects_merged_and_wrong_project_identity(self) -> None:
        self.write_build()
        (self.build / "HelloWorld.ino.merged.bin").write_bytes(b"M" * 64)
        (self.build / "flash_args").write_text(
            (self.build / "flash_args").read_text().replace(
                "0x10000 01_HelloWorld.ino.bin", "0x10000 HelloWorld.ino.merged.bin"
            ),
            encoding="utf-8",
        )
        with self.assertRaises(ValueError):
            self.package()
        self.write_build()
        with self.assertRaisesRegex(ValueError, "sketchLocation"):
            self.package(project="examples/arduino/examples/03_Drawing_board")

    def test_validator_rejects_segment_and_helper_tampering(self) -> None:
        archive = self.package()
        members = self.members(archive)
        segment = next(name for name in members if name.endswith("/bin/0x10000-01_HelloWorld.ino.bin"))
        self.assertRaisesRegex = None
        for label, mutations in (
            ("segment", {segment: members[segment] + b"tamper"}),
            ("helper", {
                next(n for n in members if n.endswith("/flash_args.txt")):
                members[next(n for n in members if n.endswith("/flash_args.txt"))] + b" --evil"
            }),
            ("manifest", {
                self.manifest_member(archive):
                json.dumps({**json.loads(members[self.manifest_member(archive)]), "segmented_payload_total": 1}).encode()
            }),
            ("privacy", {
                next(n for n in members if n.endswith("/README.md")):
                members[next(n for n in members if n.endswith("/README.md"))] + b"\nbuilt at /home/alice/x\n"
            }),
        ):
            with self.subTest(label=label):
                tampered = self.rewrite(archive, mutations, label)
                with self.assertRaises(ValueError):
                    self.validate(tampered)

    def test_validator_rejects_merged_member_and_raw_options(self) -> None:
        archive = self.package()
        members = self.members(archive)
        root = Path(self.manifest_member(archive)).parent.as_posix()
        for label, extra in (
            ("merged", {f"{root}/bin/whole.merged.bin": b"M"}),
            ("raw-options", {f"{root}/metadata/build.options.json": b"{}\n"}),
        ):
            with self.subTest(label=label):
                tampered = self.rewrite(archive, extra, label)
                with self.assertRaises(ValueError):
                    self.validate(tampered)

    def test_validator_binds_checkout_head(self) -> None:
        archive = self.package()
        with self.assertRaisesRegex(ValueError, "product Git SHA"):
            self.validate(archive, git_sha="0" * 40)

    def test_packager_requires_exact_fqbn_and_artifact_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "FQBN"):
            self.package(fqbn=FQBN + ",DebugLevel=verbose")
        with self.assertRaisesRegex(ValueError, "artifact name"):
            self.package(name="ESP32-P4-WIFI6-Touch-LCD-5-99_Other-arduino-3.3.11")


if __name__ == "__main__":
    unittest.main()
