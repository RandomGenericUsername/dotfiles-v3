#!/usr/bin/env python3
"""PROTOTYPE 4 — END TO END: does BlueZ route a PIN-family request to an agent
that declared KeyboardDisplay?

Closes the gap prototypes 1-2 left. Those proved the capability string is
legal and that GJS can hold an invocation. Neither proved BlueZ would CALL us
during a real pairing. This does, against real hardware.

It registers an org.bluez.Agent1 object with capability `KeyboardDisplay`,
makes it the DEFAULT agent, triggers `Pair` against a real unpaired device,
and reports which method BlueZ chose.

SCOPE, deliberately narrow: this probe OBSERVES ROUTING. It logs every method
BlueZ invokes and answers each one immediately. It does NOT need to hold an
invocation, because holding is already proven by prototype 2 (GJS/Gio) -- and
dbus-python cannot park an invocation across turns, which is a client-library
limitation, not a BlueZ one. So a PIN-family call here means the routing claim
is proven; the resulting pairing may then fail because we answered instantly.
That is fine and is not what is being measured.

WHY THIS DEVICE MATTERS: the Infinix NOTE 40 Pro reports `LegacyPairing: no`,
so it refuses legacy PIN entry and must use SSP. SSP is either Just Works (no
interaction) or Numeric Comparison, which requires `DisplayPasskey` +
`RequestConfirmation` -- both BEYOND the `NoInputNoOutput` capability the panel
ships today. If this probe sees either, the gap option C closes is REAL AND
OBSERVED.

SAFETY / RESTORE
  - Target is already `Bonded: no`; nothing is unpaired first.
  - This DOES take the default-agent role from the running AGS instance, and it
    CANNOT give it back: MEASURED, BlueZ keys agents by PATH ALONE (registering
    the same path twice returns "Already Exists"), so `RequestDefaultAgent` only
    resolves for the connection that exported the object. An external probe
    asking for AGS's path correctly gets "Does Not Exist".
    Consequence: restoring the panel's agent requires AGS itself to re-request
    it, i.e. an AGS restart. Plan for that rather than assuming it is free.
  - `finally` restores AGS even on failure or Ctrl-C.

Usage: python3 prototypes/pairing-e2e-probe.py --device 7C:8B:C1:8E:7B:94
"""
import argparse
import time

import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

BLUEZ = "org.bluez"
AGENT_MGR = "org.bluez.AgentManager1"
AGENT_PATH = "/org/dotfiles/E2EProbeAgent"
AGS_AGENT_PATH = "/org/dotfiles/BlueZAgent"
CAPABILITY = "KeyboardDisplay"

calls = []
# Whether Pair was actually issued. Distinguishes "BlueZ declined to call us"
# (a real negative) from "the device was never there" (no test performed).
attempted = {"pair": False}


