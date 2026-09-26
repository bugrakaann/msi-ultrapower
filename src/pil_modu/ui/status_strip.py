"""Üstteki durum çipleri: pil, sıcaklık/fan, NVIDIA, şarj sınırı. Dar pencerede alt satıra akar."""
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLabel, QLayout, QStyle, QWidget

from .. import status
from ..i18n import _


def battery_text(bat):
    if bat is None:
        return _("No battery information")
    level = f"{bat.capacity}%" if bat.capacity is not None else "—%"
    if bat.status == "Charging":
        return _("{level} · charging").format(level=level)
    if bat.status in ("Full", "Not charging"):
        return _("{level} · plugged in").format(level=level)
    if bat.discharging and bat.watts is not None:
        return _("{level} · {watts} W").format(level=level, watts=f"{bat.watts:.1f}")
    return level


def gpu_text(gpu):
    if not gpu.present:
        return _("NVIDIA off")
    return {"suspended": _("NVIDIA sleeping"), "active": _("NVIDIA active"),
            "suspending": _("NVIDIA going to sleep"), "resuming": _("NVIDIA waking up")
            }.get(gpu.runtime, "NVIDIA " + gpu.runtime)


def sensor_text(sensors):
    parts = []
    if sensors.cpu_temp is not None:
        text = _("CPU {temp}°C").format(temp=sensors.cpu_temp)
        if sensors.cpu_fan is not None:
            text += " · " + _("fan {speed}%").format(speed=sensors.cpu_fan)
        parts.append(text)
    if sensors.gpu_temp is not None:
        text = _("GPU {temp}°C").format(temp=sensors.gpu_temp)
        if sensors.gpu_fan:
            text += " · " + _("fan {speed}%").format(speed=sensors.gpu_fan)
        parts.append(text)
    return parts


class FlowLayout(QLayout):
    """Öğeleri yan yana dizer, sığmayanı alt satıra geçirir (sağdan sola dillerde aynalanır)."""

    def __init__(self, parent=None, spacing=6):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._arrange(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._arrange(rect, apply=True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _arrange(self, rect, apply):
        x, y, line_height = rect.x(), rect.y(), 0
        for item in self._items:
            if not item.widget() or item.widget().isHidden():
                continue
            hint = item.sizeHint()
            if x + hint.width() > rect.right() and line_height:
                x, y, line_height = rect.x(), y + line_height + self._spacing, 0
            if apply:
                logical = QRect(QPoint(x, y), hint)
                item.setGeometry(QStyle.visualRect(self.parentWidget().layoutDirection(), rect, logical)
                                 if self.parentWidget() else logical)
            x += hint.width() + self._spacing
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y()


class StatusStrip(QWidget):
    def __init__(self, caps):
        super().__init__()
        self.caps = caps
        self.layout_ = FlowLayout(self)
        self.battery = self._chip(_("Battery level. While discharging, the battery's own power "
                                    "reading; it cannot be measured while plugged in."))
        self.cpu = self._chip(_("Temperature and fan speed reported by the EC"))
        self.gpu = self._chip(_("Temperature and fan speed reported by the EC"))
        self.nvidia = self._chip(_("Current state of the NVIDIA GPU"))
        self.nvidia.setVisible(caps.nvidia)

    def _chip(self, tooltip):
        label = QLabel()
        label.setObjectName("chip")
        label.setToolTip(tooltip)
        self.layout_.addWidget(label)
        return label

    def refresh(self):
        self.battery.setText(battery_text(status.battery()))
        sensors = sensor_text(status.sensors())
        for chip, text in zip((self.cpu, self.gpu), sensors + ["", ""]):
            chip.setText(text)
            chip.setVisible(bool(text))
        if self.caps.nvidia:
            self.nvidia.setText(gpu_text(status.gpu()))
        self.layout_.invalidate()
