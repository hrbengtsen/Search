#!/usr/bin/env python3
"""A peek's page is drawn on whole pixels, as sharp as the same page in a tab,
and the page under it is covered as ⌘T's and ⌘L's field covers it.

Build first (`./build.sh`), then `python3 Tests/peek_crisp.py`. A hidden
probe in a world of its own (split_view.py's harness).

Before: the panel grew into place from 98%, and WebKit sizes the page's
root layer from where its view is seen as it comes: seen scaled, that was
between two pixels, and it stayed there until the window's size next
changed. The view's own frame was whole; everything WebKit drew in it sat
a fraction of a pixel off (0.42 at 1301 points across), every line of
text resampled and a little soft. The panel now fades in. And the page
under it was dimmed with black at 22%, where the field lays the window's
ground over it at 74%: two looks for the same thing, the peek's barely
there in dark. The peek now has the field's (Palette.cover).

The probe reads how far the peek's page is from the screen's pixels: the
most any corner of its layers, WebKit's own included, is off them (Bench
"probe" peekOffGrid), and the page in front's the same way beside it. At
sizes that left fractions before, in the column, as a card and with the
tabs across the top; after a pinch let go; and when a peek that stays with
its tab comes back with it. The cover is read from a picture of the
window's layers beside the panel, then beside ⌘L's field, light and dark.
"""
import os, sys, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import split_view as sv  # noqa: E402

sv.use("peek-crisp")
t = sv.T()
SIZES = [(1200, 760), (1237, 803), (1111, 689), (1301, 777)]


def start(**prefs):
    sv.setup(**prefs)
    os.makedirs(sv.SUPPORT, exist_ok=True)
    json.dump({"tabs": [{"url": f"{sv.BASE}/tall", "title": "tall"}], "active": 0},
              open(f"{sv.SUPPORT}/session.json", "w"))
    sv.launch()


def peek_up():
    sv.cmd({"do": "peek", "url": f"{sv.BASE}/peeked"})
    time.sleep(1.2)  # come in and settled


def crisp(what, key="peekOffGrid"):
    p = sv.cmd({"do": "probe"})
    t.ok(f"{what}: on whole pixels", p.get(key, 1) < 0.02, {key: p.get(key)})


try:
    for name, prefs in [("column", {"sidebar": True}), ("column, cards", {"sidebar": True, "layout.cards": True}),
                        ("tabs across the top", {"sidebar": False})]:
        start(**prefs)
        for w, h in SIZES:
            sv.cmd({"do": "resize", "width": w, "height": h, "steps": 1}); time.sleep(0.8)
            peek_up()
            crisp(f"{name}, {w}×{h}: the page in front", "pageOffGrid")
            crisp(f"{name}, {w}×{h}: the peek's page")
            sv.cmd({"do": "peek", "url": "close"}); time.sleep(0.6)
        sv.quit()

    start(sidebar=True)
    sv.cmd({"do": "resize", "width": 1301, "height": 777, "steps": 1}); time.sleep(0.8)
    peek_up()
    sv.cmd({"do": "peek", "pinch": [0.05, 0.05, 0.05]}); time.sleep(1.0)
    crisp("a small pinch let go: the peek's page")
    # Settings › Keyboard & Mouse › Peek stays with its tab: another tab
    # hides it, and coming back brings it in again.
    sv.cmd({"do": "ui", "peekstays": True})
    first = sv.cmd({"do": "tabs"})["tabs"][0]["id"]
    other = sv.cmd({"do": "open", "url": f"{sv.BASE}/a"})["id"]; time.sleep(1.0)
    sv.cmd({"do": "select", "id": other}); time.sleep(0.8)
    shown = sv.cmd({"do": "probe"})["peekShown"]
    sv.cmd({"do": "select", "id": first}); time.sleep(1.2)
    p = sv.cmd({"do": "probe"})
    t.ok("peek stays: hidden behind another tab, then back", not shown and p["peekShown"], (shown, p["peekShown"]))
    crisp("peek stays, back with its tab: the peek's page")
    sv.quit()

    # The cover beside the panel, then beside the field, in both looks. The
    # tabs across the top, so the page starts at the window's left edge.
    from PIL import Image
    start(sidebar=False)
    sv.cmd({"do": "resize", "width": 1200, "height": 760, "steps": 1}); time.sleep(0.8)
    shots = os.environ.get("PEEK_CRISP_SHOTS", sv.SUPPORT)

    def cover(tag):
        shot = sv.cmd({"do": "layershot", "path": f"{shots}/{tag}", "wide": True, "frames": 1})
        im = Image.open(shot["frames"][0]["file"]).convert("RGB")
        # 12 points in, halfway down: under the cover, clear of the panel
        # and its shadow, and of the field and its list.
        return im.getpixel((int(12 * shot["scale"]), im.size[1] // 2))

    seen = {}
    peek_up()
    for look in ("light", "dark"):
        sv.cmd({"do": "ui", "look": look}); time.sleep(0.6)
        seen[("peek", look)] = cover(f"peek-{look}")
    sv.cmd({"do": "peek", "url": "close"}); time.sleep(0.6)
    sv.cmd({"do": "field", "text": "a"}); time.sleep(0.8)
    for look in ("light", "dark"):
        sv.cmd({"do": "ui", "look": look}); time.sleep(0.6)
        seen[("field", look)] = cover(f"field-{look}")
    for look in ("light", "dark"):
        a, b = seen[("peek", look)], seen[("field", look)]
        t.ok(f"{look}: the page under a peek is covered as under the field",
             sum(abs(x - y) for x, y in zip(a, b)) <= 6, {"peek": a, "field": b})
finally:
    t.done(); sv.finish()
sys.exit(1 if t.failed else 0)
