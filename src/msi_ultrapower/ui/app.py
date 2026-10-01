"""Entry point of the window:  msi-ultrapower-ui [--tray]

--tray: start in the tray without opening the window (used by autostart at login).
Only one copy runs; starting it again brings the existing window to the front.
"""
import sys

from PySide6.QtCore import QLibraryInfo, Qt, QTranslator
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from .. import i18n, settings
from ..i18n import _
from .auto import AutoSwitcher
from .tray import Tray
from .window import MainWindow

SERVER_NAME = "msi-ultrapower-ui"


def notify_running_instance():
    """If another copy is running, tells it to show itself and returns True."""
    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    if not socket.waitForConnected(300):
        return False
    socket.write(b"show")
    socket.waitForBytesWritten(300)
    return True


def install_translations(app):
    """Qt's own buttons (Save, Cancel…) and right-to-left languages."""
    translator = QTranslator(app)
    if translator.load(f"qtbase_{i18n.current()}", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        app.installTranslator(translator)
    if i18n.is_rtl():
        app.setLayoutDirection(Qt.RightToLeft)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(_("Power Modes"))
    app.setDesktopFileName("msi-ultrapower")
    if notify_running_instance():
        return 0
    install_translations(app)

    window = MainWindow()
    server = QLocalServer(app)
    QLocalServer.removeServer(SERVER_NAME)  # socket left over from a crash
    server.listen(SERVER_NAME)

    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = Tray(window, app)
        tray.show()
        app.setQuitOnLastWindowClosed(False)
        started_in_tray = "--tray" in sys.argv
        # With automatic mode or tray start on, closing the window keeps the app in the tray.
        window.keep_running = lambda: started_in_tray or settings.load()["auto_mode"] \
            or settings.load()["tray_autostart"]
    AutoSwitcher(window)

    def show_window():
        connection = server.nextPendingConnection()
        if connection:
            connection.readAll()
        (tray.show_window if tray else window.show)()

    server.newConnection.connect(show_window)

    if tray is None or "--tray" not in sys.argv:
        window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
