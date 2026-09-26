"""Ekran planlama: kscreen-doctor argümanlarını üretir ve sonucu doğrular.

Buradaki fonksiyonlar hiçbir şeyi değiştirmez; yalnızca veri alıp veri
döndürür. Bu sayede testlerde gerçek ekran olmadan denenebilirler.
"""
from .i18n import _


def is_internal(output):
    return output["name"].startswith(("eDP", "LVDS", "DSI"))


def _old_mode(source):
    old = next((m for m in source["modes"] if m["id"] == source["currentModeId"]), None)
    if old is None:
        preferred = source.get("preferredModes", [])
        old = next((m for m in source["modes"] if m["id"] in preferred), source["modes"][0])
    return old


def refresh_rates(output):
    """Ekranın şu anki çözünürlükte desteklediği yenileme hızları (küçükten büyüğe)."""
    if not output.get("modes"):
        return []
    size = _old_mode(output)["size"]
    return sorted({round(m["refreshRate"]) for m in output["modes"] if m["size"] == size})


def panel_rates(outputs):
    """Dahili ekranın yenileme hızları; dahili ekran yoksa boş liste."""
    panel = next((o for o in outputs if o["connected"] and is_internal(o)), None)
    return refresh_rates(panel) if panel else []


def mode_for(output, previous=None, hz=None):
    """Eski çözünürlükte istenen Hz'e en yakın modun kimliği.

    hz: sayı, "max" (en yüksek), "min" (en düşük) ya da None (eski Hz korunur).
    """
    old = _old_mode(previous or output)
    candidates = [m for m in output["modes"] if m["size"] == old["size"]]
    if not candidates:
        raise RuntimeError(_("{output}: previous resolution not found").format(output=output["name"]))
    if hz == "max":
        return max(candidates, key=lambda m: m["refreshRate"])["id"]
    if hz == "min":
        return min(candidates, key=lambda m: m["refreshRate"])["id"]

    wanted = hz if hz is not None else old["refreshRate"]
    best = min(candidates, key=lambda m: abs(m["refreshRate"] - wanted))
    if abs(best["refreshRate"] - wanted) > 1:
        raise RuntimeError(_("{output}: {hz} Hz is not supported").format(output=output["name"], hz=wanted))
    return best["id"]


def _should_enable(internal, preset, external, on_nvidia):
    if internal:
        return True
    if preset.is_battery and on_nvidia:
        return False  # NVIDIA kapanacak; bu çıkış zaten çalışmayacak
    if external == "kapat":
        return False
    # Bataryada "otomatik": NVIDIA'ya bağlı olmayan (iGPU/USB-C) ekranlar açık kalır.
    return True


def screen_plan(current, original, preset=None, external="otomatik", nvidia_outputs=()):
    """kscreen-doctor argümanları.

    preset verilirse mod uygulanır; None ise `original` içindeki düzen geri yüklenir.
    nvidia_outputs: NVIDIA'ya bağlı bağlantı adları; batarya modunda bunlar kapanır.
    Ekran bilgisi yoksa (KDE dışı) boş liste döner ve ekran adımı atlanır.
    """
    if not current:
        return []
    saved = {o["name"]: o for o in original}
    if preset and not any(o["connected"] and is_internal(o) for o in current):
        raise RuntimeError(_("Built-in display not found"))

    args = []
    enabled_count = 0
    x = 0
    # Dahili ekran önce gelir; böylece en solda ve birincil olur.
    for output in sorted(current, key=lambda o: not is_internal(o)):
        if not output["connected"]:
            continue
        previous = saved.get(output["name"], output)
        internal = is_internal(output)
        prefix = f"output.{output['name']}."

        enabled = (_should_enable(internal, preset, external, output["name"] in nvidia_outputs)
                   if preset else previous["enabled"])
        args.append(prefix + ("enable" if enabled else "disable"))
        if not enabled:
            continue
        enabled_count += 1

        # Harici ekranın Hz'ine dokunulmaz; kullanıcının kendi seçimi korunur.
        hz = preset.panel if preset and internal else None
        mode_id = mode_for(output, previous, hz)
        args += [prefix + "mode." + mode_id, prefix + "scale." + str(previous["scale"])]

        if preset:
            args.append(prefix + f"position.{x},0")
            mode = next(m for m in output["modes"] if m["id"] == mode_id)
            x += round(mode["size"]["width"] / previous["scale"])
            args.append(prefix + f"priority.{enabled_count}")
        else:
            args.append(prefix + f"position.{previous['pos']['x']},{previous['pos']['y']}")
            args.append(prefix + f"priority.{previous.get('priority', enabled_count)}")

        # Plasma 6.1 öncesi parlaklık bilgisi vermez; o zaman parlaklığa dokunulmaz.
        if internal and "brightness" in output and "brightness" in previous:
            brightness = preset.brightness if preset else round(previous["brightness"] * 100)
            args.append(prefix + f"brightness.{brightness}")

    if not enabled_count:
        raise RuntimeError(_("At least one connected display must stay on"))
    return args


def verify_screen(args, before_outputs, actual_outputs):
    """Uygulanan argümanların gerçekten geçerli olduğunu kontrol eder."""
    for arg in args:
        _, name, setting, *value = arg.split(".")
        value = ".".join(value)
        output = next(o for o in actual_outputs if o["name"] == name)

        if setting in ("enable", "disable") and output["enabled"] != (setting == "enable"):
            raise RuntimeError(_("Could not verify display state: {output}").format(output=name))

        if setting == "mode":
            previous = next(o for o in before_outputs if o["name"] == name)
            expected = next(m for m in previous["modes"] if m["id"] == value)
            observed = next(m for m in output["modes"] if m["id"] == output["currentModeId"])
            if (expected["size"] != observed["size"]
                    or abs(expected["refreshRate"] - observed["refreshRate"]) > 1):
                raise RuntimeError(_("Could not verify refresh rate: {output}").format(output=name) + f" {observed}")

        if setting == "brightness" and abs(output["brightness"] * 100 - float(value)) > 2:
            raise RuntimeError(_("Could not verify brightness: {output}").format(output=name))
