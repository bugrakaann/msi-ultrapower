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
    if external == "off":
        return False
    # Bataryada "otomatik": NVIDIA'ya bağlı olmayan (iGPU/USB-C) ekranlar açık kalır.
    return True


def layout_key(names):
    """Bir ekran kombinasyonunun anahtarı: "HDMI-A-1+eDP-1"."""
    return "+".join(sorted(names))


def remember(outputs):
    """Kullanıcının şu anki düzeni: {anahtar: {ad: {pos, priority, scale, size, refresh}}}.

    Açık ekran kombinasyonuna göre saklanır; o kombinasyona dönülünce aynı düzen kurulur.
    """
    enabled = [o for o in outputs if o["connected"] and o["enabled"]]
    if not enabled:
        return {}
    layout = {}
    for o in enabled:
        mode = _old_mode(o)
        layout[o["name"]] = {"pos": o["pos"], "priority": o.get("priority", 1), "scale": o["scale"],
                             "size": mode["size"], "refresh": mode["refreshRate"]}
    return {layout_key(layout): layout}


def _normalized(layout):
    """Kapanan ekranın yerinde boşluk kalmasın: en sol üst köşe 0,0 olsun; öncelikler 1'den sıralı."""
    min_x = min(v["pos"]["x"] for v in layout.values())
    min_y = min(v["pos"]["y"] for v in layout.values())
    order = sorted(layout, key=lambda n: layout[n]["priority"])
    return {n: {**v, "pos": {"x": v["pos"]["x"] - min_x, "y": v["pos"]["y"] - min_y},
                "priority": order.index(n) + 1} for n, v in layout.items()}


def _target_layout(connected, targets, remembered):
    """Açık kalacak ekranların konum/öncelik/ölçeği.

    1. Açık ekranlar değişmiyorsa: şu anki düzen aynen korunur.
    2. Bu kombinasyon için hatırlanan bir düzen varsa: o kullanılır.
    3. Yoksa: açık kalanlar yerinde kalır, yeni açılan sağa eklenir.
    """
    by_name = {o["name"]: o for o in connected}
    current = {o["name"]: {"pos": o["pos"], "priority": o.get("priority", 1), "scale": o["scale"]}
               for o in connected if o["enabled"]}
    if set(current) == set(targets):
        return current
    saved = (remembered or {}).get(layout_key(targets))
    if saved and set(saved) == set(targets):
        return _normalized(saved)

    layout = {n: v for n, v in current.items() if n in targets}
    right = max((v["pos"]["x"] + round(_old_mode(by_name[n])["size"]["width"] / v["scale"])
                 for n, v in layout.items()), default=0)
    for name in targets:
        if name not in layout:
            o = by_name[name]
            layout[name] = {"pos": {"x": right, "y": 0}, "priority": len(layout) + 100, "scale": o["scale"]}
            right += round(_old_mode(o)["size"]["width"] / o["scale"])
    return _normalized(layout)


def _mode_id(output, hz, saved):
    """Dahili ekran için modun Hz'i; harici ekran açıksa şu anki modu, yeniden açılıyorsa hatırlanan modu."""
    if hz is not None:
        return mode_for(output, None, hz)
    if not output["enabled"] and saved and "size" in saved:
        same = [m for m in output["modes"] if m["size"] == saved["size"]]
        if same:
            return min(same, key=lambda m: abs(m["refreshRate"] - saved["refresh"]))["id"]
    return mode_for(output)


def screen_plan(current, original, preset=None, external="auto", nvidia_outputs=(), remembered=None):
    """kscreen-doctor argümanları.

    preset verilirse mod uygulanır: kullanıcının ekran düzenine (ana ekran, konum, ölçek,
    harici ekranın çözünürlüğü) dokunulmaz; yalnızca dahili ekranın Hz'i ve parlaklığı ile
    hangi ekranların açık olacağı değişir. None ise `original` içindeki düzen geri yüklenir.
    nvidia_outputs: NVIDIA'ya bağlı bağlantı adları; batarya modunda bunlar kapanır.
    remembered: display.remember() kayıtları; kapanıp yeniden açılan ekranın yeri buradan gelir.
    Ekran bilgisi yoksa (KDE dışı) boş liste döner ve ekran adımı atlanır.
    """
    if not current:
        return []
    if preset is None:
        return _restore_plan(current, original)
    connected = [o for o in current if o["connected"]]
    if not any(is_internal(o) for o in connected):
        raise RuntimeError(_("Built-in display not found"))

    targets = [o["name"] for o in connected
               if _should_enable(is_internal(o), preset, external, o["name"] in nvidia_outputs)]
    if not targets:
        raise RuntimeError(_("At least one connected display must stay on"))
    layout = _target_layout(connected, targets, remembered)
    saved = (remembered or {}).get(layout_key(targets), {})

    args = []
    for output in sorted(connected, key=lambda o: layout.get(o["name"], {}).get("priority", 99)):
        prefix = f"output.{output['name']}."
        if output["name"] not in layout:
            args.append(prefix + "disable")
            continue
        place = layout[output["name"]]
        internal = is_internal(output)
        # Harici ekranın Hz'ine dokunulmaz; kullanıcının kendi seçimi korunur.
        mode_id = _mode_id(output, preset.panel if internal else None, saved.get(output["name"]))
        args += [prefix + "enable", prefix + "mode." + mode_id, prefix + f"scale.{place['scale']}",
                 prefix + f"position.{place['pos']['x']},{place['pos']['y']}",
                 prefix + f"priority.{place['priority']}"]
        # Plasma 6.1 öncesi parlaklık bilgisi vermez; o zaman parlaklığa dokunulmaz.
        if internal and "brightness" in output:
            args.append(prefix + f"brightness.{preset.brightness}")
    return args


def _restore_plan(current, original):
    """İlk moddan önceki düzeni geri yükler; o kayıtta olmayan ekranlar şu anki haliyle kalır."""
    saved = {o["name"]: o for o in original}
    args = []
    enabled_count = 0
    for output in current:
        if not output["connected"]:
            continue
        previous = saved.get(output["name"], output)
        prefix = f"output.{output['name']}."
        if not previous["enabled"]:
            args.append(prefix + "disable")
            continue
        enabled_count += 1
        args += [prefix + "enable", prefix + "mode." + mode_for(output, previous),
                 prefix + "scale." + str(previous["scale"]),
                 prefix + f"position.{previous['pos']['x']},{previous['pos']['y']}",
                 prefix + f"priority.{previous.get('priority', enabled_count)}"]
        if is_internal(output) and "brightness" in output and "brightness" in previous:
            args.append(prefix + f"brightness.{round(previous['brightness'] * 100)}")
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
