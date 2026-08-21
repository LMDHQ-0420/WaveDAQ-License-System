from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import local_storage


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


if __name__ == "__main__":
    unittest.main()
