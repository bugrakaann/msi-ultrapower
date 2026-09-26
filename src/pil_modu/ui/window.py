"""Ana pencere: mod seç → ne değişeceğine bak → Uygula."""
import shutil

from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QProgressBar,
                               QPushButton, QScrollArea, QSlider, QToolButton, QVBoxLayout,
                               QWidget)

from .. import capabilities, describe, state, status, system
from ..presets import EXTERNAL_CHOICES, PRESETS
from ..privileged.hardware import CHARGE_LIMITS
from .runner import ModeRunner
from .widgets import STYLE, Banner, ModeCard, icon_label, muted, section_label

REFRESH_MS = 2000
CHARGE_DELAY_MS = 700  # kaydırıcı durduktan sonra uygula; her adımda parola sorulmasın
PREFERRED_SIZE = (700, 900)
SCREEN_MARGIN = 32     # pencere ile ekran kenarı arasında bırakılan boşluk
ONE_COLUMN_BELOW = 560  # içerik bu genişlikten darsa kartlar tek sütun olur
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


def charge_text(bat, start, limit):
    """Şarj sınırına göre pilin şarj olup olmayacağını anlatır."""
    if limit >= 100:
        goal = "Pil tam dolar."
    else:
        goal = f"Pil %{limit} dolunca şarj durur" + (f", %{start} altına inince yeniden başlar." if start
                                                   else ".")
    if bat is None or bat.discharging:
        return goal
    if bat.status == "Charging":
        return goal + " Şu an şarj oluyor."
    if bat.capacity is not None and bat.capacity >= limit:
        return goal + " Sınıra ulaşıldı; prizde ama şarj etmiyor."
    return goal + " Prizde, şarj beklemede."


def detect_capabilities():
    try:
        outputs = system.get_outputs()
    except Exception:
        outputs = []  # KDE dışında ya da kscreen-doctor yoksa Hz bilinmez
    return capabilities.detect(outputs)


