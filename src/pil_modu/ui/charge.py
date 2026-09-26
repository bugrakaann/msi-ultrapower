"""Şarj sınırı: 60 / 80 / 100 segmentli düğmeler ve pilin şarj olup olmayacağı."""
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton

from .. import status
from ..i18n import _
from ..privileged.hardware import CHARGE_LIMITS
from .widgets import heading, muted, panel


def charge_text(bat, start, limit):
    """Şarj sınırına göre pilin şarj olup olmayacağını anlatır."""
    if limit >= 100:
        goal = _("The battery charges to full.")
    elif start:
        goal = _("Charging stops at {limit}% and resumes below {start}%.").format(limit=limit, start=start)
    else:
        goal = _("Charging stops at {limit}%.").format(limit=limit)
    if bat is None or bat.discharging:
        return goal
    if bat.status == "Charging":
        return goal + " " + _("Charging now.")
    if bat.capacity is not None and bat.capacity >= limit:
        return goal + " " + _("Limit reached; plugged in but not charging.")
    return goal + " " + _("Plugged in, waiting to charge.")


class ChargePanel(QObject):
    requested = Signal(str)  # kullanıcı yeni bir sınır seçti

    def __init__(self):
        super().__init__()
        self.widget, layout = panel()
        self.widget.setToolTip(_("The highest level the battery charges to. Independent of modes and "
                                 "restored at boot. 60% and 80% extend battery life."))
        top = QHBoxLayout()
        top.addWidget(heading(_("Charge limit")), 1)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        segments = QHBoxLayout()
        segments.setSpacing(0)
        for index, limit in enumerate(CHARGE_LIMITS):
            button = QPushButton(f"{limit}%")
            button.setObjectName("segment")
            button.setCheckable(True)
            button.setProperty("position", "first" if index == 0 else
                               "last" if index == len(CHARGE_LIMITS) - 1 else "middle")
            self.group.addButton(button, int(limit))
            segments.addWidget(button)
        self.group.idClicked.connect(lambda limit: self.requested.emit(str(limit)))
        top.addLayout(segments)
        layout.addLayout(top)
        self.hint = muted()
        layout.addWidget(self.hint)

    def refresh(self, busy):
        start, limit = status.charge_limits()
        supported = limit is not None
        for button in self.group.buttons():
            button.setEnabled(supported and not busy)
        if not supported:
            self.hint.setText(_("This computer does not support a charge limit."))
            return
        self.hint.setText(charge_text(status.battery(), start, limit))
        if not busy:
            button = self.group.button(limit)
            if button:
                button.setChecked(True)
            elif self.group.checkedButton():  # sınır 60/80/100 dışında (başka araçla ayarlanmış)
                self.group.setExclusive(False)
                self.group.checkedButton().setChecked(False)
                self.group.setExclusive(True)
