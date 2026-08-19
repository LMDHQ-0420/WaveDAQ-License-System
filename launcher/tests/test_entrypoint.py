from __future__ import annotations

import runpy
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch
from pathlib import Path


class EntrypointTests(unittest.TestCase):
    def test_main_file_can_be_executed_directly_from_another_directory(self) -> None:
        launcher_dir = Path(__file__).resolve().parents[1]
        fake_gui = ModuleType("src.gui")
        fake_gui.run_gui = Mock(return_value=0)  # type: ignore[attr-defined]

        with patch.dict(sys.modules, {"src.gui": fake_gui}):
            with self.assertRaises(SystemExit) as result:
                runpy.run_path(str(launcher_dir / "src" / "main.py"), run_name="__main__")

        self.assertEqual(result.exception.code, 0)
        fake_gui.run_gui.assert_called_once_with()  # type: ignore[attr-defined]

    def test_main_exposes_no_command_line_commands(self) -> None:
        import src.main as main

        self.assertFalse(any(name == "parser" or name.startswith("cmd_") for name in vars(main)))


if __name__ == "__main__":
    unittest.main()