def missing_features(caps):
    notes = []
    if not caps.ec:
        notes.append("msi-ec sürücüsü bulunamadı: fan, EC modu ve Cooler Boost ayarlanamaz "
                     "(AUR: msi-ec-dkms-git).")
    if not caps.charge_limit:
        notes.append("Pil şarj sınırı bu bilgisayarda desteklenmiyor.")
    return " ".join(notes)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Güç Modları")
        self.setWindowIcon(QIcon.fromTheme("battery"))
        self.setStyleSheet(STYLE)
        self.setMinimumSize(380, 360)
        self.resize(*PREFERRED_SIZE)
        self._fitted = False
        self._columns = 0

        self.caps = detect_capabilities()
        self.runner = ModeRunner(self)
        self.runner.output.connect(self._append_log)
        self.runner.finished.connect(self._on_finished)
        self.pending_args = None

        # İçerik kaydırılabilir; Uygula çubuğu her ekran boyutunda altta görünür kalır.
        content = QWidget()
        content.setObjectName("content")
        body = QVBoxLayout(content)
        body.setContentsMargins(20, 20, 20, 16)
        body.setSpacing(14)
        body.addLayout(self._build_header())
        body.addWidget(self._build_reboot_banner())
        body.addWidget(self._build_capability_banner())
        body.addLayout(self._build_cards())
        body.addWidget(self._build_details())
        body.addWidget(self._build_charge())
        body.addLayout(self._build_footer())
        body.addWidget(self.log)
        body.addStretch()

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setWidget(content)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self.scroll, 1)
        root.addWidget(self._build_action_bar())

        active = state.load_active() or {}
        initial = active.get("mod")
        if initial not in PRESETS or self.cards[initial].unsupported:
            initial = "dengeli"
        self._select(initial)
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
        if self.caps.model:
            left.addWidget(muted(self.caps.model))
        left.addWidget(self.active_label)

        self.battery_label = QLabel()
        self.battery_label.setStyleSheet("font-size: 15px; font-weight: 600;")
        self.battery_label.setToolTip("2 saniyede bir yenilenir. Pilin bildirdiği deşarj gücüdür; "
                                      "prizdeyken toplam tüketim ölçülemez.")
        header = QHBoxLayout()
        header.addLayout(left, 1)
        header.addWidget(icon_label("battery", 22), 0, Qt.AlignTop)
        header.addWidget(self.battery_label, 0, Qt.AlignTop)
        return header

    def _build_reboot_banner(self):
        self.reboot_banner = Banner("Yeniden başlat")
        self.reboot_banner.action.connect(self._reboot)
        return self.reboot_banner

    def _build_capability_banner(self):
        banner = Banner()
        notes = missing_features(self.caps)
        if notes:
            banner.show_message("warn", notes)
        return banner

    def _build_cards(self):
        self.cards = {}
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for preset in PRESETS.values():
            card = ModeCard(preset)
            card.clicked.connect(lambda _=False, key=preset.key: self._select(key))
            reason = capabilities.unsupported_reason(preset, self.caps)
            sections = describe.describe(preset, self.caps)
            card.set_info(describe.to_html(preset.title, sections, reason), reason)
            self.group.addButton(card)
            self.cards[preset.key] = card
        self.card_grid = QGridLayout()
        self.card_grid.setSpacing(10)
        self._layout_cards(2)
        return self.card_grid

    def _layout_cards(self, columns):
        if columns == self._columns:
            return
        self._columns = columns
        for card in self.cards.values():
            self.card_grid.removeWidget(card)
        for index, card in enumerate(self.cards.values()):
            self.card_grid.addWidget(card, index // columns, index % columns)
        for column in range(2):
            self.card_grid.setColumnStretch(column, 1 if column < columns else 0)

    def _build_details(self):
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        self.details_title = QLabel()
        self.details_title.setStyleSheet("font-weight: 600; font-size: 15px;")
        layout.addWidget(self.details_title)
        layout.addWidget(muted("Uygula'ya basınca değişecek her şey:"))

        self.details_body = QGridLayout()
        self.details_body.setHorizontalSpacing(24)
        self.details_body.setVerticalSpacing(3)
        self.details_body.setColumnStretch(1, 1)
        layout.addLayout(self.details_body)

        self.external = QComboBox()
        for key, label in EXTERNAL_CHOICES.items():
            self.external.addItem(label, key)
        self.external.setToolTip("Harici ekranın bu modda açık kalıp kalmayacağı. "
                                 "Harici ekranın Hz'i ve çözünürlüğü değişmez.")
        self.external_hint = muted()
        external_row = QHBoxLayout()
        external_row.addWidget(QLabel("Harici ekran"))
        external_row.addWidget(self.external, 1)
        layout.addSpacing(6)
        layout.addLayout(external_row)
        layout.addWidget(self.external_hint)
        return panel

    def _build_charge(self):
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        title = QLabel("Şarj sınırı")
        title.setStyleSheet("font-weight: 600; font-size: 15px;")
        self.charge_value = QLabel()
        self.charge_value.setStyleSheet("font-weight: 600;")
        top = QHBoxLayout()
        top.addWidget(title)
        top.addStretch()
        top.addWidget(self.charge_value)
        layout.addLayout(top)

        self.charge_slider = QSlider(Qt.Horizontal)
        self.charge_slider.setRange(0, len(CHARGE_LIMITS) - 1)
        self.charge_slider.setPageStep(1)
        self.charge_slider.setTickPosition(QSlider.TicksBelow)
        self.charge_slider.setTickInterval(1)
        self.charge_slider.setToolTip("Pilin dolacağı en yüksek seviye. Modlardan bağımsızdır ve "
                                      "açılışta geri yüklenir. %60 ve %80 pil ömrünü uzatır.")
        self.charge_slider.valueChanged.connect(self._on_charge_moved)
        self.charge_slider.sliderReleased.connect(self._on_charge_moved)
        layout.addWidget(self.charge_slider)

        ticks = QHBoxLayout()
        for limit, align in zip(CHARGE_LIMITS, (Qt.AlignLeft, Qt.AlignHCenter, Qt.AlignRight)):
            label = muted(f"%{limit}")
            label.setWordWrap(False)
            ticks.addWidget(label, 1, align)
        layout.addLayout(ticks)

        self.charge_hint = muted()
        layout.addWidget(self.charge_hint)

        self.charge_timer = QTimer(self)
        self.charge_timer.setSingleShot(True)
        self.charge_timer.setInterval(CHARGE_DELAY_MS)
        self.charge_timer.timeout.connect(self._apply_charge)
        return panel

    def _build_footer(self):
        self.system_label = muted()
        self.log_toggle = QToolButton()
        self.log_toggle.setText("İşlem günlüğü")
        self.log_toggle.setCheckable(True)
        self.log_toggle.setArrowType(Qt.RightArrow)
        self.log_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.log_toggle.setAutoRaise(True)
        self.log_toggle.setToolTip("Son işlemde uygulanan adımlar ve hatalar.")
        self.log_toggle.toggled.connect(self._show_log)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(300)
        self.log.setMinimumHeight(160)
        self.log.setPlaceholderText("Uygulanan adımlar burada görünür.")
        self.log.hide()

        row = QHBoxLayout()
        row.addWidget(self.system_label, 1)
        row.addWidget(self.log_toggle)
        return row

    def _build_action_bar(self):
        bar = QFrame()
        bar.setObjectName("actionBar")
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(20, 10, 20, 12)
        layout.setSpacing(8)

        self.result = Banner()
        layout.addWidget(self.result)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setMaximumHeight(6)
        self.progress.hide()
        layout.addWidget(self.progress)

        self.restore_button = QPushButton(QIcon.fromTheme("edit-undo"), "Önceki ayarlara dön")
        self.restore_button.setToolTip(describe.to_html("Önceki ayarlara dön", describe.RESTORE))
        self.restore_button.clicked.connect(lambda: self._run("geri"))

        self.apply_button = QPushButton(QIcon.fromTheme("dialog-ok-apply"), "Uygula")
        self.apply_button.setMinimumWidth(140)
        self.apply_button.setMinimumHeight(34)
        self.apply_button.setStyleSheet("font-weight: 600;")
        self.apply_button.clicked.connect(lambda: self._run(self.selected))

        row = QHBoxLayout()
        row.addWidget(self.restore_button)
        row.addStretch()
        row.addWidget(self.apply_button)
        layout.addLayout(row)
        return bar

    # ---------- Pencere boyutu ----------

    def showEvent(self, event):
        super().showEvent(event)
        if not self._fitted:
            self._fitted = True
            self.windowHandle().screenChanged.connect(self._fit_to_screen)
            self._fit_to_screen(self.screen())

    def _fit_to_screen(self, screen):
        """Pencere, ölçeği daha büyük bir ekrana taşınınca da ekrana sığsın."""
        if screen is None or self.isMaximized() or self.isFullScreen():
            return
        area = screen.availableGeometry()
        width = min(max(self.width(), PREFERRED_SIZE[0]), area.width() - SCREEN_MARGIN)
        height = min(max(self.height(), PREFERRED_SIZE[1]), area.height() - SCREEN_MARGIN)
        self.resize(max(width, self.minimumWidth()), max(height, self.minimumHeight()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_cards(1 if self.scroll.viewport().width() < ONE_COLUMN_BELOW else 2)

    # ---------- Durum ----------

    @property
    def busy(self):
        return self.runner.is_running()

    def _select(self, key):
        self.selected = key
        preset = PRESETS[key]
        self.cards[key].setChecked(True)
        self.details_title.setText(preset.title)
        self._fill_details(describe.describe(preset, self.caps))

        self.external.setEnabled(not preset.is_battery and not self.busy)
        if preset.is_battery:
            self.external_hint.setText("Batarya modlarında harici ekran kapanır. NVIDIA'ya bağlı "
                                       "çıkışlar (çoğunlukla HDMI) yeniden başlatınca kullanılamaz.")
        else:
            self.external_hint.setText("“Moda göre otomatik”: bağlı harici ekran açık kalır.")
        self.apply_button.setToolTip(self.cards[key].toolTip())
        self._update_apply_text()

    def _fill_details(self, sections):
        while self.details_body.count():
            old = self.details_body.takeAt(0).widget()
            old.hide()  # deleteLater bir sonraki döngüde siler; o ana kadar görünmesin
            old.deleteLater()
        row = 0
        for section, items in sections:
            self.details_body.addWidget(section_label(section), row, 0, 1, 2)
            row += 1
            for label, value in items:
                name = muted(label)
                name.setWordWrap(False)
                text = QLabel(value)
                text.setWordWrap(True)
                self.details_body.addWidget(name, row, 0, Qt.AlignTop)
                self.details_body.addWidget(text, row, 1, Qt.AlignTop)
                row += 1

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
        parts = []
        if self.caps.nvidia:
            parts.append("NVIDIA: " + (GPU_RUNTIME.get(gpu.runtime, gpu.runtime) if gpu.present
                                       else "Devre dışı"))
        if self.caps.ec:
            parts.append("EC: " + status.ec_shift_mode())
        turbo = status.turbo_enabled()
        if turbo is not None:
            parts.append("CPU turbo: " + ("açık" if turbo else "kapalı"))
        self.system_label.setText("  ·  ".join(parts))

        if self.caps.nvidia and gpu.reboot_pending and not self.busy:
            what = "devre dışı kalacak" if gpu.blocked_next_boot else "yeniden kullanılabilir olacak"
            self.reboot_banner.show_message("warn", f"Yeniden başlatınca NVIDIA {what}.")
        else:
            self.reboot_banner.hide()

        self.restore_button.setEnabled(not self.busy and state.has_original())
        self._update_apply_text()
        self._refresh_charge()

    def _refresh_charge(self):
        start, limit = status.charge_limits()
        self.charge_slider.setEnabled(limit is not None and not self.busy)
        if limit is None:
            self.charge_value.setText("—")
            self.charge_hint.setText("Bu bilgisayarda şarj sınırı desteklenmiyor.")
            return
        self.charge_hint.setText(charge_text(status.battery(), start, limit))
        # Kullanıcı kaydırırken ya da uygulanmayı beklerken gerçek değerle ezme.
        if self.busy or self.charge_slider.isSliderDown() or self.charge_timer.isActive():
            return
        self.charge_value.setText(f"%{limit}")
        if str(limit) in CHARGE_LIMITS:
            self.charge_slider.blockSignals(True)
            self.charge_slider.setValue(CHARGE_LIMITS.index(str(limit)))
            self.charge_slider.blockSignals(False)

    def _on_charge_moved(self, *_):
        self.charge_value.setText(f"%{CHARGE_LIMITS[self.charge_slider.value()]}")
        if self.charge_slider.isSliderDown():
            self.charge_timer.stop()
        else:
            self.charge_timer.start()

    def _apply_charge(self):
        limit = CHARGE_LIMITS[self.charge_slider.value()]
        if str(status.charge_limits()[1]) != limit:
            self._run("sarj", limit)

    # ---------- İşlemler ----------

    def _run(self, mode, *extra):
        if self.busy:
            return
        args = [mode, *extra]
        if mode in PRESETS:
            external = "kapat" if PRESETS[mode].is_battery else self.external.currentData()
            args += ["--harici", external]
        self.pending_args = args
        self.log.clear()
        self.result.show_message("warn", "Uygulanıyor… Yönetici parolası istenebilir.")
        self._set_controls_enabled(False)
        self.progress.show()
        self.runner.start(args)

    def _on_finished(self, ok):
        self.progress.hide()
        self._set_controls_enabled(True)
        mode = self.pending_args[0]
        if mode == "sarj":
            name = f"%{self.pending_args[1]} şarj sınırı"
        else:
            name = PRESETS[mode].title if mode in PRESETS else "Önceki ayarlar"
        if ok:
            self.result.show_message("ok", f"{name} uygulandı. Ayrıntılar işlem günlüğünde.")
        else:
            self.result.show_message("error", "İşlem tamamlanamadı. Ayrıntılar işlem günlüğünde.")
            self.log_toggle.setChecked(True)
        self.refresh()

    def _set_controls_enabled(self, enabled):
        for card in self.cards.values():
            card.setEnabled(enabled and card.unsupported is None)
        self.apply_button.setEnabled(enabled)
        self.restore_button.setEnabled(enabled and state.has_original())
        self.external.setEnabled(enabled and not PRESETS[self.selected].is_battery)
        self.charge_slider.setEnabled(enabled and status.charge_limits()[1] is not None)

    def _append_log(self, text):
        self.log.appendPlainText(text)

    def _show_log(self, visible):
        self.log.setVisible(visible)
        self.log_toggle.setArrowType(Qt.DownArrow if visible else Qt.RightArrow)
        if visible:
            QTimer.singleShot(0, lambda: self.scroll.ensureWidgetVisible(self.log))

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
