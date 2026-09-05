"""
动物桌宠统一入口 - 配置校验 + 高DPI + 启动。
"""
import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from src.config import Config
from src.overlay import Overlay


def get_base_dir() -> str:
    """获取资源根目录（兼容 PyInstaller 打包和开发模式）"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def main():
    # 高 DPI 支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    base_dir = get_base_dir()
    cfg = Config()

    # 配置校验
    errors = cfg.validate()
    if errors:
        print("配置校验失败：")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    overlay = Overlay(cfg, base_dir)
    overlay.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
