"""Kullanıcı durum dosyalarını (JSON ve günlük) okur/yazar."""
import json
import time

from . import paths


def write_json(path, obj):
    """Önce geçici dosyaya yazıp sonra yer değiştirir; yarım dosya kalmaz."""
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
    temp.chmod(0o600)
    temp.replace(path)


def read_json(path, default=None):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def has_original():
    return paths.ORIGINAL_STATE.exists()


def load_original():
    return json.loads(paths.ORIGINAL_STATE.read_text())


def save_original(snapshot):
    write_json(paths.ORIGINAL_STATE, snapshot)


def load_active():
    """{'mode': ..., 'external': ...} ya da hiç mod seçilmediyse None."""
    return read_json(paths.ACTIVE_STATE)


def save_active(mode, external):
    write_json(paths.ACTIVE_STATE, {"mode": mode, "external": external})


def load_layouts():
    """display.remember() kayıtları: ekran kombinasyonu → düzen."""
    return read_json(paths.LAYOUTS, {})


def save_layout(outputs):
    """Kullanıcının şu anki ekran düzenini kendi kombinasyonu için saklar (diğerleri korunur)."""
    from . import display
    layouts = load_layouts()
    layouts.update(display.remember(outputs))
    write_json(paths.LAYOUTS, layouts)


def forget_all():
    """Geri dönüş tamamlanınca kayıtları temizler."""
    paths.ORIGINAL_STATE.unlink()
    paths.ACTIVE_STATE.unlink(missing_ok=True)


def log_history(mode, external):
    with paths.HISTORY_LOG.open("a") as log:
        log.write(time.strftime("%Y-%m-%d %H:%M:%S ") + f"{mode} {external}\n")
