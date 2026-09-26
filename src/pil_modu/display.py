"""Ekran planlama: kscreen-doctor argümanlarını üretir ve sonucu doğrular.

Buradaki fonksiyonlar hiçbir şeyi değiştirmez; yalnızca veri alıp veri
döndürür. Bu sayede testlerde gerçek ekran olmadan denenebilirler.
"""


def is_internal(output):
    return output["name"].startswith("eDP")


def mode_for(output, previous=None, hz=None):
    """Eski çözünürlükte, istenen Hz'e (verilmezse eski Hz'e) en yakın modun kimliği."""
    source = previous or output
    old = next((m for m in source["modes"] if m["id"] == source["currentModeId"]), None)
    if old is None:
        preferred = source.get("preferredModes", [])
        old = next((m for m in source["modes"] if m["id"] in preferred), source["modes"][0])

    wanted = hz if hz is not None else old["refreshRate"]
    candidates = [m for m in output["modes"] if m["size"] == old["size"]]
    if not candidates:
        raise RuntimeError(output["name"] + ": eski çözünürlük bulunamadı")
    best = min(candidates, key=lambda m: abs(m["refreshRate"] - wanted))
    if abs(best["refreshRate"] - wanted) > 1:
        raise RuntimeError(output["name"] + f": {wanted} Hz desteklenmiyor")
    return best["id"]


def _should_enable(internal, preset, external):
    return internal or external == "koru" or (external == "otomatik" and not preset.is_battery)


def screen_plan(current, original, preset=None, external="otomatik"):
    """kscreen-doctor argümanları.

    preset verilirse mod uygulanır; None ise `original` içindeki düzen geri yüklenir.
    """
    saved = {o["name"]: o for o in original}
    if preset and not any(o["connected"] and is_internal(o) for o in current):
        raise RuntimeError("Dahili ekran bulunamadı")

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

        enabled = _should_enable(internal, preset, external) if preset else previous["enabled"]
        args.append(prefix + ("enable" if enabled else "disable"))
        if not enabled:
            continue
        enabled_count += 1

        hz = (preset.internal_hz if internal else preset.hz) if preset else None
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

        if internal:
            brightness = preset.brightness if preset else round(previous["brightness"] * 100)
            args.append(prefix + f"brightness.{brightness}")

    if not enabled_count:
        raise RuntimeError("En az bir bağlı ekran açık kalmalı")
    return args


def verify_screen(args, before_outputs, actual_outputs):
    """Uygulanan argümanların gerçekten geçerli olduğunu kontrol eder."""
    for arg in args:
        _, name, setting, *value = arg.split(".")
        value = ".".join(value)
        output = next(o for o in actual_outputs if o["name"] == name)

        if setting in ("enable", "disable") and output["enabled"] != (setting == "enable"):
            raise RuntimeError("Ekran durumu doğrulanamadı: " + name)

        if setting == "mode":
            previous = next(o for o in before_outputs if o["name"] == name)
            expected = next(m for m in previous["modes"] if m["id"] == value)
            observed = next(m for m in output["modes"] if m["id"] == output["currentModeId"])
            if (expected["size"] != observed["size"]
                    or abs(expected["refreshRate"] - observed["refreshRate"]) > 1):
                raise RuntimeError("Ekran frekansı doğrulanamadı: " + name + " " + str(observed))

        if setting == "brightness" and abs(output["brightness"] * 100 - float(value)) > 2:
            raise RuntimeError("Parlaklık doğrulanamadı: " + name)
