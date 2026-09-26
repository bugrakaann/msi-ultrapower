"""Seçili modun şu anki duruma göre neyi değiştireceği; istenirse modun tüm ayarları."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel

from ..i18n import _, ngettext
from .widgets import heading, link_button, muted, panel, section_label


def clear(grid):
    while grid.count():
        widget = grid.takeAt(0).widget()
        widget.hide()  # deleteLater bir sonraki döngüde siler; o ana kadar görünmesin
        widget.deleteLater()


def fill(grid, rows, start=0):
    """rows: [(ayar, değer)] ya da None (bölüm başlığı için (başlık, None))."""
    row = start
    for label, value in rows:
        if value is None:
            grid.addWidget(section_label(label), row, 0, 1, 2)
        else:
            name = muted(label)
            name.setWordWrap(False)
            text = QLabel(value)
            text.setWordWrap(True)
            grid.addWidget(name, row, 0, Qt.AlignTop)
            grid.addWidget(text, row, 1, Qt.AlignTop)
        row += 1
    return row


def grid_layout():
    grid = QGridLayout()
    grid.setHorizontalSpacing(20)
    grid.setVerticalSpacing(3)
    grid.setColumnStretch(1, 1)
    return grid


class ChangesPanel:
    def __init__(self):
        self.widget, layout = panel()
        top = QHBoxLayout()
        self.title = heading()
        self.toggle = link_button(_("All settings of this mode"), "view-list-details")
        self.toggle.setCheckable(True)
        self.toggle.toggled.connect(self._show_details)
        top.addWidget(self.title, 1)
        top.addWidget(self.toggle)
        layout.addLayout(top)

        self.note = muted()
        layout.addWidget(self.note)
        self.changes = grid_layout()
        layout.addLayout(self.changes)

        self.details_host, details_layout = panel(0)
        self.details_host.setStyleSheet("QFrame#panel { background: transparent; }")
        details_layout.setContentsMargins(0, 4, 0, 0)
        self.details = grid_layout()
        details_layout.addLayout(self.details)
        self.details_host.hide()
        layout.addWidget(self.details_host)

    def show(self, changes, sections, error=None):
        """changes: [(ayar, eski, yeni)], sections: describe.describe() çıktısı."""
        clear(self.changes)
        arrow = "←" if self.widget.isRightToLeft() else "→"
        if error:
            self.title.setText(_("Cannot apply this mode"))
            self.note.setText(error)
        elif changes:
            self.title.setText(ngettext("{count} setting will change", "{count} settings will change",
                                        len(changes)).format(count=len(changes)))
            self.note.setText("")
            fill(self.changes, [(label, f"{old}  {arrow}  {new}") for label, old, new in changes])
        else:
            self.title.setText(_("Nothing to change"))
            self.note.setText(_("This mode is already in effect."))
        self.note.setVisible(bool(self.note.text()))

        clear(self.details)
        rows = []
        for section, items in sections:
            rows.append((section, None))
            rows += items
        fill(self.details, rows)

    def _show_details(self, visible):
        self.details_host.setVisible(visible)
