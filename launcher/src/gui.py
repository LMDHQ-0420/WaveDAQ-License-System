from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Callable

from PySide6 import QtCore, QtGui, QtWidgets

from src.api_client import LicenseApi, LicenseApiError
from src.config import API_URL, SERVER_PUBLIC_KEY
from src.device_identity import device_fingerprint, load_or_create
from src.license_verifier import verify_license
from src.local_storage import data_dir, load_catalogs, load_installations, load_licenses, mark_license_revoked, save_catalog, save_installation, save_license, set_active_license
from src.software_installer import launch, open_installer


def current_platform() -> str:
    import platform
    if platform.system() == "Darwin":
        machine = platform.machine().lower()
        # Under Rosetta, platform.machine() can report x86_64 even on Apple
        # Silicon. Ask macOS directly so the matching Release is correct.
        translated = False
        try:
            translated = subprocess.check_output(["sysctl", "-in", "sysctl.proc_translated"], text=True, timeout=2).strip() == "1"
        except (OSError, subprocess.SubprocessError):
            pass
        return "macos-arm64" if "arm" in machine or translated else "macos-x64"
    if platform.system() == "Windows":
        return "windows-x64"
    return "linux-x64"


class TaskThread(QtCore.QThread):
    succeeded = QtCore.Signal(object)
    failed = QtCore.Signal(str)
    progressed = QtCore.Signal(int)

    def __init__(self, task: Callable[[Callable[[int], None]], Any], parent: QtCore.QObject | None = None):
        super().__init__(parent)
        self.task = task

    def run(self) -> None:
        try:
            self.succeeded.emit(self.task(self.progressed.emit))
        except Exception as exc:
            self.failed.emit(str(exc))


class ActivationPage(QtWidgets.QWidget):
    activated = QtCore.Signal()
    activation_warning = QtCore.Signal(str)
    cancelled = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        title = QtWidgets.QLabel("设备激活")
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 4)
        title_font.setBold(True)
        title.setFont(title_font)
        subtitle = QtWidgets.QLabel("请输入激活码以继续。")
        subtitle.setWordWrap(True)

        input_label = QtWidgets.QLabel("激活码")
        self.code = QtWidgets.QLineEdit()
        self.code.setPlaceholderText("XXXXX-XXXXX-XXXXX-XXXXX")
        self.code.setClearButtonEnabled(True)
        self.code.setMinimumHeight(44)
        code_font = self.code.font()
        code_font.setPointSize(code_font.pointSize() + 2)
        self.code.setFont(code_font)
        self.code.returnPressed.connect(self.activate)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        status_palette = self.status.palette()
        status_palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor("#dc3545"))
        self.status.setPalette(status_palette)
        self.status.hide()

        self.button = QtWidgets.QPushButton("验证并继续")
        self.button.setDefault(True)
        self.button.clicked.connect(self.activate)
        self.cancel = QtWidgets.QPushButton("返回软件列表")
        self.cancel.clicked.connect(self.cancelled.emit)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self.cancel)
        buttons.addStretch()
        buttons.addWidget(self.button)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(6)
        layout.addWidget(input_label)
        layout.addWidget(self.code)
        layout.addWidget(self.status)
        layout.addLayout(buttons)
        layout.addStretch()
        self.thread: TaskThread | None = None

    def set_cancel_visible(self, visible: bool) -> None:
        self.cancel.setVisible(visible)

    def _set_status(self, message: str) -> None:
        self.status.setText(message)
        self.status.setVisible(bool(message))

    def activate(self) -> None:
        code = self.code.text().strip().upper()
        if not code:
            self._set_status("请输入激活码")
            return
        if SERVER_PUBLIC_KEY.startswith("REPLACE_"):
            self._set_status("Launcher 尚未配置服务器公钥，请先完成本地服务配置。")
            return
        self.button.setEnabled(False)
        self.button.setText("正在验证…")
        self._set_status("")

        def task(_: Callable[[int], None]) -> object:
            identity = load_or_create()
            api = LicenseApi(API_URL)
            response = api.activate(code, identity["device_id"], identity["public_key"], device_fingerprint())
            document = response["license"]
            verify_license(document, identity, SERVER_PUBLIC_KEY)
            save_license(document)
            warning = ""
            try:
                catalog = api.releases(document["license_id"], identity)
                save_catalog(document["license_id"], catalog)
            except Exception as exc:
                warning = f"授权已激活，但暂时无法读取安装包：{exc}。请稍后点击“在线检查更新”。"
            return {"license": document, "warning": warning}

        self.thread = TaskThread(task, self)
        self.thread.succeeded.connect(self._activation_done)
        self.thread.failed.connect(self._activation_failed)
        self.thread.start()

    def _activation_done(self, result: object) -> None:
        self.button.setEnabled(True)
        self.button.setText("验证并继续")
        self.code.clear()
        self._set_status("")
        self.activated.emit()
        if isinstance(result, dict) and result.get("warning"):
            self.activation_warning.emit(str(result["warning"]))

    def _activation_failed(self, message: str) -> None:
        self.button.setEnabled(True)
        self.button.setText("验证并继续")
        self._set_status(message)


