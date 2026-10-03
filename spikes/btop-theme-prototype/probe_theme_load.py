#!/usr/bin/env python3
"""Probe: does btop provably LOAD and APPLY a theme, headlessly?"""
import fcntl, os, pathlib, pty, select, struct, subprocess, sys, termios, time

def run(theme_value, timeout=3.0):
    root = pathlib.Path(os.path.abspath(f"run-{theme_value or 'none'}"))
    shutil_clean(root)
    (root / "state").mkdir(parents=True); (root / "config/btop/themes").mkdir(parents=True)
    shutil = __import__("shutil")
    for t in ("minimal", "balanced", "full"):
        shutil.copy(f"config/btop/themes/csg-{t}.theme", root / f"config/btop/themes/csg-{t}.theme")
    conf = f'color_theme = "{theme_value}"\nlog_level = "DEBUG"\nupdate_ms = 3000\n' if theme_value else 'log_level = "DEBUG"\nupdate_ms = 3000\n'
    (root / "config/btop/btop.conf").write_text(conf)
    env = dict(os.environ, XDG_STATE_HOME=str(root/"state"), XDG_CONFIG_HOME=str(root/"config"),
               TERM="xterm-256color", COLORTERM="truecolor")
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 200, 0, 0))
    p = subprocess.Popen(["btop", "--no-tty"], stdin=slave, stdout=slave, stderr=slave, env=env, close_fds=True)
    os.close(slave)
    time.sleep(timeout)
    p.terminate()
    try: p.wait(timeout=5)
    except Exception: p.kill()
    os.set_blocking(master, False)
    buf = b""
    while True:
        r, _, _ = select.select([master], [], [], 0.5)
        if not r: break
        try: d = os.read(master, 65536)
        except OSError: break
        if not d: break
        buf += d
    os.close(master)
    return buf, (root / "state/btop.log").read_text()

def shutil_clean(p):
    import shutil as s
    if p.exists(): s.rmtree(p)

for tv in ("csg-minimal.theme", "csg-balanced.theme", "csg-full.theme", "nonexistent.theme"):
    buf, log = run(tv)
    loaded = [l.split("Loading theme file: ")[-1] for l in log.splitlines() if "Loading theme file:" in l]
    fallback = "theme_path.empty" if not loaded else "-"
    print(f"color_theme={tv!r:24s} frame={len(buf):6d}B  loaded={loaded[0].rsplit('/',1)[-1] if loaded else 'NONE (fell back to Default)'}")
