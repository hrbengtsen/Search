#!/usr/bin/env python3
"""⌘← and ⌘→ in a peek's text box move the caret, as in a tab's, in a hidden
probe.

Build first (`./build.sh`), then `python3 Tests/peek_caret_keys.py`. It uses
the split suite's harness in a world of its own (peek-caret-keys): started
hidden, everything removed afterwards.

The peek's page has the keys, as a click on it leaves them, and the caret is
in its text box: ⌘← goes to the start of the line and ⌘→ to the end, and the
tab under the peek stays on its page. They took that tab back and forward,
as whether the caret was in a text box was asked of it, not of the peek.
With nothing being typed, ⌘← is Back, as before.
"""
import http.server
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import split_view as sv  # noqa: E402

sv.use("peek-caret-keys")
t = sv.T()

WORDS = "hello world"
PAGE = f"<!doctype html><title>box</title><input id=box value='{WORDS}'>".encode()


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(PAGE))); self.end_headers(); self.wfile.write(PAGE)

    def log_message(self, *a): pass


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=server.serve_forever, daemon=True).start()
BOX = f"http://localhost:{server.server_port}/box"
LEFT, RIGHT = (123, ""), (124, "")


def until(check, seconds=4):
    for _ in range(int(seconds * 10)):
        if check(): return True
        time.sleep(0.1)
    return False


def peek_js(js): return sv.cmd({"do": "peek", "js": js}).get("value")
def caret(): return peek_js("document.getElementById('box').selectionStart")
def shown(): return sv.cmd({"do": "probe"})["peekShown"]


def at(tab):
    return next((x.get("url") for x in sv.cmd({"do": "tabs"})["tabs"] if x["id"].startswith(tab) or tab.startswith(x["id"])), None)


def press(key):
    sv.cmd({"do": "press", "code": key[0], "chars": key[1], "mods": ["cmd", "arrow"]}); time.sleep(0.6)


try:
    sv.setup(); sv.launch()
    # The tab under the peek has a page to go back to and one to go forward to.
    under = sv.cmd({"do": "open", "url": f"{sv.BASE}/one"})["id"]; time.sleep(1)
    for name in ("two", "three"):
        sv.cmd({"do": "go", "id": under, "url": f"{sv.BASE}/{name}"}); time.sleep(0.8)
    sv.cmd({"do": "eval", "id": under, "js": "history.back(); 0"})
    TWO = f"{sv.BASE}/two"
    t.ok("the tab under the peek can go back and forward", until(lambda: at(under) == TWO), at(under))
    sv.cmd({"do": "select", "id": under}); time.sleep(0.4)

    sv.cmd({"do": "peek", "url": BOX})
    t.ok("a peek with a text box", until(lambda: shown() and peek_js("!!document.getElementById('box')") is True))
    t.ok("its page has the keys", sv.cmd({"do": "peek", "focus": True}).get("keys") is True)
    peek_js("var b = document.getElementById('box'); b.focus(); b.setSelectionRange(5, 5); 0"); time.sleep(0.4)

    press(LEFT)
    t.ok("⌘← in the peek's text box goes to the start of the line", until(lambda: caret() == 0), caret())
    t.ok("…and the tab under the peek stays on its page", at(under) == TWO, at(under))
    press(RIGHT)
    t.ok("⌘→ goes to the end of the line", until(lambda: caret() == len(WORDS)), caret())
    t.ok("…and the tab under the peek stays on its page", at(under) == TWO, at(under))
    t.ok("the peek stays up", shown())

    peek_js("document.activeElement.blur(); 0"); time.sleep(0.4)
    press(LEFT)
    t.ok("with nothing being typed, ⌘← is Back, as before", until(lambda: at(under) == f"{sv.BASE}/one"), at(under))
finally:
    t.done(); sv.finish(); server.shutdown()
sys.exit(1 if t.failed else 0)