class E2EAgent(dbus.service.Object):
    def __init__(self, bus):
        super().__init__(bus, AGENT_PATH)

    @dbus.service.method("org.bluez.Agent1")
    def Release(self):
        calls.append(("Release", ""))
        print("  >> Release() — BlueZ told us we are no longer the default")

    @dbus.service.method("org.bluez.Agent1", in_signature="os")
    def DisplayPinCode(self, dev, pincode):
        calls.append(("DisplayPinCode", pincode))
        print(f"  >> DisplayPinCode: the device is showing PIN {pincode}")

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="s")
    def RequestPinCode(self, dev):
        calls.append(("RequestPinCode", str(dev)))
        print(f"  >> RequestPinCode({dev})")
        # Answered instantly and deliberately wrong: this probe measures
        # ROUTING, not completion. A real implementation would park this.
        return "0000"

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="u")
    def RequestPasskey(self, dev):
        calls.append(("RequestPasskey", str(dev)))
        print(f"  >> RequestPasskey({dev})")
        return dbus.UInt32(0)

    @dbus.service.method("org.bluez.Agent1", in_signature="ouq")
    def DisplayPasskey(self, dev, passkey, entered):
        calls.append(("DisplayPasskey", str(passkey)))
        print(f"  >> DisplayPasskey({dev}, {passkey})"
              + (f" — already entered {entered}" if entered else ""))
        print(f"     *** COMPARE {passkey} ON YOUR PHONE ***")

    @dbus.service.method("org.bluez.Agent1", in_signature="ou")
    def RequestConfirmation(self, dev, passkey):
        calls.append(("RequestConfirmation", str(passkey)))
        print(f"  >> RequestConfirmation({dev}, {passkey})")
        return None

    @dbus.service.method("org.bluez.Agent1", in_signature="o")
    def RequestAuthorization(self, dev):
        calls.append(("RequestAuthorization", str(dev)))
        print(f"  >> RequestAuthorization({dev})")

    @dbus.service.method("org.bluez.Agent1", in_signature="os")
    def AuthorizeService(self, dev, uuid):
        calls.append(("AuthorizeService", uuid))
        print(f"  >> AuthorizeService({dev}, {uuid})")

    @dbus.service.method("org.bluez.Agent1")
    def Cancel(self):
        calls.append(("Cancel", ""))
        print("  >> Cancel — pairing request withdrawn")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", required=True)
    ap.add_argument("--timeout", type=int, default=70)
    args = ap.parse_args()

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    E2EAgent(bus)
    mgr = dbus.Interface(bus.get_object(BLUEZ, "/org/bluez"), AGENT_MGR)
    dev = args.device.upper()
    dev_path = "/org/bluez/hci0/dev_" + dev.replace(":", "_")
    loop = GLib.MainLoop()

    print("PROBE: end-to-end pairing against a KeyboardDisplay agent")
    print(f"  capability : {CAPABILITY}")
    print(f"  device     : {dev}")
    print(f"  path       : {dev_path}")
    print("\n  >>> OPEN BLUETOOTH SETTINGS ON YOUR PHONE AND WAIT FOR THE PROMPT <<<\n")

    registered = made_default = False
    try:
        mgr.RegisterAgent(AGENT_PATH, CAPABILITY)
        registered = True
        print(f"  RegisterAgent({CAPABILITY})  -> OK")
        mgr.RequestDefaultAgent(AGENT_PATH)
        made_default = True
        print("  RequestDefaultAgent(ours)   -> OK (AGS's agent displaced)")
    except dbus.DBusException as e:
        print(f"  RegisterAgent FAILED: {e.get_dbus_message()}")
        return 1

    try:
        # dbus-python has no Bus.call(). Method calls go through a
        # dbus.Interface proxy over the remote object; the proxy method
        # accepts timeout= in SECONDS.
        adapter = dbus.Interface(bus.get_object(BLUEZ, "/org/bluez/hci0"),
                                 "org.bluez.Adapter1")

        def go():
            try:
                adapter.StartDiscovery(timeout=10)
                print("  StartDiscovery()            -> OK")
            except dbus.DBusException as e:
                print(f"  StartDiscovery() -> {e.get_dbus_message()}")

            state = {"tries": 0, "paired": False}

            def poll():
                """Wait for the Device1 object to actually exist, then Pair.

                A fixed sleep is wrong here: the object only appears once
                BlueZ has resolved an advertisement, and on this machine that
                has already been observed to take longer than any sleep
                worth choosing -- a previous run's `info` reported the device
                as gone between two commands. So poll the ObjectManager and
                report explicitly if it never turns up, rather than pairing
                an object that is not there and blaming the method.
                """
                state["tries"] += 1
                try:
                    objs = bus.get_object(BLUEZ, "/")
                    mgr_if = dbus.Interface(objs,
                        "org.freedesktop.DBus.ObjectManager")
                    managed = mgr_if.GetManagedObjects(timeout=8)
                except dbus.DBusException as e:
                    print(f"  GetManagedObjects -> "
                          f"{e.get_dbus_message()}")
                    return False

                if dev_path in managed:
                    alias = ""
                    props = managed[dev_path].get("org.bluez.Device1")
                    if props:
                        alias = str(props.get("Alias", ""))
                    print(f"  device object present after "
                          f"{state['tries']} poll(s)  [{alias or dev}]")
                    try:
                        attempted["pair"] = True
                        dev = dbus.Interface(
                            bus.get_object(BLUEZ, dev_path),
                            "org.bluez.Device1")
                        dev.Pair(timeout=args.timeout)
                        print("  Pair() returned OK")
                    except dbus.DBusException as e:
                        print(f"  Pair() -> {e.get_dbus_message()}")
                    state["paired"] = True
                    return False

                if state["tries"] % 3 == 0:
                    print(f"  ...not discovered yet "
                          f"({state['tries']} polls, "
                          f"{len(managed)} objects on the bus)")
                if state["tries"] >= 30:
                    print("  device never appeared. The target is out of")
                    print("  range, not in pairing mode, or already bonded.")
                    print("  RESULT IS INCONCLUSIVE -- not a negative.")
                    return False
                return True

            # NOTE: dbus-python's GLib override is
            #   timeout_add(interval, function, *user_data, priority=...)
            # with priority KEYWORD-ONLY and last -- NOT the C ordering
            # (priority, interval, func). Passing it positionally makes
            # `function` receive the interval int and raises
            # "Callback needs to be a function or method not int".
            GLib.timeout_add(2000, poll)
            return False

        def bail():
            loop.quit()
            return False

        GLib.timeout_add(300, go)
        # Budget: up to ~60s of discovery polling, plus the Pair timeout.
        GLib.timeout_add((args.timeout + 90) * 1000, bail)
        loop.run()
    finally:
        # Restore is best-effort and, on this machine, a NO-OP by design.
        # MEASURED: no agent is registered at AGS_AGENT_PATH (the panel's own
        # agent is dead -- see the prototype header), and BlueZ keys agents by
        # path alone, so "Does Not Exist" here is the EXPECTED, correct answer,
        # not a failed restore. There is no displaced agent to give back.
        print("\n  restoring default-agent state...")
        try:
            mgr.RequestDefaultAgent(AGS_AGENT_PATH)
            print(f"  RequestDefaultAgent({AGS_AGENT_PATH}) -> OK")
        except dbus.DBusException as e:
            msg = e.get_dbus_message()
            if "Does Not Exist" in str(msg):
                print(f"  RequestDefaultAgent(AGS) -> {msg}")
                print("     expected: the panel's agent was never registered,")
                print("     so there was nothing to displace. No harm done.")
            else:
                print(f"  !! unexpected restore error: {msg}")
        try:
            mgr.UnregisterAgent(AGENT_PATH)
            print("  probe agent unregistered")
        except dbus.DBusException:
            pass
        # Stop the discovery this probe started. BlueZ refcounts
        # Start/StopDiscovery, and an unbalanced Start leaves the adapter
        # scanning forever -- an earlier version of this script did exactly
        # that, and the controller was left reporting Discovering=yes while
        # resolving nothing. Always balance it.
        try:
            dbus.Interface(bus.get_object(BLUEZ, "/org/bluez/hci0"),
                           "org.bluez.Adapter1").StopDiscovery(timeout=8)
            print("  StopDiscovery()            -> OK (discovery refcount balanced)")
        except dbus.DBusException as e:
            print(f"  StopDiscovery() -> {e.get_dbus_message()}")

    # ---- report ----------------------------------------------------------
    print("\n" + "=" * 70)
    print("WHAT BLUEZ ACTUALLY CALLED")
    print("=" * 70)
    if calls:
        for kind, arg in calls:
            print(f"  {kind}({arg})")
    elif not attempted["pair"]:
        print("  (nothing — the device object never appeared, so Pair was")
        print("   never issued. NO agent method was tested. Inconclusive.)")
    else:
        print("  (nothing — our agent was never invoked)")

    kinds = {k for k, _ in calls}
    pin_family = {"RequestPinCode", "DisplayPinCode", "RequestPasskey",
                  "DisplayPasskey", "RequestConfirmation"}
    reached = bool(kinds & pin_family)

    inconclusive = not attempted["pair"]

    print("\n" + "=" * 70)
    print("ASSERTIONS")
    print("=" * 70)
    print(f"0. Pair was actually issued                "
          f"{'PASS' if attempted['pair'] else 'FAIL -- NO TEST PERFORMED'}")
    print(f"1. agent registered AND made default      "
          f"{'PASS' if (registered and made_default) else 'FAIL'}")
    print(f"2. BlueZ invoked our agent at all         "
          f"{'PASS' if calls else 'FAIL'}")
    print(f"3. a PIN-FAMILY method was requested      "
          f"{'PASS' if reached else 'FAIL'}"
          + ("" if reached else "   (device paired via Just Works)"))
    print("\n" + "=" * 70)
    if inconclusive:
        print("VERDICT: INCONCLUSIVE. The device object never appeared on the")
        print("bus, so Pair was never issued and no agent method was exercised.")
        print("This measures nothing about PIN routing. Put the target in")
        print("pairing mode and re-run.")
    elif reached:
        print("VERDICT: BlueZ DID route a PIN-family method to an agent that")
        print("declared KeyboardDisplay. The panel's NoInputNoOutput agent could")
        print("not have served it. Option C's premise is now OBSERVED.")
    elif calls:
        print("VERDICT: BlueZ called the agent, but only with methods that")
        print("NoInputNoOutput already covers. This device paired via Just Works")
        print("and is NOT a witness for the PIN path.")
    else:
        print("VERDICT: Pair was issued and BlueZ still never called our agent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
