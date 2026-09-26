"""Ana pencere: durum → mod seç → neyin değişeceğine bak → Uygula.

Donanıma dokunmaz; her işlemi CLI'ye (runner) yaptırır. Tepsi ve otomatik mod da
buradaki apply_mode / apply_charge'ı kullanır; böylece tek bir işlem kuyruğu olur.
"""
import shutil

from PySide6.QtCore import QProcess, Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QFrame,
                               QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QProgressBar,
                               QPushButton, QScrollArea, QToolButton, QVBoxLayout, QWidget)

from .. import capabilities, controller, describe, settings, state, status, system
from ..i18n import _
from ..presets import EXTERNAL_CHOICES, PRESETS
from .changes import ChangesPanel
from .charge import ChargePanel
from .runner import ModeRunner
from .settings_dialog import SettingsDialog, set_autostart
from .status_strip import StatusStrip
from .widgets import STYLE, Banner, ModeCard, link_button, muted

REFRESH_MS = 2000
PREVIEW_EVERY = 8      # değişiklik listesi her 8 yenilemede bir (≈16 sn) yeniden hesaplanır
PREFERRED_SIZE = (600, 820)
SCREEN_MARGIN = 32     # pencere ile ekran kenarı arasında bırakılan boşluk


def detect_capabilities():
    try:
        outputs = system.get_outputs()
    except Exception:
        outputs = []  # kscreen-doctor çalışmazsa Hz bilinmez
    return capabilities.detect(outputs)


def missing_features(caps):
    notes = []
    if not caps.ec:
        notes.append(_("The msi-ec driver was not found: fan, EC mode and Cooler Boost cannot be "
                       "changed (AUR: msi-ec-dkms-git)."))
    if not caps.screen:
        notes.append(_("KDE Plasma 6 was not found: refresh rate and brightness are not changed."))
    if caps.conflicts:
        notes.append(_("{services} is running and conflicts with power profiles; modes may fail to "
                       "verify. Disable one of them.").format(services=", ".join(caps.conflicts)))
    return " ".join(notes)


class LogDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(_("Activity log"))
        self.resize(620, 380)
        layout = QVBoxLayout(self)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(500)
        self.text.setPlaceholderText(_("Applied steps appear here."))
        layout.addWidget(self.text)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.hide)
        layout.addWidget(buttons)


