#!/usr/bin/env gjs
// GJS-side parser for a D-Bus introspection XML contract.
//
// Uses the real GObject-Introspection D-Bus parser that AGS/GJS actually links
// against: Gio.DBusNodeInfo.new_for_xml. It emits the SAME canonical normalized
// model as spikes/dbus-xml/python_parse.py so the conformance harness can
// byte-compare the two independent parse results.
//
// Usage: gjs gjs_parse.js <path-to-xml>

const { GLib, Gio } = imports.gi;
const System = imports.system;

function readFile(path) {
  const [ok, bytes] = GLib.file_get_contents(path);
  if (!ok) throw new Error(`cannot read ${path}`);
  return new TextDecoder("utf-8").decode(bytes);
}

function parseArgs(args) {
  // Gio gives an array of Gio.DBusArgInfo; preserve positional order.
  return args.map((a) => ({ name: a.name || "", type: a.signature || "" }));
}

function parseXml(xml) {
  const node = Gio.DBusNodeInfo.new_for_xml(xml);
  if (!node) throw new Error("Gio.DBusNodeInfo.new_for_xml returned null");

  const ifaces = node.interfaces || [];
  if (ifaces.length !== 1) {
    throw new Error(`expected exactly 1 interface, found ${ifaces.length}`);
  }
  const iface = ifaces[0];

  const methods = [];
  for (const m of iface.methods || []) {
    methods.push({
      name: m.name,
      in: parseArgs(m.in_args || []),
      out: parseArgs(m.out_args || []),
    });
  }

  const signals = [];
  for (const s of iface.signals || []) {
    signals.push({ name: s.name, args: parseArgs(s.args || []) });
  }

  methods.sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
  signals.sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));

  return { interface: iface.name, methods, signals };
}

function main() {
  const argv = ARGV;
  if (argv.length < 1) {
    printerr("usage: gjs gjs_parse.js <path-to-xml>");
    System.exit(2);
  }
  const xml = readFile(argv[0]);
  const model = parseXml(xml);
  print(JSON.stringify(model, null, 2));
}

main();
