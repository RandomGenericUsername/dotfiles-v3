# Review — D-Bus XML as single source of truth for `org.dotfiles.Events1`

**Scope:** prototype at `spikes/dbus-xml/`, assessed against
`contracts/event-contract.json` + `contracts/event-contract.md` (AD‑34/37/38/44).
**Method:** parse ONE introspection XML with two independent D-Bus parsers
(Python `dbus-fast` `Node.parse`; GJS `Gio.DBusNodeInfo.new_for_xml`), normalize,
and assert agreement by execution (`spikes/dbus-xml/run.sh`, transcript in
`spikes/dbus-xml/transcript.txt`). No prose-based checking.

## Verdict (two parts)

1. **Interface surface — YES.** One introspection XML can be the single source of
   the *wire interface*: interface/version name, method names and in/out arg
   names + signatures, signal names + arg signatures. Proven: both parsers
   produce byte-identical normalized models, and the model equals the
   `methods`/`signals` blocks of `contracts/event-contract.json`.
2. **Whole event contract — NO.** D-Bus introspection is structural only. The XML
   cannot express the topic registry, `a{sv}` payload field schemas, enums,
   required/optional keys, `epoch`/`seq` ordering, at-most-once delivery,
   hydration + reserved `_epoch`/`_seq`, job-lease semantics, typed-error
   meaning, or the size/depth/rate caps. `a{sv}` is an opaque variant map to
   D-Bus. Those must stay in the JSON/prose (or move to a companion schema).

So the accurate claim is: **XML is the single source of the interface surface; the
JSON remains the source of payload/semantic rules; a conformance script binds the
two so they cannot drift.** It is not "one XML replaces the contract".

## What runs (evidence)

| Artifact | What it proves |
| --- | --- |
| `spikes/dbus-xml/org.dotfiles.Events1.xml` | valid introspection XML for all 9 methods + 5 signals |
| `spikes/dbus-xml/python_parse.py` | `dbus-fast` parses + validates names; model `{interface, methods[{name,in,out}], signals[{name,args}]}` |
| `spikes/dbus-xml/gjs_parse.js` | `Gio.DBusNodeInfo.new_for_xml` yields the same model |
| `spikes/dbus-xml/conformance.py` | cross-parser agreement **and** XML↔JSON equality **and** declared-signal guard |
| `spikes/dbus-xml/negative_demos.sh` | guard fails on drift / undeclared emission (non-vacuous) |
| `spikes/dbus-xml/python_runtime_validate.py` | Python runtime type validation via `SignatureTree.verify` derived from XML |
| `spikes/dbus-xml/gjs_runtime_validate.js` | GJS runtime lookup/validation via `Gio.DBusInterfaceInfo` |
| `spikes/dbus-xml/run.sh` | one command runs all of the above |

Positive run (`run.sh` §1):

```
[1/4] Python parser : dbus-fast -> 9 methods, 5 signals
[2/4] GJS parser    : Gio.DBusNodeInfo.new_for_xml -> 9 methods, 5 signals
[3/4] cross-parser agreement: PASS (interface, methods in/out, signals args identical)
[4/4] XML <-> event-contract.json: PASS (interface, methods in/out, signals args identical)
RESULT: PASS
```

Negative run (`run.sh` §2) — every case is required to fail, and does:

- **A** XML drops `ReportProgress`, JSON still lists it → `XML <-> event-contract.json: FAIL` (cross-parser still PASS — drift is between XML and JSON, not between parsers).
- **B** interface renamed `…Events2` in XML only → `interface: xml='org.dotfiles.Events2' vs contract='org.dotfiles.Events1'`, FAIL.
- **C** producer emits `JobCrashed`, undeclared → `[emit] declared-signal guard: FAIL`, FAIL.
- **D** control: declared `JobFinished` passes the emit guard.

```
ALL NEGATIVE CASES CORRECTLY DETECTED
```

Runtime validation (`run.sh` §3), both sides reject exactly the wrong-type body
and the undeclared signal, and accept the declared ones:

```
GJS:    signal REJECT  JobStarted/sss (wrong types)    declared (ssu), emitted (sss)
        signal REJECT  JobCrashed/ssu (undeclared)     signal 'JobCrashed' not declared in XML
        RESULT: PASS
Python: signal REJECT  JobStarted/sss (wrong types)    SignatureBodyMismatchError: UINT32 "u" must be int
        signal REJECT  JobCrashed/ssu (undeclared)     signal 'JobCrashed' not declared in XML
        RESULT: PASS
```

## How each side enforces (and where it differs)

