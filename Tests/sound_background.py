#!/usr/bin/env python3
"""Music goes on to the next track in a tab behind, in a hidden probe.

Build first (`./build.sh`), then `python3 Tests/sound_background.py`. It uses
the split suite's harness: started hidden, no window made or shown, removed
afterwards. The pages play WAVs of silence, so nothing is heard, and WebKit
still counts them as making sound, as the tab's speaker does.

A page playing music is kept in the window, unseen, while another tab is in
front, as a page on a call is (StageView.calls), and for MediaKeys.wait after
it goes quiet: out of the window, the next track fails to start there
(Spotify's "Media failed to decode"; idea 997). Not a page with a video of
its own playing (Tab.playingVideo), muted or heard: that leaves the window
as before. A hidden probe's window is never on screen, so what is checked is
where the page is, not the next track itself; that is checked by hand with
Spotify.
"""
import subprocess
import sys
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import split_view as sv  # noqa: E402

sv.use("bld-sound")
t = sv.T()

WAV = r"""
function wav(seconds) {
  const n = 8000 * seconds, b = new ArrayBuffer(44 + n), v = new DataView(b);
  const s = (o, x) => { for (let i = 0; i < x.length; i++) v.setUint8(o + i, x.charCodeAt(i)); };
  s(0, 'RIFF'); v.setUint32(4, 36 + n, true); s(8, 'WAVE'); s(12, 'fmt ');
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, 8000, true); v.setUint32(28, 8000, true); v.setUint16(32, 1, true); v.setUint16(34, 8, true);
  s(36, 'data'); v.setUint32(40, n, true);
  for (let i = 0; i < n; i++) v.setUint8(44 + i, 128);
  return URL.createObjectURL(new Blob([b], {type: 'audio/wav'}));
}
"""
# Music: a player never put in the page, as Spotify's.
MUSIC = r"""<!doctype html><title>music</title><script>
window.clicks = 0; addEventListener('mousedown', () => clicks++);
""" + WAV + r"""
window.a = new Audio(wav(600)); a.loop = true;
window.state = 'idle';
window.start = () => { a.play().then(() => state = 'playing', e => state = 'refused ' + e.name); return 1; };
window.stop = () => { a.pause(); state = 'paused'; return 1; };
</script>"""
# A video of the page's own, heard: never kept.
FILM = r"""<!doctype html><title>film</title><video id=v loop playsinline></video><script>
""" + WAV + r"""
const v = document.getElementById('v'); v.src = wav(600);
window.state = 'idle'; v.play().then(() => state = 'playing', e => state = 'refused ' + e.name);
</script>"""
# A muted video, playing: no sound, so never kept.
MUTED = r"""<!doctype html><title>muted</title>
<canvas id=c width=64 height=64></canvas><video id=v muted autoplay playsinline></video><script>
const c = document.getElementById('c'), g = c.getContext('2d'); let f = 0;
setInterval(() => { g.fillStyle = `hsl(${f++ % 360},80%,50%)`; g.fillRect(0, 0, 64, 64); }, 40);
const v = document.getElementById('v'); v.srcObject = c.captureStream(25);
window.state = 'idle'; v.play().then(() => state = 'playing', e => state = 'refused ' + e.name);
</script>"""
PLAIN = r"""<!doctype html><title>%s</title><script>
window.clicks = 0; addEventListener('mousedown', () => clicks++);
</script>"""


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        name = self.path.strip("/")
        body = {"music": MUSIC, "film": FILM, "muted": MUTED}.get(name, PLAIN % name).encode()
        self.send_response(200); self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def log_message(self, *a): pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
sv.BASE = f"http://127.0.0.1:{srv.server_port}"


def tab(id): return next(x for x in sv.sp("state")["tabs"] if x["id"] == id)


def kept(id):
    x = tab(id); return x["inWindow"] and x["heldForCall"]


def out(id):
    x = tab(id); return not x["inWindow"] and not x["heldForCall"]


def until(cond, within=6):
    end = time.time() + within
    while time.time() < end:
        if cond(): return True
        time.sleep(0.25)
    return cond()


