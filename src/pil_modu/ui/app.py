"""Grafik arayüzün giriş noktası:  pil-modu-ui"""
import sys

from PySide6.QtWidgets import QApplication

from .window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Güç Modları")
    app.setDesktopFileName("pil-modu-ui")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
