from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import device_identity, local_crypto, local_storage


class LocalStorageTests(unittest.TestCase):
    def test_revoked_license_is_removed_and_can_be_reactivated(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(local_storage, "data_dir", return_value=Path(directory)):
            document = {"license_id": "lic_test", "signature": "test"}
            local_storage.save_license(document)
            local_storage.save_catalog("lic_test", {"products": [], "releases": []})

            local_storage.mark_license_revoked("lic_test")

            self.assertEqual(local_storage.load_licenses(), [])
            self.assertFalse((Path(directory) / "license.json").exists())
            with self.assertRaisesRegex(RuntimeError, "撤销或解绑"):
                local_storage.set_active_license("lic_test")

            local_storage.save_license(document)
            self.assertEqual(local_storage.load_licenses(), [document])
            self.assertNotIn("lic_test", local_storage.load_revoked_license_ids())

    def test_corrupt_json_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.json"
            path.write_text("not-json", encoding="utf-8")
            self.assertIsNone(local_storage.read_json(path))

    def test_machine_code_change_allows_recovery_of_old_local_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(local_storage, "data_dir", return_value=Path(directory)):
            root = Path(directory)
            local_storage.write_json(root / "device.json", {"device_id": "dev_old"})
            local_storage.save_license({"license_id": "lic_old"})
            local_storage.save_catalog("lic_old", {"products": []})
            local_storage.write_protected_json(root / "installations.json", {"installations": []})
            (root / "downloads").mkdir()
            (root / "downloads" / "package.zip").write_text("package", encoding="utf-8")

            with patch.object(local_crypto, "machine_code", return_value="changed-machine"):
                self.assertEqual(local_storage.load_licenses(), [])
                self.assertEqual(local_storage.load_catalogs(), {})
                self.assertEqual(local_storage.load_installations(), [])
                backup = local_storage.backup_and_reset_binding()
                self.assertTrue((backup / "device.json").exists())
                self.assertTrue((backup / "license.json").exists())
                self.assertTrue((backup / "licenses" / "lic_old.json").exists())
                self.assertTrue((backup / "installations.json").exists())
                self.assertFalse((root / "device.json").exists())
                self.assertEqual((root / "downloads" / "package.zip").read_text(encoding="utf-8"), "package")
                local_storage.save_license({"license_id": "lic_new"})
                self.assertEqual(local_storage.load_licenses(), [{"license_id": "lic_new"}])

    def test_reset_creates_a_new_device_after_machine_code_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(local_storage, "data_dir", return_value=Path(directory)), patch.object(device_identity, "data_dir", return_value=Path(directory)):
            with patch.object(local_crypto, "machine_code", return_value="original-machine"):
                old_identity = device_identity.load_or_create()
            with patch.object(local_crypto, "machine_code", return_value="changed-machine"):
                with self.assertRaisesRegex(RuntimeError, "设备机器码不匹配"):
                    device_identity.load_or_create()
                backup = local_storage.backup_and_reset_binding()
                new_identity = device_identity.load_or_create()
                self.assertNotEqual(old_identity["device_id"], new_identity["device_id"])
                self.assertTrue((backup / "device.json").exists())


if __name__ == "__main__":
    unittest.main()
