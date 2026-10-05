#!/usr/bin/env gjs
/*
 * Does `halign={CENTER}` actually centre a row, and does the parent's
 * ORIENTATION decide whether it works?
 *
 * The claim under test: `halign` positions a child on its parent's CROSS axis.
 * AGS's `<box>` defaults to horizontal, so a horizontal parent packs its
 * children left-to-right along the MAIN axis and `halign` is ignored -- the row
 * gets its natural width at the start. A VERTICAL parent makes the row's
 * horizontal placement a cross-axis decision, which `halign` honours.
 *
 * This measures real allocations rather than reasoning about them, because
 * reasoning about it is what produced two wrong deploys.
 */
const { Gtk, GLib } = imports.gi;
Gtk.init();

const OUTER_W = 300;   // stands in for the 312px popup
const ROW_W = 90;      // spinner + "Scanning..."

function build(outerVertical, outerHexpand) {
    const inner = new Gtk.Box({ spacing: 7 });
    // GtkSpinner has no pixel_size (that is a Gtk.Image property); its size
    // comes from CSS, exactly as .settings-spinner does in the real code.
    const sp = new Gtk.Spinner();
    sp.set_size_request(14, 14);
    inner.append(sp);
    inner.append(new Gtk.Label({ label: "Scanning…" }));
    inner.halign = 3; // Gtk.Align.CENTER -- NOT 1, which is START

    const outer = new Gtk.Box({
        orientation: outerVertical ? Gtk.Orientation.VERTICAL : Gtk.Orientation.HORIZONTAL,
    });
    if (outerHexpand) outer.hexpand = true;
    outer.append(inner);
    return { outer, inner };
}

function measure(label, cfg) {
    const win = new Gtk.Window();
    const root = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL });
    const { outer, inner } = build(cfg.vertical, cfg.hexpand);
    root.append(outer);
    win.set_child(root);
    win.set_default_size(OUTER_W, 200);
    win.present();

    // Let the layout settle.
    const ctx = GLib.MainContext.default();
    for (let i = 0; i < 200; i++) ctx.iteration(false);

    const oa = outer.get_allocation();
    const ia = inner.get_allocation();
    const slack = oa.width - ia.width;
    const fromLeft = ia.x - oa.x;
    const fromRight = (oa.x + oa.width) - (ia.x + ia.width);

    console.log(
        `  ${label.padEnd(34)} outer.w=${String(oa.width).padStart(4)}  row.w=${String(ia.width).padStart(4)}` +
        `  slack=${String(slack).padStart(4)}  L=${String(fromLeft).padStart(4)} R=${String(fromRight).padStart(4)}` +
        `  ${Math.abs(fromLeft - fromRight) <= 1 ? "CENTRED" : "not centred"}`
    );
    win.destroy();
}

console.log(`GTK ${Gtk.get_major_version()}.${Gtk.get_minor_version()} — outer ${OUTER_W}px, row ~${ROW_W}px`);
measure("horizontal parent, no hexpand", { vertical: false, hexpand: false });
measure("horizontal parent, hexpand", { vertical: false, hexpand: true });
measure("VERTICAL parent, no hexpand", { vertical: true, hexpand: false });
measure("VERTICAL parent, hexpand", { vertical: true, hexpand: true });