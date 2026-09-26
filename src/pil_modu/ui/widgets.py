"""Arayüzün yeniden kullanılabilir parçaları."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
                               QVBoxLayout)

STYLE = """
QPushButton#modeCard {
    text-align: left; border: 1px solid palette(mid); border-radius: 10px;
    background: palette(base); padding: 0;
}
QPushButton#modeCard:hover { border-color: palette(highlight); }
QPushButton#modeCard:checked { border: 2px solid palette(highlight); background: palette(alternate-base); }
QPushButton#modeCard:disabled { color: palette(mid); }
QLabel#cardTitle { font-weight: 600; font-size: 14px; }
QLabel#muted { color: palette(placeholder-text); }
QLabel#badge {
    background: palette(highlight); color: palette(highlighted-text);
    border-radius: 8px; padding: 1px 8px; font-size: 11px; font-weight: 600;
}
QFrame#panel { background: palette(alternate-base); border-radius: 10px; }
QFrame#banner { border-radius: 8px; }
QFrame#banner[kind="ok"]    { background: rgba(39, 174, 96, 0.15);  border: 1px solid rgba(39, 174, 96, 0.55); }
QFrame#banner[kind="warn"]  { background: rgba(246, 116, 0, 0.15);  border: 1px solid rgba(246, 116, 0, 0.55); }
QFrame#banner[kind="error"] { background: rgba(218, 68, 83, 0.15);  border: 1px solid rgba(218, 68, 83, 0.55); }
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


class ModeCard(QPushButton):
    """Tıklanınca seçilen, aktif moddaysa "Aktif" rozeti gösteren kart."""

    def __init__(self, preset):
        super().__init__()
        self.preset = preset
        self.setObjectName("modeCard")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(78)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setToolTip("\n".join(f"{k}: {v}" for k, v in preset.details()))

        title = QLabel(preset.title)
        title.setObjectName("cardTitle")
        self.badge = QLabel("Aktif")
        self.badge.setObjectName("badge")
        self.badge.hide()
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(title)
        top.addStretch()
        top.addWidget(self.badge)

        text = QVBoxLayout()
        text.setSpacing(2)
        text.addLayout(top)
        text.addWidget(muted(preset.summary))

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(12)
        row.addWidget(icon_label(preset.icon, 32), 0, Qt.AlignTop)
        row.addLayout(text, 1)

        for child in self.findChildren(QLabel):
            child.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_active(self, active):
        self.badge.setVisible(active)


class Banner(QFrame):
    """Renkli bilgi şeridi; isteğe bağlı bir eylem düğmesiyle."""

    action = Signal()

    def __init__(self, action_text=None):
        super().__init__()
        self.setObjectName("banner")
        self.text = QLabel()
        self.text.setWordWrap(True)
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
