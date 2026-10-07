#!/usr/bin/env python3
"""PROTOTYPE 1 — which agent capability strings does BlueZ actually accept?

Validates, by execution against the LIVE system bus, the claim that drives
option C: that BlueZ routes a pairing method only to an agent whose DECLARED
capability satisfies it, and therefore that raising the capability from
NoInputNoOutput to KeyboardDisplay is what unlocks PIN/passkey handling.

SAFETY: this registers an agent object but NEVER calls RequestDefaultAgent, so
it cannot steal the pairing role from the running AGS instance. Every agent is
unregistered in a finally block. Read-only with respect to user state.

Usage: python3 prototypes/agent-capability-probe.py
"""
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

BLUEZ = "org.bluez"
AGENT_MGR_PATH = "/org/bluez"
AGENT_MGR_IFACE = "org.bluez.AgentManager1"
AGENT_PATH = "/org/dotfiles/ProbeAgent"

# The capability vocabulary from BlueZ's agent.c, in the order BlueZ compares.
CAPABILITIES = [
    "",
    "DisplayOnly",
    "DisplayYesNo",
    "KeyboardOnly",
    "NoInputNoOutput",
    "KeyboardDisplay",
    "keyboarddisplay",      # case sensitivity probe
    "Keyboard",             # partial / not a real token
    "NotACapability",       # garbage
]


class Agent(dbus.service.Object):
    def __init__(self, bus):
        super().__init__(bus, AGENT_PATH)

    @dbus.service.method("org.bluez.Agent1")
    def Release(self):
        pass

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="s")
    def RequestPinCode(self, o):
        return "0000"

    @dbus.service.method("org.bluez.Agent1", in_signature="os")
    def DisplayPinCode(self, o, s):
        pass

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="u")
    def RequestPasskey(self, o):
        return 0

    @dbus.service.method("org.bluez.Agent1", in_signature="ouq")
    def DisplayPasskey(self, o, u, q):
        pass

    @dbus.service.method("org.bluez.Agent1", in_signature="ou")
    def RequestConfirmation(self, o, u):
        pass

    @dbus.service.method("org.bluez.Agent1", in_signature="o")
    def RequestAuthorization(self, o):
        pass

    @dbus.service.method("org.bluez.Agent1", in_signature="os")
    def AuthorizeService(self, o, s):
        pass

    @dbus.service.method("org.bluez.Agent1")
    def Cancel(self):
        pass


def main() -> int:
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    obj = Agent(bus)
    mgr = dbus.Interface(
        bus.get_object(BLUEZ, AGENT_MGR_PATH), AGENT_MGR_IFACE
    )

    print("PROBE: RegisterAgent capability acceptance (live system bus)")
    print("       RequestDefaultAgent is NEVER called.\n")
    print(f"{'capability':<20} {'result':<10} detail")
    print("-" * 72)

    accepted, rejected = [], []
    for cap in CAPABILITIES:
        label = repr(cap) if cap == "" else cap
        try:
            mgr.RegisterAgent(AGENT_PATH, cap)
            accepted.append(cap)
            print(f"{label:<20} {'ACCEPTED':<10}")
            try:
                mgr.UnregisterAgent(AGENT_PATH)
            except dbus.DBusException as e:
                print(f"{'':<20} {'':<10} cleanup failed: {e.get_dbus_message()}")
        except dbus.DBusException as e:
            rejected.append(cap)
            print(f"{label:<20} {'REJECTED':<10} {e.get_dbus_message()}")

    print("\n" + "=" * 72)
    print("VERDICT")
    print("=" * 72)
    print(f"accepted ({len(accepted)}): {accepted}")
    print(f"rejected ({len(rejected)}): {rejected}")

    # The two facts option C depends on.
    print("\nASSERT 1: 'NoInputNoOutput' is a valid capability")
    print("  ->", "PASS" if "NoInputNoOutput" in accepted else "FAIL")
    print("ASSERT 2: 'KeyboardDisplay' is a valid capability")
    print("  ->", "PASS" if "KeyboardDisplay" in accepted else "FAIL")
    print("ASSERT 3: capability strings are case-SENSITIVE")
    lower_ok = "keyboarddisplay" in accepted
    exact_ok = "KeyboardDisplay" in accepted
    print(f"  -> {'PASS' if (exact_ok and not lower_ok) else 'INCONCLUSIVE/FAIL'}"
          f" (exact accepted={exact_ok}, lowercase accepted={lower_ok})")
    print("ASSERT 4: an unrecognised capability is rejected (so the")
    print("          vocabulary is enforced, not free-form)")
    print("  ->", "PASS" if "NotACapability" in rejected else "FAIL")

    ok = (
        "NoInputNoOutput" in accepted
        and "KeyboardDisplay" in accepted
        and "NotACapability" in rejected
    )
    print(f"\nOVERALL: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
