"""Fake kscreen-doctor output used by the tests."""


def fake_output(name, ids=("old", "new")):
    size = {"width": 1920, "height": 1080}
    return dict(name=name, connected=True, enabled=True, scale=1.25, priority=1, brightness=1,
                pos={"x": 0, "y": 0}, currentModeId=ids[0],
                modes=[dict(id=ids[0], refreshRate=120.11, size=size),
                       dict(id=ids[1], refreshRate=59.96, size=size),
                       dict(id="low", refreshRate=48.08, size=size)])
