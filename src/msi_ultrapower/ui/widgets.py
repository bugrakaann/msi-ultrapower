"""Arayüzün yeniden kullanılabilir parçaları ve ortak stil.

Renkler sabit değil, sistemin (Breeze) paletinden gelir; açık ve koyu tema kendiliğinden çalışır.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
                               QToolButton, QVBoxLayout)

from ..i18n import _

STYLE = """
QPushButton#modeRow {
    text-align: left; border: 1px solid palette(mid); border-radius: 12px;
    background: palette(base); padding: 0;
}
QPushButton#modeRow:hover { border-color: palette(highlight); }
QPushButton#modeRow:checked { border: 2px solid palette(highlight); background: palette(alternate-base); }
QPushButton#modeRow:disabled { color: palette(mid); }
QLabel#rowTitle { font-weight: 600; font-size: 14px; }
QLabel#muted { color: palette(placeholder-text); }
QLabel#badge {
    background: palette(highlight); color: palette(highlighted-text);
    border-radius: 9px; padding: 1px 9px; font-size: 11px; font-weight: 600;
}
QLabel#chip {
    background: palette(alternate-base); border: 1px solid palette(midlight);
    border-radius: 13px; padding: 3px 11px;
}
QFrame#panel { background: palette(alternate-base); border-radius: 12px; }
QFrame#actionBar { border-top: 1px solid palette(midlight); }
QLabel#section { color: palette(highlight); font-weight: 600; }
QLabel#heading { font-weight: 600; font-size: 15px; }
QPushButton#segment { padding: 5px 16px; border: 1px solid palette(mid); background: palette(base); }
QPushButton#segment:checked { background: palette(highlight); color: palette(highlighted-text);
                              border-color: palette(highlight); }
QPushButton#segment[position="first"] { border-top-left-radius: 8px; border-bottom-left-radius: 8px; }
QPushButton#segment[position="last"] { border-top-right-radius: 8px; border-bottom-right-radius: 8px; }
QPushButton#primary {
    font-weight: 600; padding: 6px 24px; border-radius: 8px; border: none;
    background: palette(highlight); color: palette(highlighted-text);
}
QPushButton#primary:hover { background: palette(link); }
QPushButton#primary:disabled { background: palette(mid); color: palette(base); }
QFrame#banner { border-radius: 10px; }
QFrame#banner[kind="ok"]    { background: rgba(39, 174, 96, 0.15);  border: 1px solid rgba(39, 174, 96, 0.55); }
QFrame#banner[kind="warn"]  { background: rgba(246, 116, 0, 0.15);  border: 1px solid rgba(246, 116, 0, 0.55); }
QFrame#banner[kind="error"] { background: rgba(218, 68, 83, 0.15);  border: 1px solid rgba(218, 68, 83, 0.55); }
QScrollArea, QScrollArea > QWidget > QWidget#content { background: transparent; }
"""


def icon_label(name, size):
    label = QLabel()
    label.setPixmap(QIcon.fromTheme(name, QIcon.fromTheme("battery")).pixmap(size, size))
    label.setFixedSize(size, size)
    return label


def muted(text=""):
    label = QLabel(text)
    label.setObjectName("muted")
    label.setWordWrap(True)
    return label


def heading(text=""):
    label = QLabel(text)
    label.setObjectName("heading")
    return label


def section_label(text):
    label = QLabel(text)
    label.setObjectName("section")
    label.setContentsMargins(0, 8, 0, 2)
    label.setStyleSheet("font-weight: 600;")  # kalın yazının yüksekliği yerleşimden önce bilinsin
    label.setMinimumHeight(label.sizeHint().height())
    return label


def panel(spacing=8):
    """Yuvarlak köşeli arka planlı kutu ve içindeki dikey yerleşim."""
    frame = QFrame()
    frame.setObjectName("panel")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(spacing)
    return frame, layout


def link_button(text, icon=None):
    """Kenarlıksız, metin gibi görünen küçük düğme ("Tüm ayrıntılar", "Günlük")."""
    button = QToolButton()
    button.setText(text)
    button.setAutoRaise(True)
    button.setCursor(Qt.PointingHandCursor)
    if icon:
        button.setIcon(QIcon.fromTheme(icon))
        button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    return button


class ModeCard(QPushButton):
    """Mod satırı: simge, ad, kısa açıklama; uygulanmış moddaysa "Aktif" rozeti."""

    def __init__(self, preset):
        super().__init__()
        self.preset = preset
        self.unsupported = None
        self.setObjectName("modeRow")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(60)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.title = QLabel(preset.title)
        self.title.setObjectName("rowTitle")
        self.summary = muted(preset.summary)
        text = QVBoxLayout()
        text.setSpacing(1)
        text.addWidget(self.title)
        text.addWidget(self.summary)

        self.badge = QLabel(_("Active"))
        self.badge.setObjectName("badge")
        self.badge.hide()

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 8, 14, 8)
        row.setSpacing(12)
        row.addWidget(icon_label(preset.icon, 28))
        row.addLayout(text, 1)
        row.addWidget(self.badge, 0, Qt.AlignVCenter)

        for child in self.findChildren(QLabel):
            child.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_active(self, active):
        self.badge.setVisible(active)

    def set_info(self, tooltip, unsupported=None):
        """Üzerine gelince görünen tam değişiklik listesi; desteklenmiyorsa satır kapanır."""
        self.setToolTip(tooltip)
        self.setEnabled(unsupported is None)
        self.unsupported = unsupported
        self.summary.setText(self.preset.summary if unsupported is None
                             else _("Not available here: {reason}").format(reason=unsupported))


class Banner(QFrame):
    """Renkli bilgi şeridi; isteğe bağlı bir eylem düğmesiyle."""

    action = Signal()

    def __init__(self, action_text=None):
        super().__init__()
        self.setObjectName("banner")
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.addWidget(self.text, 1)
        self.button = None
        if action_text:
            self.button = QPushButton(action_text)
            self.button.clicked.connect(self.action)
            layout.addWidget(self.button)
        self.hide()

    def show_message(self, kind, text):
        self.setProperty("kind", kind)
        self.style().unpolish(self)
        self.style().polish(self)
        self.text.setText(text)
        self.show()
