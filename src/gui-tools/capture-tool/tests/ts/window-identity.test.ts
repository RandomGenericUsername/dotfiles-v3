// ---------------------------------------------------------------------------
// Window IDENTITY tests (fix-capture-window-identity).
//
// The bug these pin: `ClassicWindow` resolved "my own window" through
// `app.get_window("capture-window")`. `app.tsx` builds one window per monitor and
// every window carries that same name, so the lookup could not mean "this
// window" — it meant "whichever duplicate AGS's `windows.find(...)` reached
// first", and that answer MOVES as windows are mapped and unmapped. Measured
// live on this host, two real `ClassicWindow`s on one monitor:
//
//   app.windows order        get_window("capture-window") resolved to
//   B,A  (fresh, unmapped)   B      <- the window that was NOT pressed
//   A,B  (after map/unmap)   A
//
// Reproduced live, both windows visible, capture pressed on window A:
// pre-fix left A VISIBLE and unmapped B. That is the reported defect, confirmed.
//
// WHAT IS AND IS NOT TESTABLE HERE. `ClassicWindow` is a `.tsx` importing
// `ags/gtk4` and `gi://GLib`; `node --test` has no GTK and no display, so it
// cannot construct one. The suite therefore pins three reachable things:
//
//   1. the LOOKUP SEMANTICS, executed — a faithful model of AGS's
//      `windows.find(...)` over an order that is not registration order, driving
//      both the old name-scoped hide and the new self-scoped one. The old one
//      must demonstrably hide the wrong window (the negative control), and the
//      new one must not.
//   2. the WIRING, read from the real `ClassicWindow.tsx` — no `get_window`
//      call survives, and the self-reference is per-CALL rather than per-module.
//   3. the NAME CONTRACT, read across files — the window's `name`, the
//      stylesheet's `window#...` id selector and the provisioned launcher's
//      `WINDOW=` all still agree. A rename that misses the launcher would leave
//      the keybind addressing a window that does not exist, which is exactly the
//      failure `extract-capture-gui-tool/proposal.md` records from the last time
//      this name moved.
//
// (1) is a model, not the window, and is labelled as one. The end-to-end proof
// is the harness described in the change's design.md.
// ---------------------------------------------------------------------------

import { test } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"

const WINDOW = fileURLToPath(new URL("../../ui/classic/ClassicWindow.tsx", import.meta.url))
const CSS = fileURLToPath(new URL("../../style.css", import.meta.url))
const LAUNCHER = fileURLToPath(
  new URL(
    "../../../../provisioning/ansible/roles/cli_tools/templates/capture-ui.j2",
    import.meta.url,
  ),
)

function code(path: string): string {
  return readFileSync(path, "utf8")
    .split("\n")
    .filter((line) => !line.trimStart().startsWith("//"))
    .join("\n")
}

// ---------------------------------------------------------------------------
// 1. The lookup semantics, executed
// ---------------------------------------------------------------------------

/**
 * A stand-in for the two windows `app.tsx` builds on a two-monitor host, plus
 * AGS's resolution. The `order` is the whole point: it is NOT registration
 * order, and GTK re-orders it as windows are mapped and unmapped. Both states
 * below were read off a live run, not assumed.
 */
function fakeApp() {
  const windows: Array<{ id: string; name: string; visible: boolean }> = []
  return {
    windows,
    /** What AGS does: `windows.find((w) => w.name === name)` (app.ts:156-158). */
    get_window(name: string) {
      return windows.find((w) => w.name === name)
    },
    toggle_window(name: string) {
      const win = this.get_window(name)
      if (!win) throw Error(`no window registered with name "${name}"`)
      win.visible = !win.visible
    },
    /** GTK's own list, in the order it was measured to hold. */
    set_order(order: string[]) {
      windows.sort((x, y) => order.indexOf(x.id) - order.indexOf(y.id))
    },
  }
}

function who(w: { id: string } | undefined): string {
  return w ? w.id.toUpperCase() : "null"
}

/** The PRE-FIX `hideCaptureWindow()`, verbatim. */
function hideByName(app: ReturnType<typeof fakeApp>, _pressed: string) {
  const window = app.get_window("capture-window")
  if (window) window.visible = false
}

/** The POST-FIX `hideCaptureWindow()`: the window that owns the button. */
function hideSelf(self: { visible: boolean }) {
  self.visible = false
}

test("the name lookup hides the WRONG window (the defect, executed)", () => {
  // Measured live: on a fresh instance GTK holds the list as [b, a], so
  // `find` returns b — the window nobody pressed. After window A has mapped and
  // unmapped the order flips to [a, b] and the same code happens to be right.
  // That is why this defect is intermittent rather than constant, and why
  // asserting "it is always wrong" would be the wrong test.
  const app = fakeApp()
  const a = { id: "a", name: "capture-window", visible: true }
  const b = { id: "b", name: "capture-window", visible: true }
  app.windows.push(a, b)
  app.set_order(["b", "a"])

  assert.equal(who(app.get_window("capture-window")), "B", "lookup target changed")

  hideByName(app, "a")

  assert.equal(a.visible, true, "with order [b,a] the pressed window A stayed visible")
  assert.equal(b.visible, false, "with order [b,a] the un-pressed window B was hidden")
})

