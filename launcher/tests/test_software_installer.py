from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from src.software_installer import _repair_macos_framework_symlinks, install_product


class SoftwareInstallerTests(unittest.TestCase):
    def test_zip_product_replaces_old_version_and_returns_executable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "WaveDAQ-macos-arm64-v2.0.0.zip"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("WaveDAQ.app/Contents/MacOS/WaveDAQ", "binary")
            data = root / "data"
            old = data / "products" / "wavedaq-8ch" / "macos-arm64" / "v1.0.0"
            old.mkdir(parents=True)
            (old / "old.app").write_text("old")
            with patch("src.software_installer.data_dir", return_value=data):
                target = install_product(package, "wavedaq-8ch", "macos-arm64", "v2.0.0")
            self.assertEqual(target, data / "products" / "wavedaq-8ch" / "macos-arm64" / "v2.0.0" / "WaveDAQ.app")
            self.assertTrue(target.exists())
            self.assertFalse(old.exists())

    def test_zip_product_preserves_macos_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "product.zip"
            link = zipfile.ZipInfo("Product.app/Contents/Frameworks/Python")
            link.create_system = 3
            link.external_attr = (0o120777 << 16) | 0xA000
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr(link, "Python.framework/Versions/3.11/Python")
                archive.writestr("Product.app/Contents/Frameworks/Python.framework/Versions/3.11/Python", "binary")
            destination = root / "extracted"
            from src.software_installer import _safe_extract_zip
            _safe_extract_zip(package, destination)
            extracted = destination / "Product.app/Contents/Frameworks/Python"
            self.assertTrue(extracted.is_symlink())
            self.assertEqual(extracted.readlink(), Path("Python.framework/Versions/3.11/Python"))

    def test_zip_product_rejects_traversal_and_symlink_parent_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "unsafe.zip"
            link = zipfile.ZipInfo("Product.app/Contents/Frameworks/outside")
            link.create_system = 3
            link.external_attr = (0o120777 << 16) | 0xA000
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr(link, "../../outside")
                archive.writestr("Product.app/Contents/Frameworks/outside/payload", "bad")
            with self.assertRaises(RuntimeError):
                from src.software_installer import _safe_extract_zip
                _safe_extract_zip(package, root / "extracted")

            traversal = root / "traversal.zip"
            with zipfile.ZipFile(traversal, "w") as archive:
                archive.writestr("../../outside.txt", "bad")
            with self.assertRaises(RuntimeError):
                _safe_extract_zip(traversal, root / "traversal-extracted")

    def test_repairs_flattened_links_across_frameworks_and_resources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / "Product.app"
            frameworks = app / "Contents" / "Frameworks"
            resources = app / "Contents" / "Resources"
            (frameworks / "Python.framework" / "Versions" / "3.11").mkdir(parents=True)
            resources.mkdir(parents=True)
            (frameworks / "Python.framework" / "Versions" / "3.11" / "Python").write_bytes(b"binary")
            (frameworks / "Python").write_text("Python.framework/Versions/3.11/Python")
            (frameworks / "base_library.zip").write_text("../Resources/base_library.zip")
            (resources / "base_library.zip").write_bytes(b"zip")
            (resources / "Python.framework").write_text("../Frameworks/Python.framework")

            _repair_macos_framework_symlinks(app)

            self.assertTrue((frameworks / "Python").is_symlink())
            self.assertTrue((frameworks / "base_library.zip").is_symlink())
            self.assertTrue((resources / "Python.framework").is_symlink())


if __name__ == "__main__":
    unittest.main()