class MainWindow(QWidget):
    finished = Signal(str, bool)  # (işlem adı, başarılı mı) — tepsi bildirimleri için

    def __init__(self):
        super().__init__()
        self.setWindowTitle(_("Power Modes"))
        self.setWindowIcon(QIcon.fromTheme("battery-profile-balanced"))
        self.setStyleSheet(STYLE)
        self.setMinimumSize(380, 360)
        self.resize(*PREFERRED_SIZE)
        self._fitted = False
        self._ticks = 0
        self.quit_on_close = True  # tepsi varsa False; pencere kapanınca gizlenir

        self.caps = detect_capabilities()
        self.runner = ModeRunner(self)
        self.runner.output.connect(self._append_log)
        self.runner.finished.connect(self._on_finished)
        self.pending = None      # (args, görünen ad, değişen ayar sayısı)
        self.log_dialog = LogDialog(self)
        self.selected = None
        self._change_count = 0

        content = QWidget()
        content.setObjectName("content")
        body = QVBoxLayout(content)
        body.setContentsMargins(20, 18, 20, 16)
        body.setSpacing(12)
        body.addLayout(self._build_header())
        self.status_strip = StatusStrip(self.caps)
        body.addWidget(self.status_strip)
        body.addWidget(self._build_reboot_banner())
        body.addWidget(self._build_capability_banner())
        body.addLayout(self._build_modes())
        body.addLayout(self._build_external())
        self.changes = ChangesPanel()
        body.addWidget(self.changes.widget)
        self.charge = ChargePanel()
        self.charge.requested.connect(self.apply_charge)
        body.addWidget(self.charge.widget)
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
        self.external.setCurrentIndex(max(0, self.external.findData(active.get("harici", "otomatik"))))
        self._select(initial)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(REFRESH_MS)
        self.refresh()

    # ---------- Arayüzün kurulumu ----------

    def _build_header(self):
        title = QLabel(_("Power Modes"))
        title.setStyleSheet("font-size: 22px; font-weight: 600;")
        self.subtitle = muted(self.caps.model)
        left = QVBoxLayout()
        left.setSpacing(2)
        left.addWidget(title)
        left.addWidget(self.subtitle)

        settings_button = QToolButton()
        settings_button.setIcon(QIcon.fromTheme("configure"))
        settings_button.setAutoRaise(True)
        settings_button.setToolTip(_("Settings"))
        settings_button.clicked.connect(self.open_settings)

        header = QHBoxLayout()
        header.addLayout(left, 1)
        header.addWidget(settings_button, 0, Qt.AlignTop)
        return header

    def _build_reboot_banner(self):
        self.reboot_banner = Banner(_("Restart"))
        self.reboot_banner.action.connect(self._reboot)
        return self.reboot_banner

    def _build_capability_banner(self):
        self.capability_banner = Banner()
        notes = missing_features(self.caps)
        if notes:
            self.capability_banner.show_message("warn", notes)
        return self.capability_banner

    def _build_modes(self):
        self.cards = {}
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        layout = QVBoxLayout()
        layout.setSpacing(8)
        for preset in PRESETS.values():
            card = ModeCard(preset)
            card.clicked.connect(lambda _checked=False, key=preset.key: self._select(key))
            self.group.addButton(card)
            self.cards[preset.key] = card
            layout.addWidget(card)
        self._update_card_info()
        return layout

    def _update_card_info(self):
        options = settings.load()
        for preset in PRESETS.values():
            reason = capabilities.unsupported_reason(preset, self.caps)
            sections = describe.describe(preset, self.caps, options)
            self.cards[preset.key].set_info(describe.to_html(preset.title, sections, reason), reason)

    def _build_external(self):
        self.external = QComboBox()
        for key, label in EXTERNAL_CHOICES.items():
            self.external.addItem(_(label), key)
        self.external.setToolTip(_("Whether external displays stay on in this mode. Their "
                                   "refresh rate and resolution never change."))
        self.external.currentIndexChanged.connect(lambda _index: self._refresh_preview())
        self.external_label = QLabel(_("External displays"))
        self.external_hint = muted()
        row = QHBoxLayout()
        row.addWidget(self.external_label)
        row.addWidget(self.external, 1)
        box = QVBoxLayout()
        box.setSpacing(4)
        box.addLayout(row)
        box.addWidget(self.external_hint)
        return box

    def _build_action_bar(self):
        bar = QFrame()
        bar.setObjectName("actionBar")
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(20, 10, 20, 12)
        layout.setSpacing(8)

        self.result = Banner(_("Show log"))
        self.result.action.connect(self.show_log)
        layout.addWidget(self.result)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setMaximumHeight(4)
        self.progress.hide()
        layout.addWidget(self.progress)

        self.restore_button = link_button(_("Restore previous settings"), "edit-undo")
        self.restore_button.setToolTip(describe.to_html(_("Restore previous settings"),
                                                        describe.restore_sections()))
        self.restore_button.clicked.connect(lambda: self._run(["geri"], _("Previous settings")))

        self.apply_button = QPushButton(QIcon.fromTheme("dialog-ok-apply"), _("Apply"))
        self.apply_button.setObjectName("primary")
        self.apply_button.setDefault(True)
        self.apply_button.setMinimumHeight(36)
        self.apply_button.clicked.connect(lambda: self.apply_mode(self.selected))

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

    # ---------- Durum ----------

    @property
    def busy(self):
        return self.runner.is_running()

    def active_mode(self):
        return (state.load_active() or {}).get("mod")

    def _select(self, key):
        self.selected = key
        self.cards[key].setChecked(True)
        self.apply_button.setToolTip(self.cards[key].toolTip())
        self._refresh_preview()

    def _refresh_preview(self):
        """Seçili modun şu anki duruma göre değiştireceklerini hesaplar (hiçbir şey uygulamaz)."""
        if self.selected is None or self.busy:
            return
        preset = PRESETS[self.selected]
        sections = describe.describe(preset, self.caps, settings.load())
        try:
            prepared = controller.prepare(self.selected, self.external.currentData())
            rows = describe.changes(prepared.plan, prepared.before, status.gpu().blocked_next_boot)
            error = None
            outputs = prepared.before["outputs"]
        except Exception as exc:
            rows, error, outputs = [], str(exc), []
        self._change_count = len(rows)
        self.changes.show(rows, sections, error)
        self.apply_button.setEnabled(error is None)
        self._update_external(preset, outputs)
        self._update_apply_text()

    def _update_external(self, preset, outputs):
        externals = [o for o in outputs if o["connected"] and not o["name"].startswith(("eDP", "LVDS", "DSI"))]
        visible = bool(externals)
        for widget in (self.external_label, self.external):
            widget.setVisible(visible)
        on_nvidia = [o["name"] for o in externals if o["name"] in self.caps.nvidia_outputs]
        if preset.is_battery and on_nvidia:
            self.external_hint.setText(_("{outputs} is wired to NVIDIA: it turns off in battery mode "
                                         "and cannot be used until NVIDIA is back.").format(
                                           outputs=", ".join(on_nvidia)))
        else:
            self.external_hint.setText("")
        self.external_hint.setVisible(visible and bool(self.external_hint.text()))

    def _update_apply_text(self):
        again = self.active_mode() == self.selected
        self.apply_button.setText(_("Apply again") if again else _("Apply"))

    def refresh(self):
        self.status_strip.refresh()
        active = self.active_mode()
        for key, card in self.cards.items():
            card.set_active(key == active)
        active_text = (_("Active mode: {mode}").format(mode=PRESETS[active].title) if active in PRESETS
                       else _("No mode applied yet (system settings)"))
        self.subtitle.setText(" · ".join(x for x in (self.caps.model, active_text) if x))

        gpu = status.gpu()
        if self.caps.nvidia and gpu.reboot_pending and not self.busy:
            message = (_("NVIDIA will be disabled after a restart.") if gpu.blocked_next_boot
                       else _("NVIDIA will be available again after a restart."))
            self.reboot_banner.show_message("warn", message)
        else:
            self.reboot_banner.hide()

        self.restore_button.setEnabled(not self.busy and state.has_original())
        self.charge.refresh(self.busy)
        self._update_apply_text()
        self._ticks += 1
        if self._ticks % PREVIEW_EVERY == 0:
            self._refresh_preview()

    # ---------- İşlemler (tepsi ve otomatik mod da kullanır) ----------

    def apply_mode(self, key, external=None, keep_gpu=False):
        external = external or self.external.currentData()
        args = [key, "--harici", external] + (["--gpu-koru"] if keep_gpu else [])
        count = self._change_count if key == self.selected else None
        return self._run(args, PRESETS[key].title, count)

    def apply_charge(self, limit):
        if str(status.charge_limits()[1]) == limit:
            return True
        return self._run(["sarj", limit], _("{limit}% charge limit").format(limit=limit))

    def set_passwordless(self, enabled):
        state_text = _("on") if enabled else _("off")
        return self._run(["passwordless", "on" if enabled else "off"],
                         _("Password-free switching {state}").format(state=state_text))

    def _run(self, args, name, count=None):
        if self.busy:
            return False
        self.pending = (args, name, count)
        self.log_dialog.text.clear()
        self.result.show_message("warn", _("Applying {name}… An administrator password may be "
                                           "requested.").format(name=name))
        self._set_controls_enabled(False)
        self.progress.show()
        self.runner.start(args)
        return True

    def _on_finished(self, ok):
        self.progress.hide()
        self._set_controls_enabled(True)
        _args, name, count = self.pending
        if ok:
            text = _("{name} applied.").format(name=name)
            if count:
                text += " " + _("{count} settings changed.").format(count=count)
            self.result.show_message("ok", text)
        else:
            self.result.show_message("error", _("{name} could not be applied. See the log for "
                                                "details.").format(name=name))
        self.finished.emit(name, ok)
        self.refresh()
        self._refresh_preview()

    def _set_controls_enabled(self, enabled):
        for card in self.cards.values():
            card.setEnabled(enabled and card.unsupported is None)
        self.apply_button.setEnabled(enabled)
        self.restore_button.setEnabled(enabled and state.has_original())
        self.external.setEnabled(enabled)
        self.charge.refresh(not enabled)

    def _append_log(self, text):
        self.log_dialog.text.appendPlainText(text)

    def show_log(self):
        self.log_dialog.show()
        self.log_dialog.raise_()

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        before = settings.load()
        values = dialog.values()
        settings.save(values)
        if values["tray_autostart"] != before["tray_autostart"]:
            set_autostart(values["tray_autostart"])
        self._update_card_info()
        self._refresh_preview()
        self.settings_changed(before, values)
        if values["passwordless"] != before["passwordless"]:
            if not self.set_passwordless(values["passwordless"]):
                settings.save({"passwordless": before["passwordless"]})
        if values["language"] != before["language"]:
            QMessageBox.information(self, _("Language"),
                                    _("The new language is used after the app restarts."))

    def settings_changed(self, before, after):
        """Tepsi/otomatik mod kancası; app.py bağlar."""

    def _reboot(self):
        # KDE'nin kendi onay penceresini açar; açık uygulamalar düzgün kapanır.
        if shutil.which("qdbus6"):
            QProcess.startDetached("qdbus6", ["org.kde.LogoutPrompt", "/LogoutPrompt", "promptReboot"])
        elif QMessageBox.question(self, _("Restart"), _("Restart the computer now?")) \
                == QMessageBox.Yes:
            QProcess.startDetached("systemctl", ["reboot"])

    def closeEvent(self, event):
        if self.busy and self.quit_on_close:
            QMessageBox.information(self, _("Still working"),
                                    _("You can close the window when the settings are applied."))
            event.ignore()
            return
        event.accept()
