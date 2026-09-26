"""Ana pencere: mod seç → ayrıntılara bak → Uygula."""
import shutil

from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFormLayout, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QProgressBar,
                               QPushButton, QToolButton, QVBoxLayout, QWidget)

from .. import state, status
from ..presets import EXTERNAL_CHOICES, PRESETS
from .runner import ModeRunner
from .widgets import STYLE, Banner, ModeCard, icon_label, muted

REFRESH_MS = 2000
GPU_RUNTIME = {"suspended": "Uykuda", "active": "Aktif",
               "suspending": "Uykuya geçiyor", "resuming": "Uyanıyor"}


def battery_text(bat):
    if bat is None:
        return "Pil bilgisi yok"
    level = f"%{bat.capacity}" if bat.capacity is not None else "%—"
    if bat.status == "Charging":
        return f"{level} · Şarj oluyor"
    if bat.status in ("Full", "Not charging"):
        return f"{level} · Prizde"
    if bat.discharging and bat.watts is not None:
        return f"{level} · {bat.watts:.1f} W tüketim"
    return level


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Güç Modları")
        self.setWindowIcon(QIcon.fromTheme("battery"))
        self.setStyleSheet(STYLE)
        self.resize(640, 720)

        self.runner = ModeRunner(self)
        self.runner.output.connect(self._append_log)
        self.runner.finished.connect(self._on_finished)
        self.pending_mode = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(14)
        root.addLayout(self._build_header())
        root.addWidget(self._build_reboot_banner())
        root.addLayout(self._build_cards())
        root.addWidget(self._build_details())
        root.addLayout(self._build_actions())
        root.addWidget(self._build_result())
        root.addStretch()
        root.addLayout(self._build_footer())
        root.addWidget(self.log)

        active = state.load_active() or {}
        self._select(active.get("mod") if active.get("mod") in PRESETS else "dengeli")
        self.external.setCurrentIndex(max(0, self.external.findData(active.get("harici", "otomatik"))))

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(REFRESH_MS)
        self.refresh()

    # ---------- Arayüzün kurulumu ----------

    def _build_header(self):
        title = QLabel("Güç Modları")
        title.setStyleSheet("font-size: 22px; font-weight: 600;")
        self.active_label = muted()
        left = QVBoxLayout()
        left.setSpacing(2)
        left.addWidget(title)
        left.addWidget(self.active_label)

        self.battery_label = QLabel()
        self.battery_label.setStyleSheet("font-size: 15px; font-weight: 600;")
        self.battery_label.setToolTip("2 saniyede bir yenilenir. Pilin bildirdiği deşarj gücüdür; "
                                      "prizdeyken toplam tüketim ölçülemez.")
        header = QHBoxLayout()
        header.addLayout(left, 1)
        header.addWidget(icon_label("battery", 22))
        header.addWidget(self.battery_label)
        return header

    def _build_reboot_banner(self):
        self.reboot_banner = Banner("Yeniden başlat")
        self.reboot_banner.action.connect(self._reboot)
        return self.reboot_banner

    def _build_cards(self):
        self.cards = {}
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        grid = QGridLayout()
        grid.setSpacing(10)
        for index, preset in enumerate(PRESETS.values()):
            card = ModeCard(preset)
            card.clicked.connect(lambda _=False, key=preset.key: self._select(key))
            self.group.addButton(card)
            self.cards[preset.key] = card
            grid.addWidget(card, index // 2, index % 2)
        return grid

    def _build_details(self):
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        self.details_title = QLabel()
        self.details_title.setStyleSheet("font-weight: 600; font-size: 15px;")
        layout.addWidget(self.details_title)

        self.details_form = QFormLayout()
        self.details_form.setHorizontalSpacing(24)
        self.details_form.setVerticalSpacing(4)
        layout.addLayout(self.details_form)

        self.external = QComboBox()
        for key, label in EXTERNAL_CHOICES.items():
            self.external.addItem(label, key)
        self.external_hint = muted()
        external_row = QHBoxLayout()
        external_row.addWidget(QLabel("Harici ekran"))
        external_row.addWidget(self.external, 1)
        layout.addLayout(external_row)
        layout.addWidget(self.external_hint)
        return panel

    def _build_actions(self):
        self.restore_button = QPushButton(QIcon.fromTheme("edit-undo"), "Önceki ayarlara dön")
        self.restore_button.setToolTip("İlk moddan önceki ekran, profil ve donanım ayarlarını geri yükler.")
        self.restore_button.clicked.connect(lambda: self._run("geri"))

        self.apply_button = QPushButton(QIcon.fromTheme("dialog-ok-apply"), "Uygula")
        self.apply_button.setMinimumWidth(140)
        self.apply_button.setMinimumHeight(34)
        self.apply_button.setStyleSheet("font-weight: 600;")
        self.apply_button.clicked.connect(lambda: self._run(self.selected))

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setMaximumHeight(6)
        self.progress.hide()

        row = QHBoxLayout()
        row.addWidget(self.restore_button)
        row.addStretch()
        row.addWidget(self.apply_button)
        layout = QVBoxLayout()
        layout.addLayout(row)
        layout.addWidget(self.progress)
        return layout

    def _build_result(self):
        self.result = Banner()
        return self.result

    def _build_footer(self):
        self.system_label = muted()
        self.log_toggle = QToolButton()
        self.log_toggle.setText("İşlem günlüğü")
        self.log_toggle.setCheckable(True)
        self.log_toggle.setArrowType(Qt.RightArrow)
        self.log_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.log_toggle.setAutoRaise(True)
        self.log_toggle.toggled.connect(self._show_log)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(300)
        self.log.setMinimumHeight(140)
        self.log.setPlaceholderText("Uygulanan adımlar burada görünür.")
        self.log.hide()

        row = QHBoxLayout()
        row.addWidget(self.system_label, 1)
        row.addWidget(self.log_toggle)
        return row

    # ---------- Durum ----------

    @property
    def busy(self):
        return self.runner.is_running()

    def _select(self, key):
        self.selected = key
        preset = PRESETS[key]
        self.cards[key].setChecked(True)
        self.details_title.setText(preset.title)
        while self.details_form.rowCount():
            self.details_form.removeRow(0)
        for label, value in preset.details():
            self.details_form.addRow(muted(label), QLabel(value))

        self.external.setEnabled(not preset.is_battery and not self.busy)
        if preset.is_battery:
            self.external_hint.setText("Batarya modlarında NVIDIA'ya bağlı HDMI çıkışı kapanır; "
                                       "harici ekran kullanılamaz. Geçiş için yeniden başlatma gerekir.")
        else:
            self.external_hint.setText("“Moda göre otomatik”: bağlı harici ekran açık kalır.")
        self._update_apply_text()

    def _update_apply_text(self):
        active = (state.load_active() or {}).get("mod")
        self.apply_button.setText("Yeniden uygula" if active == self.selected else "Uygula")

    def refresh(self):
        self.battery_label.setText(battery_text(status.battery()))

        active = (state.load_active() or {}).get("mod")
        for key, card in self.cards.items():
            card.set_active(key == active)
        self.active_label.setText("Aktif mod: " + (PRESETS[active].title if active in PRESETS
                                                   else "seçilmedi (sistem ayarları)"))

        gpu = status.gpu()
        nvidia = GPU_RUNTIME.get(gpu.runtime, gpu.runtime) if gpu.present else "Devre dışı"
        turbo = {True: "açık", False: "kapalı", None: "—"}[status.turbo_enabled()]
        self.system_label.setText(f"NVIDIA: {nvidia}  ·  EC: {status.ec_shift_mode()}  ·  CPU turbo: {turbo}")

        if gpu.reboot_pending and not self.busy:
            what = "devre dışı kalacak" if gpu.blocked_next_boot else "yeniden kullanılabilir olacak"
            self.reboot_banner.show_message("warn", f"Yeniden başlatınca NVIDIA {what}.")
        else:
            self.reboot_banner.hide()

        self.restore_button.setEnabled(not self.busy and state.has_original())
        self._update_apply_text()

    # ---------- İşlemler ----------

    def _run(self, mode):
        if self.busy:
            return
        args = [mode]
        if mode in PRESETS:
            external = "kapat" if PRESETS[mode].is_battery else self.external.currentData()
            args += ["--harici", external]
        self.pending_mode = mode
        self.log.clear()
        self.result.show_message("warn", "Uygulanıyor… Yönetici parolası istenebilir.")
        self._set_controls_enabled(False)
        self.progress.show()
        self.runner.start(args)

    def _on_finished(self, ok):
        self.progress.hide()
        self._set_controls_enabled(True)
        name = "Önceki ayarlar" if self.pending_mode not in PRESETS else PRESETS[self.pending_mode].title
        if ok:
            self.result.show_message("ok", f"{name} uygulandı.")
        else:
            self.result.show_message("error", "İşlem tamamlanamadı. Ayrıntılar işlem günlüğünde.")
            self.log_toggle.setChecked(True)
        self.refresh()

    def _set_controls_enabled(self, enabled):
        for card in self.cards.values():
            card.setEnabled(enabled)
        self.apply_button.setEnabled(enabled)
        self.restore_button.setEnabled(enabled and state.has_original())
        self.external.setEnabled(enabled and not PRESETS[self.selected].is_battery)

    def _append_log(self, text):
        self.log.appendPlainText(text)

    def _show_log(self, visible):
        self.log.setVisible(visible)
        self.log_toggle.setArrowType(Qt.DownArrow if visible else Qt.RightArrow)

    def _reboot(self):
        # KDE'nin kendi onay penceresini açar; açık uygulamalar düzgün kapanır.
        if shutil.which("qdbus6"):
            QProcess.startDetached("qdbus6", ["org.kde.LogoutPrompt", "/LogoutPrompt", "promptReboot"])
        elif QMessageBox.question(self, "Yeniden başlat", "Bilgisayar şimdi yeniden başlatılsın mı?") \
                == QMessageBox.Yes:
            QProcess.startDetached("systemctl", ["reboot"])

    def closeEvent(self, event):
        if self.busy:
            QMessageBox.information(self, "İşlem sürüyor",
                                    "Ayarların uygulanması bitince pencereyi kapatabilirsin.")
            event.ignore()
        else:
            event.accept()
