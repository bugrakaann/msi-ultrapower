"""Status chips at the top: battery, temperature/fan, NVIDIA, charge limit. Wraps in a narrow window."""
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLabel, QLayout, QStyle, QWidget

from .. import status
from ..i18n import _, decimal, percent


def battery_text(bat):
    if bat is None:
        return _("No battery information")
    level = percent(bat.capacity if bat.capacity is not None else "—")
    if bat.status == "Charging":
        return _("{level} · charging").format(level=level)
    if bat.status in ("Full", "Not charging"):
        return _("{level} · plugged in").format(level=level)
    if bat.discharging:
        return _("{level} · on battery").format(level=level)
    return level


def watts(value):
    return _("{watts} W").format(watts=decimal(value))


def power_text(meter):
    """For the status chip and the tray: "Now 12.3 W · average 11.8 W"."""
    if meter.current is None:
        return _("Power use: not measured while plugged in")
    text = _("Now {watts}").format(watts=watts(meter.current))
    if meter.average is not None:
        text += " · " + _("average {watts}").format(watts=watts(meter.average))
    return text


def power_details(meter):
    """Which period the average covers (tooltip)."""
    if meter.current is None:
        return _("Plugged in, the battery only reports its charging power, so the laptop's "
                 "power use cannot be measured. Unplug to see it.")
    if meter.average is None:
        return _("The average appears after a few seconds on battery.")
    return _("Average since the charger was unplugged ({minutes} min). Resets when you plug "
             "it in.").format(minutes=meter.minutes)


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
    """Lays items out side by side and wraps what does not fit (mirrored in right-to-left languages)."""

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
        self.battery = self._chip(_("Battery level and charging state"))
        self.power = self._chip("")
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

    def refresh(self, meter):
        self.battery.setText(battery_text(status.battery()))
        self.power.setText(power_text(meter))
        self.power.setToolTip(power_details(meter))
        sensors = sensor_text(status.sensors())
        for chip, text in zip((self.cpu, self.gpu), sensors + ["", ""]):
            chip.setText(text)
            chip.setVisible(bool(text))
        if self.caps.nvidia:
            self.nvidia.setText(gpu_text(status.gpu()))
        self.layout_.invalidate()