- **GJS/AGS (parse-once-and-enforce).** `Gio.DBusNodeInfo.new_for_xml` yields a
  `Gio.DBusInterfaceInfo` usable directly for enforcement: the hub passes it to
  `Gio.DBusConnection.register_object` (Gio serves introspection and rejects
  unknown/mis-typed incoming calls), and consumers pass it to
  `Gio.DBusProxy.new(...)` for typed method calls and `g-signal`. Outgoing signal
  bodies still need a lookup against `interface_info` (`lookup_signal`) plus a
  `GLib.Variant` type-string compare — demonstrated in `gjs_runtime_validate.js`.
  AGS already uses `Gio.DBusProxy` (`dotfiles/config/ags/bar/widgets/battery.tsx:31`).
- **Python hub (parse-once-and-generate/validate).** `dbus-fast` `Node.parse`
  validates the XML, but `ServiceInterface` is built from `@method`/`@signal`
  decorators — there is **no** "serve this introspection Node" path
  (`ServiceInterface.introspect()` goes class→XML, not XML→service). So the
  signatures must either be generated from the XML or hand-declared and guarded
  by a conformance test. dbus-fast still enforces **types** at marshal time
  (`SignatureTree.verify`, shown), so a thin XML-derived signature table gives
  real runtime validation; it is just not automatic.

Net: GJS gets boundary enforcement for free from Gio; Python needs a generated
table or a small assertion shim. Both can validate emissions against the XML at
runtime; only Gio enforces incoming calls without extra code.

## Does "execute to check" hold?

Yes for the checks it claims. Caveats, stated plainly:

- The **cross-parser check is near-tautological** (same bytes to both parsers).
  Its real value is confirming the XML is valid and means the same thing to both
  ecosystems, and catching parser-version divergences. The load-bearing checks
  are **XML↔JSON** and the **declared-signal guard**, both of which are proven
  non-vacuous by the negative demos.
- Exact-match equality is the **strictest** rule and conflicts with the
  contract's additive-change policy (AD‑34): adding a method/signal/topic is
  non-breaking. If XML is authoritative and the JSON is generated, additive
  changes are free; if the JSON is hand-kept, the check must become
  subset-tolerant (XML ⊇ JSON) for members, and non-breaking `a{sv}` payload
  additions are invisible to the wire and safe by construction.

## Integration with `contracts/`

Recommendation, minimal and honest:

1. Promote the XML to `contracts/org.dotfiles.Events1.xml` as the interface
   source; keep `event-contract.json` as the **semantic** source (topics,
   payloads, limits, versioning, errors).
2. **Derive** the JSON's `methods`/`signals` blocks from the XML (or delete them
   from the JSON and have consumers read the XML), so the signatures are not
   maintained twice. Keep `topics`/`delivery`/`validation`/errors in JSON.
3. Keep `contracts/event-contract.md` as descriptive prose, with its signature
   tables generated from the XML rather than hand-typed.
4. Wire `uv run contracts/conformance.py` (moved from the spike) into
   `Makefile`/CI as the drift gate; both runtime (`IEventPublisher`/
   `IEventSubscriber`, pending AD‑45) and AGS load the same XML at startup.
5. `a{sv}` payload validation (schema/size/depth/enum) stays a hub concern
   described in the JSON; the XML only fixes the *transport* signature
   `a{sv}` and cannot enforce field names or types.

## Files

- `spikes/dbus-xml/org.dotfiles.Events1.xml`
- `spikes/dbus-xml/python_parse.py`, `gjs_parse.js`, `conformance.py`
- `spikes/dbus-xml/python_runtime_validate.py`, `gjs_runtime_validate.js`
- `spikes/dbus-xml/negative_demos.sh`, `run.sh`, `transcript.txt`
- `reviews/schema-dbus-xml.md` (this file)

## How to run

```sh
# from repo root
bash spikes/dbus-xml/run.sh                 # everything
uv run spikes/dbus-xml/conformance.py        # positive only (exit 1 on drift)
uv run spikes/dbus-xml/conformance.py --check-emitted JobCrashed   # expected FAIL
bash spikes/dbus-xml/negative_demos.sh       # negative cases, exit 0 iff all detected
gjs spikes/dbus-xml/gjs_runtime_validate.js spikes/dbus-xml/org.dotfiles.Events1.xml
uv run spikes/dbus-xml/python_runtime_validate.py spikes/dbus-xml/org.dotfiles.Events1.xml
```

Requires: `gjs` (Gio), `uv` (fetch of `dbus-fast` is declared inline via PEP 723).
