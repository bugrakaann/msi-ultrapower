"""Display planning: builds kscreen-doctor arguments and verifies the result.

These functions change nothing; they only take and return data, so they can be
tested without a real display.
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
    """Refresh rates the display supports at its current resolution (ascending)."""
    if not output.get("modes"):
        return []
    size = _old_mode(output)["size"]
    return sorted({round(m["refreshRate"]) for m in output["modes"] if m["size"] == size})


def panel_rates(outputs):
    """Refresh rates of the built-in display; empty list without one."""
    panel = next((o for o in outputs if o["connected"] and is_internal(o)), None)
    return refresh_rates(panel) if panel else []


def mode_for(output, previous=None, hz=None):
    """Id of the mode closest to the wanted refresh rate at the previous resolution.

    hz: a number, "max" (highest), "min" (lowest) or None (keep the previous rate).
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
        return False  # NVIDIA will be off; this output will not work anyway
    if external == "off":
        return False
    # "auto" on battery: displays not wired to NVIDIA (iGPU/USB-C) stay on.
    return True


def layout_key(names):
    """Key of a display combination: "HDMI-A-1+eDP-1"."""
    return "+".join(sorted(names))


def remember(outputs):
    """The user's current layout: {key: {name: {pos, priority, scale, size, refresh}}}.

    Stored per combination of enabled displays and restored when that combination returns.
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
    """No gap where a display was turned off: top-left corner at 0,0, priorities numbered from 1."""
    min_x = min(v["pos"]["x"] for v in layout.values())
    min_y = min(v["pos"]["y"] for v in layout.values())
    order = sorted(layout, key=lambda n: layout[n]["priority"])
    return {n: {**v, "pos": {"x": v["pos"]["x"] - min_x, "y": v["pos"]["y"] - min_y},
                "priority": order.index(n) + 1} for n, v in layout.items()}


def _target_layout(connected, targets, remembered):
    """Position, priority and scale of the displays that stay on.

    1. If the enabled displays do not change, the current layout is kept as is.
    2. If a layout was remembered for this combination, it is used.
    3. Otherwise displays that stay on keep their place and newly enabled ones go to the right.
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
    """Built-in display: the mode's refresh rate; external: its current mode, or the remembered one when re-enabled."""
    if hz is not None:
        return mode_for(output, None, hz)
    if not output["enabled"] and saved and "size" in saved:
        same = [m for m in output["modes"] if m["size"] == saved["size"]]
        if same:
            return min(same, key=lambda m: abs(m["refreshRate"] - saved["refresh"]))["id"]
    return mode_for(output)


def screen_plan(current, original, preset=None, external="auto", nvidia_outputs=(), remembered=None):
    """kscreen-doctor arguments.

    With a preset, the mode is applied: the user's layout (primary display, position, scale,
    external resolution) is left alone; only the built-in refresh rate and brightness and which
    displays are on change. With None, the layout in `original` is restored.
    nvidia_outputs: names of outputs wired to NVIDIA; they are turned off in battery modes.
    remembered: display.remember() records; a re-enabled display gets its place from here.
    Without display information (not KDE) an empty list is returned and the step is skipped.
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
        # The external refresh rate is never touched; the user's own choice is kept.
        mode_id = _mode_id(output, preset.panel if internal else None, saved.get(output["name"]))
        args += [prefix + "enable", prefix + "mode." + mode_id, prefix + f"scale.{place['scale']}",
                 prefix + f"position.{place['pos']['x']},{place['pos']['y']}",
                 prefix + f"priority.{place['priority']}"]
        # Before Plasma 6.1 there is no brightness information; brightness is then left alone.
        if internal and "brightness" in output:
            args.append(prefix + f"brightness.{preset.brightness}")
    return args


def _restore_plan(current, original):
    """Restores the layout from before the first mode; displays not in that snapshot stay as they are."""
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
    """Checks that the applied arguments really took effect."""
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
