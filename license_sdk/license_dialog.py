from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets


def show_license_error(message: str, product_name: str = "产品", parent: QtWidgets.QWidget | None = None) -> None:
    """Show the shared Qt authorization-failure dialog for a product."""
    dialog = QtWidgets.QDialog(parent)
    dialog.setWindowTitle(f"{product_name} 授权失败")
    dialog.setMinimumWidth(460)
    dialog.setModal(True)
    dialog.setWindowFlags(dialog.windowFlags() & ~QtCore.Qt.WindowType.WindowContextHelpButtonHint)

    layout = QtWidgets.QVBoxLayout(dialog)
    layout.setContentsMargins(28, 24, 28, 20)
    layout.setSpacing(12)

    title = QtWidgets.QLabel("未经过授权")
    title_font = title.font()
    title_font.setPointSize(title_font.pointSize() + 6)
    title_font.setBold(True)
    title.setFont(title_font)

    subtitle = QtWidgets.QLabel(f"{product_name} 未通过本机授权校验，启动失败")
    subtitle.setWordWrap(True)

    detail = QtWidgets.QLabel(f"原因：{message}\n\n请先通过 WaveDAQ-Launcher 激活当前设备，或联系管理员获取有效授权。")
    detail.setWordWrap(True)
    detail.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
    detail_palette = detail.palette()
    detail_palette.setColor(QtGui.QPalette.ColorRole.WindowText, detail_palette.color(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.WindowText))
    detail.setPalette(detail_palette)

    close_button = QtWidgets.QPushButton("关闭")
    close_button.setDefault(True)
    close_button.clicked.connect(dialog.accept)
    buttons = QtWidgets.QHBoxLayout()
    buttons.addStretch()
    buttons.addWidget(close_button)

    layout.addWidget(title)
    layout.addWidget(subtitle)
    layout.addWidget(detail)
    layout.addLayout(buttons)
    dialog.exec()
