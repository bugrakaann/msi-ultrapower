"""Grafik arayüzün giriş noktası:  pil-modu-ui [--tray]

--tray: pencere açılmadan tepside başlar (oturum açılışında otomatik başlatma bunu kullanır).
Uygulama tek kopya çalışır; ikinci kez açılınca var olan pencere öne gelir.
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

SERVER_NAME = "pil-modu-ui"


def notify_running_instance():
    """Başka bir kopya çalışıyorsa ona "göster" der ve True döner."""
    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    if not socket.waitForConnected(300):
        return False
    socket.write(b"show")
    socket.waitForBytesWritten(300)
    return True


def install_translations(app):
    """Qt'nin kendi düğmeleri (Kaydet, İptal…) ve sağdan sola diller."""
    translator = QTranslator(app)
    if translator.load(f"qtbase_{i18n.current()}", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        app.installTranslator(translator)
    if i18n.is_rtl():
        app.setLayoutDirection(Qt.RightToLeft)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(_("Power Modes"))
    app.setDesktopFileName("pil-modu")
    if notify_running_instance():
        return 0
    install_translations(app)

    window = MainWindow()
    server = QLocalServer(app)
    QLocalServer.removeServer(SERVER_NAME)  # önceki çökmeden kalan soket
    server.listen(SERVER_NAME)

    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = Tray(window, app)
        tray.show()
        app.setQuitOnLastWindowClosed(False)
        started_in_tray = "--tray" in sys.argv
        # Otomatik mod ya da tepside başlatma açıksa pencere kapanınca uygulama tepside kalır.
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