test("the pre-fix lookup is correct only by luck of the order", () => {
  // The other measured order. Nothing about the CODE changed; only GTK's list
  // did. A test that passed on this ordering would not have caught the bug.
  const app = fakeApp()
  const a = { id: "a", name: "capture-window", visible: true }
  const b = { id: "b", name: "capture-window", visible: true }
  app.windows.push(a, b)
  app.set_order(["a", "b"])

  hideByName(app, "a")

  assert.equal(a.visible, false)
  assert.equal(b.visible, true)
})

test("the self-scoped hide always hides the pressed window", () => {
  for (const order of [["b", "a"], ["a", "b"], ["b", "a", "b"]]) {
    const app = fakeApp()
    const a = { id: "a", name: "capture-window", visible: true }
    const b = { id: "b", name: "capture-window", visible: true }
    app.windows.push(a, b)
    app.set_order(order)

    hideSelf(a)

    assert.equal(a.visible, false, `pressed window stayed up with order [${order}]`)
    assert.equal(b.visible, true, `the other window was hidden with order [${order}]`)
  }
})

test("only ONE window is reachable by name, whatever the order", () => {
  // The property that makes the launcher half of this unsolvable without a
  // rename: `ags toggle capture-window` (capture-ui.j2) reaches one window. It
  // is not "the focused monitor's" and it is not stable across map history.
  for (const order of [["b", "a"], ["a", "b"]]) {
    const app = fakeApp()
    const a = { id: "a", name: "capture-window", visible: false }
    const b = { id: "b", name: "capture-window", visible: false }
    app.windows.push(a, b)
    app.set_order(order)

    app.toggle_window("capture-window")

    const shown = app.windows.filter((w) => w.visible)
    assert.equal(shown.length, 1, `toggle showed ${shown.length} windows`)
  }
})

// ---------------------------------------------------------------------------
// 2. The wiring, read from the real source
// ---------------------------------------------------------------------------

test("ClassicWindow resolves no window by name", () => {
  const source = code(WINDOW)
  assert.equal(
    /app\.get_window\(/.test(source),
    false,
    "ClassicWindow still resolves a window by name — with one window per monitor that is not necessarily THIS window",
  )
  assert.equal(
    /from "ags\/gtk4\/app"/.test(source),
    false,
    "the AGS app singleton is no longer needed in this file",
  )
  assert.match(
    source,
    /captureWindow\s*=\s*self/,
    "the window must capture its own instance from the `<window>` `$` handler",
  )
})

test("the self-reference is per-CALL, not per-module", () => {
  // The mistake I made first: `let captureWindow` at module scope. `app.tsx`
  // builds one window per monitor, so a shared variable is overwritten by the
  // second construction and the defect returns verbatim — measured, not
  // theorised (see design.md, "The bug I wrote first").
  const source = code(WINDOW)
  const factoryAt = source.indexOf("export function ClassicWindow(")
  const declAt = source.indexOf("let captureWindow")
  assert.ok(factoryAt > -1, "ClassicWindow factory not found")
  assert.ok(declAt > -1, "captureWindow declaration not found")
  assert.ok(
    declAt > factoryAt,
    "`captureWindow` is declared at MODULE scope — every window would share one reference and the last one built would win",
  )
  // ...and declared exactly once, so a stray second declaration cannot shadow it.
  assert.equal(
    (source.match(/let captureWindow/g) ?? []).length,
    1,
    "captureWindow must be declared exactly once",
  )
})

// ---------------------------------------------------------------------------
// 3. The name contract, read across files
// ---------------------------------------------------------------------------

function windowName(): string {
  const m = /name="([^"]+)"/.exec(code(WINDOW))
  assert.ok(m, "the window no longer declares a name")
  return m[1]
}

test("the window, the stylesheet and the provisioned launcher agree on the name", () => {
  const name = windowName()

  // style.css matches the window with an ID selector, which in GTK4 matches the
  // widget NAME — not the CSS class. Renaming the window without touching this
  // line silently drops `background-color: transparent; color: @color_foreground`
  // onto nothing, and the panel paints a first-frame rectangle.
  const css = readFileSync(CSS, "utf8")
  assert.match(
    css,
    new RegExp(`window#${name}\\b`),
    `style.css no longer selects the window by its name ("${name}")`,
  )

  // capture-ui.j2 is provisioned to ~/.local/bin/capture-ui, which is what the
  // SUPER+PRINT keybind runs (dotfiles/config/hypr/keybindings.lua:42-46). If the
  // window is renamed and this is not, `ags toggle` throws "no window
  // registered with name" — the keybind launches nothing, silently.
  const launcher = readFileSync(LAUNCHER, "utf8")
  const w = /^WINDOW="([^"]+)"/m.exec(launcher)
  assert.ok(w, "capture-ui.j2 no longer declares WINDOW=")
  assert.equal(
    w[1],
    name,
    `capture-ui.j2 toggles "${w[1]}" but the window is named "${name}" — the keybind would launch nothing`,
  )
  assert.match(
    launcher,
    /ags toggle "\$WINDOW" -i "\$INSTANCE"/,
    "capture-ui.j2 no longer toggles $WINDOW on $INSTANCE",
  )
})

test("the name is still shared by every monitor's window, by design", () => {
  // Pinned deliberately. If this ever fails, the three consumers above are the
  // checklist, and `capture-ui.j2` needs a PROVISION RUN to change — see
  // design.md §Blast radius.
  const source = code(WINDOW)
  assert.equal(
    (source.match(/name="capture-window"/g) ?? []).length,
    1,
    "the window name is no longer the single literal `capture-window`",
  )
  assert.match(
    source,
    /const WINDOW_NAME = "capture-window"/,
    "WINDOW_NAME is no longer bound to the literal",
  )
})