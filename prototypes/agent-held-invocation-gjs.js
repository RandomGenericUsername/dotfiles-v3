#!/usr/bin/env gjs
/*
 * PROTOTYPE 3 — can the GJS/Gio agent HOLD a D-Bus method invocation?
 *
 * This is the decisive prototype for option C, because it tests the mechanism
 * the real implementation would use. `bluetooth-agent.ts` is GJS and calls
 * `Gio.DBusNodeInfo.new_for_xml(...)` + `bus.register_object(...)`, whose
 * callback receives a `Gio.DBusMethodInvocation`. Option C requires keeping
 * that invocation and calling `return_value()` later, when the user submits a
 * PIN — instead of returning synchronously as the current code does.
 *
 * If Gio cannot hold an invocation across a user interaction, option C is not
 * buildable as designed. Asserting it here, by execution, in the same language
 * and the same API the implementation uses.
 *
 * BUS: the SESSION bus. `/usr/share/dbus-1/system.conf` sets
 * `<deny send_type="method_call"/>` in its default policy, so a user
 * connection cannot invoke method calls on the system bus (org.bluez is
 * exempted by a later rule, which is why RegisterAgent works). BlueZ reaches
 * our agent because it runs as root; a user-space probe cannot. Holding an
 * invocation is a property of the protocol and of Gio, not of the bus.
 *
 * NOT COVERED: BlueZ actually invoking us with capability KeyboardDisplay.
 * That needs a PIN-requiring device and remains untested.
 *
 * Usage: gjs prototypes/agent-held-invocation-gjs.js
 * Exit 0 = all assertions passed.
 */

const Gio = imports.gi.Gio;
const GLib = imports.gi.GLib;

const PATH = "/org/dotfiles/GjsHeldAgentProbe";

const XML = `
<node><interface name="org.bluez.Agent1">
  <method name="Release"/>
  <method name="RequestPinCode">
    <arg type="o" direction="in"/>
    <arg type="s" direction="out"/>
  </method>
  <method name="RequestPasskey">
    <arg type="o" direction="in"/>
    <arg type="u" direction="out"/>
  </method>
  <method name="Cancel"/>
</interface></node>`;

// The parked invocation — exactly what option C's agent would hold.
let parked = null;
let arrivalMs = 0;
let repliedMs = 0;
const startedMs = GLib.get_monotonic_time() / 1000;

function log(msg) {
    print(msg);
}

function main() {
    const bus = Gio.bus_get_sync(Gio.BusType.SESSION, null);

    const node = Gio.DBusNodeInfo.new_for_xml(XML);
    const iface = node.interfaces[0];

    bus.register_object(
        PATH,
        iface,
        (_conn, _sender, _path, _iface, method, _params, invocation) => {
            if (method === "RequestPinCode") {
                // THE TEST: deliberately do NOT call return_value() here.
                // Park the invocation for the "user" to answer later.
                parked = invocation;
                arrivalMs = GLib.get_monotonic_time() / 1000;
                log(`  agent: RequestPinCode received, invocation PARKED`);
                // Deliberately no return — the call stays outstanding.
                return;
            }
            invocation.return_value(null);
        },
        null,
        null,
    );

    log("PROBE: Gio.DBusMethodInvocation held across a user interaction\n");

    // Fire the call the way BlueZ does: async, so our loop keeps running.
    bus.call(
        // Our own unique name: the agent object lives on THIS connection.
        // Addressing it to the bus daemon sends the message to the daemon
        // instead, which errors with ServiceUnknown and proves nothing.
        bus.get_unique_name(),
        PATH,
        "org.bluez.Agent1",
        "RequestPinCode",
        new GLib.Variant("(o)", ["/org/bluez/hci0/dev_TEST"]),
        new GLib.VariantType("(s)"),
        Gio.DBusCallFlags.NONE,
        -1,
        null,
        (_c, res) => {
            try {
                const reply = bus.call_finish(res);
                repliedMs = GLib.get_monotonic_time() / 1000;
                print(`  caller: returned ${reply.deepUnpack()[0]}`);
                globalThis.__reply = reply.deepUnpack()[0];
            } catch (e) {
                print(`  caller: ERROR ${e.message}`);
                globalThis.__reply = null;
            }
            globalThis.__done = true;
            loop.quit();
        },
    );

    loop.run();
}

const loop = new GLib.MainLoop(null, false);

// --- the "user" typing a PIN, ~1s later, from a separate event ------------
GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1000, () => {
    if (parked === null) {
        print("  user: nothing parked — the agent returned early (FAIL)");
        globalThis.__reply = null;
        globalThis.__done = true;
        loop.quit();
        return GLib.SOURCE_REMOVE;
    }
    log(`  user: submitting PIN after ${(GLib.get_monotonic_time() / 1000 - arrivalMs).toFixed(3)}s parked`);
    globalThis.__submittedMs = GLib.get_monotonic_time() / 1000;
    // This is the line option C's submit handler would run.
    parked.return_value(new GLib.Variant("(s)", ["1234"]));
    parked = null;
    return GLib.SOURCE_REMOVE;
});

main();

// --- assertions -----------------------------------------------------------
print("");
print("=".repeat(68));
print("ASSERTIONS");
print("=".repeat(68));

const arrived = arrivalMs > 0;
print(`1. Gio delivered RequestPinCode to the callback      ${arrived ? "PASS" : "FAIL"}`);

// ASSERT 2 is the load-bearing one: the caller's reply must arrive AFTER the
// user submitted, not before. An agent that replied synchronously would make
// repliedMs < submittedMs. Comparing wall-clock order is what actually proves
// the invocation was withheld, rather than asserting on a latency threshold.
const withheld = repliedMs > 0 && globalThis.__submittedMs > 0 &&
    repliedMs >= globalThis.__submittedMs;
print(`2. reply withheld until the user submitted            ${withheld ? "PASS" : "FAIL"}` +
      (withheld
          ? `  (reply +${((repliedMs - globalThis.__submittedMs) * 1000).toFixed(1)}ms after submit)`
          : `  (replied=${repliedMs.toFixed(3)} submitted=${(globalThis.__submittedMs ?? 0).toFixed(3)})`));

const reply = globalThis.__reply;
const delivered = reply === "1234";
print(`3. return_value() later delivered the typed PIN      ${delivered ? "PASS" : "FAIL"}` +
      `  (got ${JSON.stringify(reply)})`);

const overall = arrived && withheld && delivered;
print("");
print(`OVERALL: ${overall ? "PASS" : "FAIL"}`);
print("");
print("CONCLUSION");
print("-----------");
if (overall) {
    print("Gio CAN hold a Gio.DBusMethodInvocation and resolve it from a later");
    print("event. This is exactly what bluetooth-agent.ts would do under a");
    print("KeyboardDisplay capability: park the invocation in RequestPinCode,");
    print("render a prompt, and call return_value() when the user submits.");
    print("The current synchronous return_value(['0000']) is only sound");
    print("because NoInputNoOutput means BlueZ never asks.");
} else {
    print("Gio could NOT hold the invocation. Option C's design would have to");
    print("change: the agent would need a different approach, or the capability");
    print("change would be unsafe.");
}
imports.system.exit(overall ? 0 : 1);
