from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

from src import gui


class GuiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_main_window_can_be_created_without_local_state(self) -> None:
        identity = {"device_id": "dev_" + "a" * 32, "public_key": "x" * 43, "private_key": "y" * 43}
        with patch.object(gui, "load_or_create", return_value=identity), patch.object(gui, "load_licenses", return_value=[]), patch.object(gui, "load_catalogs", return_value={}), patch.object(gui, "load_installations", return_value=[]):
            window = gui.MainWindow()
            self.assertEqual(window.windowTitle(), "WaveDAQ Launcher")
            self.assertIs(window.stack.currentWidget(), window.activation)
            self.assertGreaterEqual(window.minimumWidth(), 540)
            window.close()

    def test_machine_mismatch_shows_recovery_and_new_activation(self) -> None:
        identity = {"device_id": "dev_" + "a" * 32, "public_key": "x" * 43, "private_key": "y" * 43}
        with patch.object(gui, "load_or_create", return_value=identity), patch.object(gui, "load_licenses", return_value=[]), patch.object(gui, "load_catalogs", return_value={}), patch.object(gui, "load_installations", return_value=[]):
            window = gui.MainWindow(startup_error="设备机器码不匹配，无法读取本机授权")
            self.assertIs(window.stack.currentWidget(), window.activation)
            self.assertIn("清除本机绑定", window.activation.status.text())
            self.assertTrue(any(button.text() == "清除本机绑定并重新激活" for button in window.findChildren(gui.QtWidgets.QPushButton)))
            window.close()


if __name__ == "__main__":
    unittest.main()
