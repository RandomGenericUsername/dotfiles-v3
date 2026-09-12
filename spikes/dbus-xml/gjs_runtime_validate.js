#!/usr/bin/env gjs
// Runtime-validation demonstration on the GJS/AGS side.
//
// Parse the contract XML into a Gio.DBusInterfaceInfo (the SAME object AGS uses
// with Gio.DBusConnection.register_object / signal_subscribe), then validate a
// candidate outgoing signal emission and an incoming method call against it at
// runtime. No code generation: the XML drives the check.
//
// Usage: gjs gjs_runtime_validate.js <path-to-xml>

const { GLib, Gio } = imports.gi;
const System = imports.system;

function readFile(path) {
  const [ok, bytes] = GLib.file_get_contents(path);
  if (!ok) throw new Error(`cannot read ${path}`);
  return new TextDecoder("utf-8").decode(bytes);
}

function signalSignature(iface, name) {
  const s = iface.lookup_signal(name);
  if (!s) return null;
  return "(" + s.args.map((a) => a.signature).join("") + ")";
}

function methodSignatures(iface, name) {
  const m = iface.lookup_method(name);
  if (!m) return null;
  return {
    in: "(" + m.in_args.map((a) => a.signature).join("") + ")",
    out: "(" + m.out_args.map((a) => a.signature).join("") + ")",
  };
}

function checkSignal(iface, signalName, variant) {
  const expected = signalSignature(iface, signalName);
  if (expected === null) {
    return { ok: false, reason: `signal '${signalName}' not declared in XML` };
  }
  const actual = variant.get_type_string();
  if (actual !== expected) {
    return { ok: false, reason: `declared ${expected}, emitted ${actual}` };
  }
  return { ok: true, reason: `declared ${expected} == emitted ${actual}` };
}

function main() {
  const argv = ARGV;
  if (argv.length < 1) {
    printerr("usage: gjs gjs_runtime_validate.js <path-to-xml>");
    System.exit(2);
  }
  const iface = Gio.DBusNodeInfo.new_for_xml(readFile(argv[0])).interfaces[0];

  const cases = [
    ["JobStarted/ssu (declared)", "JobStarted", new GLib.Variant("(ssu)", ["j1", "capture", 7])],
    ["JobStarted/sss (wrong types)", "JobStarted", new GLib.Variant("(sss)", ["j1", "capture", "x"])],
    ["JobCrashed/ssu (undeclared)", "JobCrashed", new GLib.Variant("(ssu)", ["j1", "capture", 7])],
    ["JobsCleared/u (declared)", "JobsCleared", new GLib.Variant("(u)", [9])],
  ];
  let bad = 0;
  for (const [label, name, variant] of cases) {
    const r = checkSignal(iface, name, variant);
    print(`signal ${r.ok ? "ACCEPT" : "REJECT"}  ${label.padEnd(30)}  ${r.reason}`);
    if (!r.ok) bad++;
  }

  const m = methodSignatures(iface, "Control");
  print(`method lookup Control -> in=${m.in} out=${m.out}`);
  const missing = methodSignatures(iface, "LaunchJob");
  print(`method lookup LaunchJob -> ${missing === null ? "REJECT (undeclared)" : "found"}`);

  print(`RESULT: ${bad === 2 ? "PASS" : "FAIL"} (expected exactly 2 rejections, got ${bad})`);
  System.exit(bad === 2 ? 0 : 1);
}

main();
