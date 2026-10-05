#!/usr/bin/env gjs
/*
 * Does the routeInFlight guard actually drop re-entry, and does the transition
 * tracker in BluetoothContent avoid re-routing on an unrelated list change?
 *
 * Both are logic claims with no runtime observable in the panel, so they are
 * extracted and exercised here against the same code shape:
 *
 *   1. re-entrant call for a label already in flight  -> dropped
 *   2. a DIFFERENT label while one is in flight        -> proceeds (switching
 *      the default sink to another device must not queue behind the first)
 *   3. re-entry AFTER completion                        -> allowed again
 *   4. transition tracker: RSSI-only churn             -> routes once
 *   5. transition tracker: disconnect then reconnect    -> routes twice
 */
const sleep = (ms) => new Promise((r) => GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => { r(); return false; }));
const { GLib } = imports.gi;

const routeInFlight = new Set();
let pollsRun = 0;

async function route(label, attempts = 3, gap = 60) {
    if (label && routeInFlight.has(label)) return "dropped";
    if (label) routeInFlight.add(label);
    try {
        pollsRun++;
        for (let i = 0; i < attempts; i++) await sleep(gap);   // stands in for the 16x500ms poll
        return "routed";
    } finally {
        if (label) routeInFlight.delete(label);
    }
}

function makeTracker() {
    const routed = new Set();
    return (devices) => {
        const connected = devices.filter((d) => d.connected);
        const still = new Set(connected.map((d) => d.address));
        const fired = [];
        for (const d of connected) {
            if (routed.has(d.address)) continue;
            routed.add(d.address);
            fired.push(d.alias);
        }
        for (const a of [...routed]) if (!still.has(a)) routed.delete(a);
        return fired;
    };
}

const results = [];
const check = (name, got, want) => {
    const ok = got === want;
    results.push(ok);
    print(`  ${ok ? "PASS" : "FAIL"}  ${name.padEnd(46)} got=${got} want=${want}`);
};

print("routeInFlight re-entrancy:");
// Order matters: the FIRST call must still be in flight while re-entry is
// tested. Awaiting it first completes it and clears the in-flight marker, which
// made the guard look broken when it is not.
const inflight = route("TOZO");
check("re-entry same label is dropped", await route("TOZO"), "dropped");
check("different label still proceeds", await route("Sony"), "routed");
check("first call completes", await inflight, "routed");
check("re-entry after completion proceeds", await route("TOZO"), "routed");

print("\ntransition tracker:");
const track = makeTracker();
check("initial connect routes once", track([{ address: "A", connected: true, alias: "TOZO" }]).length, 1);
check("RSSI-only churn does not re-route",
    track([{ address: "A", connected: true, alias: "TOZO", rssi: -55 }]).length, 0);
check("RSSI churn again does not re-route",
    track([{ address: "A", connected: true, alias: "TOZO", rssi: -80 }]).length, 0);
check("disconnect routes nothing", track([{ address: "A", connected: false, alias: "TOZO" }]).length, 0);
check("reconnect routes again", track([{ address: "A", connected: true, alias: "TOZO" }]).length, 1);
check("a second device connects", track([
    { address: "A", connected: true, alias: "TOZO" },
    { address: "B", connected: true, alias: "Sony" },
]).length, 1);

const ok = results.every((r) => r);
print("\n" + (ok ? "ALL PASS" : "FAILURES PRESENT"));
imports.system.exit(ok ? 0 : 1);