class LibraryPage(QtWidgets.QWidget):
    add_key = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__()
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 12)
        root.setSpacing(10)
        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("软件列表")
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 3)
        title_font.setBold(True)
        title.setFont(title_font)
        self.refresh_button = QtWidgets.QPushButton("在线检查更新")
        self.refresh_button.clicked.connect(self.refresh_online)
        add = QtWidgets.QPushButton("新增密钥")
        add.clicked.connect(self.add_key.emit)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.refresh_button)
        header.addWidget(add)
        root.addLayout(header)

        self.notice = QtWidgets.QLabel("")
        self.notice.setWordWrap(True)
        self.notice.hide()
        root.addWidget(self.notice)

        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["软件", "说明", "版本 / 状态", "操作"])
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        self.table.verticalHeader().setVisible(False)
        table_header = self.table.horizontalHeader()
        table_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        table_header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        table_header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Interactive)
        table_header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(2, 140)
        self.table.setColumnWidth(3, 120)
        root.addWidget(self.table, 1)

        footer = QtWidgets.QHBoxLayout()
        self.device_label = QtWidgets.QLabel("")
        footer.addWidget(self.device_label)
        footer.addStretch()
        root.addLayout(footer)
        self.thread: TaskThread | None = None
        self.reload()

    def _set_notice(self, message: str) -> None:
        self.notice.setText(message)
        self.notice.setVisible(bool(message))

    def _valid_license_ids(self) -> set[str]:
        identity = load_or_create()
        valid: set[str] = set()
        for document in load_licenses():
            try:
                verify_license(document, identity, SERVER_PUBLIC_KEY)
                valid.add(str(document["license_id"]))
            except Exception:
                continue
        return valid

    def reload(self) -> None:
        self.table.clearContents()
        self.table.clearSpans()
        self.table.setRowCount(0)
        try:
            identity = load_or_create()
            self.device_label.setText(f"设备  {identity['device_id'][-8:]}")
            valid_ids = self._valid_license_ids() if not SERVER_PUBLIC_KEY.startswith("REPLACE_") else set()
        except Exception as exc:
            self._set_notice(str(exc))
            valid_ids = set()
        catalogs = load_catalogs()
        installations = load_installations()
        items: list[dict[str, Any]] = []
        for license_id, catalog in catalogs.items():
            if license_id not in valid_ids:
                continue
            for product in catalog.get("products", []):
                releases = [release for release in catalog.get("releases", []) if release.get("product_id") == product.get("id") and release.get("platform") == current_platform()]
                releases.sort(key=lambda value: value.get("version", ""), reverse=True)
                installation = next((record for record in installations if record.get("product_id") == product.get("id") and record.get("license_id") == license_id), None)
                installation_target = Path(os.path.expandvars(installation.get("launch_path", ""))) if installation else None
                if installation and installation_target and installation_target.exists():
                    item = {**product, "license_id": license_id, "installation": installation, "release": releases[0] if releases else None, "action": "launch", "action_label": "打开", "detail": f"已安装 {installation.get('version', '')}"}
                elif releases:
                    item = {**product, "license_id": license_id, "release": releases[0], "action": "download", "action_label": "下载并安装", "detail": f"可用版本 {releases[0].get('version')}"}
                else:
                    item = {**product, "license_id": license_id, "action": "unavailable", "action_label": "暂无适用版本", "detail": current_platform()}
                items.append(item)
        # A local installation must remain launchable even if the cached
        # catalog is missing or was never refreshed. The signed license and
        # the installation record are sufficient for an offline launch.
        known_installations = {(item.get("license_id"), item.get("id"), item["installation"].get("platform")) for item in items if item.get("installation")}
        for installation in installations:
            key = (installation.get("license_id"), installation.get("product_id"), installation.get("platform"))
            target = Path(os.path.expandvars(str(installation.get("launch_path", ""))))
            if installation.get("license_id") not in valid_ids or key in known_installations or installation.get("platform") != current_platform() or not target.exists():
                continue
            items.append({"id": installation.get("product_id", "wavedaq-8ch"), "name": installation.get("name", "WaveDAQ"), "description": "本地已安装版本", "license_id": installation["license_id"], "installation": installation, "release": None, "action": "launch", "action_label": "打开", "detail": f"已安装 {installation.get('version', '')}（离线）"})
        if not items:
            self.table.setRowCount(1)
            empty = QtWidgets.QTableWidgetItem("暂无可用软件，请点击右上角“新增密钥”。")
            empty.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(0, 0, empty)
            self.table.setSpan(0, 0, 1, 4)
            self.table.setRowHeight(0, 72)
            return

        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(item["name"]))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(item.get("description") or "WaveDAQ 数据采集软件"))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(item.get("detail", "")))
            button = QtWidgets.QPushButton(item["action_label"])
            button.setEnabled(item["action"] != "unavailable")
            button.clicked.connect(lambda _checked=False, selected=item: self.handle_action(selected))
            self.table.setCellWidget(row, 3, button)
            self.table.setRowHeight(row, 44)

    def refresh_online(self) -> None:
        self.refresh_button.setEnabled(False)
        self._set_notice("正在在线检查授权和软件更新…")

        def task(_: Callable[[int], None]) -> object:
            identity = load_or_create()
            api = LicenseApi(API_URL)
            refreshed_count = 0
            revoked_count = 0
            warnings: list[str] = []
            for document in load_licenses():
                license_id = str(document["license_id"])
                try:
                    refreshed = api.refresh(license_id, identity)["license"]
                    verify_license(refreshed, identity, SERVER_PUBLIC_KEY)
                    save_license(refreshed, make_active=False)
                    refreshed_count += 1
                    try:
                        save_catalog(license_id, api.releases(license_id, identity))
                    except LicenseApiError as exc:
                        warnings.append(f"{license_id[-8:]} 更新目录失败：{exc}")
                except LicenseApiError as exc:
                    if exc.status == 403:
                        mark_license_revoked(license_id)
                        revoked_count += 1
                        continue
                    warnings.append(f"{license_id[-8:]} 检查失败：{exc}")
            return {"refreshed": refreshed_count, "revoked": revoked_count, "warnings": warnings}

        self.thread = TaskThread(task, self)
        self.thread.succeeded.connect(self._refresh_done)
        self.thread.failed.connect(self._task_failed)
        self.thread.start()

    def _refresh_done(self, result: object) -> None:
        self.refresh_button.setEnabled(True)
        values = result if isinstance(result, dict) else {}
        message = f"已在线检查 {values.get('refreshed', 0)} 个授权"
        if values.get("revoked"):
            message += f"，已停用 {values['revoked']} 个无效授权"
        warnings = values.get("warnings") or []
        if warnings:
            message += "；" + "；".join(str(item) for item in warnings)
        self._set_notice(message)
        self.reload()

    def handle_action(self, item: dict[str, Any]) -> None:
        if item["action"] == "launch":
            try:
                set_active_license(item["license_id"])
                target = Path(os.path.expandvars(item["installation"]["launch_path"]))
                if not target.exists():
                    raise RuntimeError(f"找不到已安装程序：{target}")
                launch(target)
            except Exception as exc:
                self._set_notice(str(exc))
            return
        release = item["release"]
        file_name = release.get("file_name") or release["id"]
        destination = data_dir() / "downloads" / item["id"] / release["version"] / file_name
        self._set_notice(f"正在下载 {item['name']}… 0%")

        def task(report: Callable[[int], None]) -> object:
            identity = load_or_create()
            api = LicenseApi(API_URL)
            def progress(received: int, total: int) -> None:
                report(int(received * 100 / total) if total else 0)
            path = api.download(release["download_url"], item["license_id"], identity, release["sha256"], destination, progress)
            launch_path = release.get("launch_path") or "@downloaded"
            if launch_path == "@downloaded": launch_path = str(path)
            record = {"license_id": item["license_id"], "product_id": item["id"], "name": item["name"], "version": release["version"], "platform": release["platform"], "launch_path": launch_path, "package_path": str(path)}
            save_installation(record)
            set_active_license(item["license_id"])
            open_installer(path)
            return record

        self.thread = TaskThread(task, self)
        self.thread.progressed.connect(lambda value: self._set_notice(f"正在下载 {item['name']}… {value}%"))
        self.thread.succeeded.connect(lambda _: self._download_done(item["name"]))
        self.thread.failed.connect(self._task_failed)
        self.thread.start()

    def _download_done(self, name: str) -> None:
        self._set_notice(f"{name} 下载完成，安装程序已打开。安装完成后可从这里启动。")
        self.reload()

    def _task_failed(self, message: str) -> None:
        self.refresh_button.setEnabled(True)
        self._set_notice(message)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("WaveDAQ Launcher")
        self.resize(640, 360)
        self.setMinimumSize(540, 300)
        self.stack = QtWidgets.QStackedWidget()
        self.activation = ActivationPage()
        self.library = LibraryPage()
        self.stack.addWidget(self.activation)
        self.stack.addWidget(self.library)
        central = QtWidgets.QWidget()
        central_layout = QtWidgets.QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.stack, 1)
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        central_layout.addWidget(separator)
        credit = QtWidgets.QLabel("Coding by sunyuxiang25@mails.ucas.edu.cn")
        credit.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        credit_font = credit.font()
        credit_font.setPointSize(max(8, credit_font.pointSize() - 2))
        credit.setFont(credit_font)
        credit_palette = credit.palette()
        credit_palette.setColor(QtGui.QPalette.ColorRole.WindowText, credit_palette.color(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.WindowText))
        credit.setPalette(credit_palette)
        credit.setContentsMargins(0, 3, 10, 5)
        central_layout.addWidget(credit)
        self.setCentralWidget(central)
        self.activation.activated.connect(self.show_library)
        self.activation.activation_warning.connect(self.library._set_notice)
        self.activation.cancelled.connect(self.show_library)
        self.library.add_key.connect(self.show_activation)
        if load_licenses(): self.show_library()
        else: self.show_activation()

    def show_activation(self) -> None:
        self.activation.set_cancel_visible(bool(load_licenses()))
        self.stack.setCurrentWidget(self.activation)

    def show_library(self) -> None:
        self.library.reload()
        self.stack.setCurrentWidget(self.library)


def run_gui() -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app.setApplicationName("WaveDAQ Software Center")
    try:
        # Identity creation is local only. If an identity already exists, this
        # also verifies the machine-code binding before showing any page.
        load_or_create()
    except Exception as exc:
        QtWidgets.QMessageBox.critical(None, "无法启动", str(exc))
        return 1
    window = MainWindow()
    window.show()
    return app.exec()
