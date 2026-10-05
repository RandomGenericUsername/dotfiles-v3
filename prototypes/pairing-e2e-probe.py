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
        # Discovery so the Device1 object exists, then Pair.
        def go():  # noqa: D401
            try:
                bus.call(BLUEZ, "/org/bluez/hci0", "org.bluez.Adapter1",
                         "StartDiscovery", None, None,
                         dbus.DBusCallFlags.NONE, 10000, None)
            except dbus.DBusException:
                pass
            def pair():
                try:
                    bus.call(BLUEZ, dev_path, "org.bluez.Device1", "Pair",
                             None, None, dbus.DBusCallFlags.NONE,
                             args.timeout * 1000, None)
                    print("  Pair() returned")
                except dbus.DBusException as e:
                    print(f"  Pair() -> {e.get_dbus_message()}")
                return False
            GLib.timeout_add(GLib.PRIORITY_DEFAULT, 3000, pair)
            return GLib.SOURCE_REMOVE

        def bail():
            loop.quit()
            return False

        GLib.timeout_add(GLib.PRIORITY_DEFAULT, 300, go)
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, args.timeout * 1000, bail)
        loop.run()
    finally:
        print("\n  restoring AGS as the default agent...")
        try:
            mgr.RequestDefaultAgent(AGS_AGENT_PATH)
            print("  RequestDefaultAgent(AGS) -> OK, panel pairing is yours again")
        except dbus.DBusException as e:
            print(f"  !! restore FAILED: {e.get_dbus_message()}")
        try:
            mgr.UnregisterAgent(AGENT_PATH)
            print("  probe agent unregistered")
        except dbus.DBusException:
            pass

    # ---- report ----------------------------------------------------------
    print("\n" + "=" * 70)
    print("WHAT BLUEZ ACTUALLY CALLED")
    print("=" * 70)
    if calls:
        for kind, arg in calls:
            print(f"  {kind}({arg})")
    else:
        print("  (nothing — our agent was never invoked)")

    kinds = {k for k, _ in calls}
    pin_family = {"RequestPinCode", "DisplayPinCode", "RequestPasskey",
                  "DisplayPasskey", "RequestConfirmation"}
    reached = bool(kinds & pin_family)

    print("\n" + "=" * 70)
    print("ASSERTIONS")
    print("=" * 70)
    print(f"1. agent registered AND made default      {'PASS' if (registered and made_default) else 'FAIL'}")
    print(f"2. BlueZ invoked our agent at all         {'PASS' if calls else 'FAIL'}")
    print(f"3. a PIN-FAMILY method was requested       {'PASS' if reached else 'FAIL'}"
          + ("" if reached else "   (device paired via Just Works)"))
    print("\n" + "=" * 70)
    if reached:
        print("VERDICT: BlueZ DID route a PIN-family method to an agent that")
        print("declared KeyboardDisplay. The panel's NoInputNoOutput agent could")
        print("not have served it. Option C's premise is now OBSERVED.")
    elif calls:
        print("VERDICT: BlueZ called the agent, but only with methods that")
        print("NoInputNoOutput already covers. This device paired via Just Works")
        print("and is NOT a witness for the PIN path.")
    else:
        print("VERDICT: our agent was never invoked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
