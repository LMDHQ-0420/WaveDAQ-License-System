from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from src.software_installer import install_product


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


if __name__ == "__main__":
    unittest.main()