try:
    sv.setup()
    # The test pages may play by themselves (Autoplay, the site card's switch).
    subprocess.run(["defaults", "write", sv.SUITE, "autoplay.127.0.0.1", "-bool", "true"])
    sv.launch()

    idle = sv.page("idle")
    muted = sv.page("muted")
    t.ok("the muted video plays", until(lambda: sv.ev(muted, "state") == "playing"), sv.ev(muted, "state"))
    film = sv.page("film")
    t.ok("the film plays", until(lambda: sv.ev(film, "state") == "playing"), sv.ev(film, "state"))
    time.sleep(1.5)
    music = sv.page("music")
    sv.ev(music, "start()")
    t.ok("the music plays", until(lambda: sv.ev(music, "state") == "playing"), sv.ev(music, "state"))
    time.sleep(1.5)

    other = sv.page("other"); time.sleep(1)
    st = sv.sp("state")
    t.ok("another tab is in front", st["visibleIDs"] == [other], st["visibleIDs"])
    heard = [x["id"] for x in sv.cmd({"do": "tabs"})["tabs"] if x["noisy"]]
    t.ok("the film and the music are both heard behind", film in heard and music in heard, heard)
    t.ok("behind, playing: the music's page stays in the window", until(lambda: kept(music), within=3), tab(music))
    t.ok("behind, playing: it doesn't have the keys", not tab(music)["hasKeys"], tab(music))
    t.ok("a quiet tab leaves the window as before", out(idle), tab(idle))
    t.ok("a muted video leaves the window as before", out(muted), tab(muted))
    t.ok("a video with sound leaves the window as before", out(film), tab(film))

    # A click on the page in front reaches it, not the page kept under it.
    f = sv.frames(sv.sp("state")).get(other)
    if f:
        x, y = f["x"] + f["width"] / 2, f["y"] + f["height"] / 2
        sv.sp("mouse", points=[[x, y], [x, y]], to="view"); time.sleep(0.5)
        t.ok("a click lands on the page in front", sv.ev(other, "clicks") >= 1, sv.ev(other, "clicks"))
        t.ok("and never on the music kept under it", sv.ev(music, "clicks") == 0, sv.ev(music, "clicks"))
    else:
        t.ok("the page in front has a frame on the stage", False, sv.sp("state").get("paneFrames"))

    # Back to the music: seen again; away again: kept again.
    sv.sp("select", id=music); time.sleep(1)
    m = tab(music)
    t.ok("back: in front, no longer kept unseen",
         sv.sp("state")["visibleIDs"] == [music] and m["inWindow"] and not m["heldForCall"], m)
    sv.sp("select", id=other); time.sleep(1)
    t.ok("away again: kept", until(lambda: kept(music), within=3), tab(music))

    # The track ends behind: kept through the gap, then let go.
    sv.ev(music, "stop()")
    stopped = time.time()
    time.sleep(5)
    t.ok("quiet for 5 s: still kept, for the next track", kept(music), tab(music))
    gone = until(lambda: not tab(music)["inWindow"], within=20)
    t.ok("quiet past the gap: out of the window", gone, tab(music))
    print(f"       let go {time.time() - stopped:.1f} s after it went quiet")
    st = sv.sp("state")
    t.ok("the tab in front is still in front", st["visibleIDs"] == [other] and tab(other)["inWindow"], st["visibleIDs"])

    # Left in the gap: a track over in front, another tab chosen before the
    # next one starts. Kept for it all the same, then let go.
    sv.sp("select", id=music); time.sleep(1)
    sv.ev(music, "start()"); time.sleep(2); sv.ev(music, "stop()"); time.sleep(2)
    sv.sp("select", id=other); time.sleep(1)
    t.ok("left quiet in the gap: kept for the next track", kept(music), tab(music))
    t.ok("left quiet in the gap: let go after it", until(lambda: not tab(music)["inWindow"], within=20), tab(music))
finally:
    t.done(); sv.finish()
sys.exit(1 if t.failed else 0)
