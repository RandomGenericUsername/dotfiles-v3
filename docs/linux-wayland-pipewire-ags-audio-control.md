# Linux Wayland Dynamic Audio Control with PipeWire, WirePlumber, and AGS

## 1. Goal

The goal is to build a **dynamic, application-aware audio control system** for a Linux Wayland desktop.

The desired user experience is:

- Control the master output volume.
- Control individual application playback volumes.
- Dynamically discover applications instead of hard-coding names such as Chrome, Spotify, or Discord.
- Control microphones and other input devices.
- Discover recording applications dynamically.
- Potentially move application streams between output devices.
- Expose the controls through a custom **AGS** widget in the desktop bar.
- Have a conventional GUI available for configuration and troubleshooting.

The central design principle is:

> **Do not make AGS responsible for discovering or implementing the audio system. Let PipeWire/WirePlumber provide the audio graph and state, and use AGS as the user interface.**

---

## 2. Recommended Stack

The recommended architecture is:

```text
                         Linux Wayland Desktop
                                  │
                         ┌────────▼────────┐
                         │      AGS        │
                         │ Custom UI / Bar │
                         └────────┬────────┘
                                  │
                           Audio service/API
                                  │
                    ┌─────────────▼─────────────┐
                    │        PipeWire           │
                    │      Audio Graph           │
                    └─────────────┬─────────────┘
                                  │
                         ┌────────▼────────┐
                         │   WirePlumber   │
                         │ Session / Policy│
                         └────────┬────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │     pipewire-pulse        │
                    │ PulseAudio compatibility  │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │       pavucontrol          │
                    │ Conventional GUI mixer     │
                    └─────────────────────────────┘
```

### Main components

| Component | Responsibility |
|---|---|
| PipeWire | Audio server, graph, nodes, streams, routing |
| WirePlumber | Session management and policy |
| pipewire-pulse | PulseAudio compatibility server |
| wpctl | Command-line control/debugging interface |
| pavucontrol | Graphical mixer/control panel |
| AGS | Custom desktop UI |
| Your widget | Presentation and interaction layer |

---

# 3. PipeWire: The Core Audio System

PipeWire is the underlying multimedia server and graph.

For this project, the important concept is that audio is represented as a **graph of nodes and streams**.

A simplified graph looks like:

```text
             ┌─────────────────┐
             │ Chrome / YouTube│
             └────────┬────────┘
                      │
                      ▼
                ┌───────────┐
                │ PipeWire  │
                │   Graph   │
                └─────┬─────┘
                      │
                      ▼
              ┌───────────────┐
              │ Headphones    │
              │ Output Device │
              └───────────────┘
```

Multiple applications can participate simultaneously:

```text
Chrome ─────────────┐
                    │
Spotify ────────────┤
                    ├──► PipeWire ───► Headphones
Discord ────────────┤
                    │
System sounds ──────┘
```

Each application can have its own stream.

That is what makes per-application volume possible.

---

# 4. PipeWire Terminology

Understanding the terminology is important before building the AGS widget.

## 4.1 Node

A **node** is an entity in the PipeWire graph.

Examples can include:

- audio hardware
- speakers
- headphones
- microphones
- playback streams
- recording streams
- virtual audio devices

---

## 4.2 Sink

A sink is an audio output target.

For example:

```text
Built-in Speakers
USB Headphones
HDMI Monitor
Bluetooth Headset
```

Conceptually:

```text
Application
     │
     ▼
  Playback
   Stream
     │
     ▼
   Sink
     │
     ▼
Physical output
```

---

## 4.3 Source

A source is an audio input.

Examples:

```text
Built-in microphone
USB microphone
Bluetooth headset microphone
Virtual microphone
```

Conceptually:

```text
Physical microphone
        │
        ▼
      Source
        │
        ▼
Application recording stream
```

---

## 4.4 Playback Stream

A playback stream is audio being produced by an application.

Examples:

```text
Chrome
Spotify
Firefox
Discord
VLC
Steam
```

These are the objects that make the desired per-application volume controls possible.

---

## 4.5 Recording Stream

A recording stream is an application consuming audio from an input.

Examples:

```text
Discord ← microphone
OBS ← microphone
Chrome ← microphone
Audacity ← microphone
```

These can be treated separately from physical input devices.

---

# 5. WirePlumber

PipeWire provides the graph, but a desktop system needs policy and session management.

That is where **WirePlumber** comes in.

WirePlumber manages things such as:

- device discovery
- session policy
- default devices
- stream routing
- metadata
- application streams
- connecting streams to devices

A useful mental model is:

```text
PipeWire
    =
The audio graph

WirePlumber
    =
The manager deciding how the graph should behave
```

For a desktop environment, both are important.

---

# 6. pipewire-pulse

Many Linux applications and desktop utilities historically expect a PulseAudio server.

PipeWire provides a compatibility layer called:

```text
pipewire-pulse
```

This means software designed around the PulseAudio API can communicate with a PipeWire-based system.

This is particularly relevant to:

```text
pavucontrol
```

You therefore do not need to choose between "PipeWire" and "PulseAudio" when using pavucontrol on a normal modern PipeWire desktop.

The architecture is approximately:

```text
Application
     │
     │ PulseAudio API
     ▼
pipewire-pulse
     │
     ▼
PipeWire
     │
     ▼
WirePlumber / devices
```

---

# 7. pavucontrol: The GUI

The conventional GUI to use is:

```text
pavucontrol
```

It is extremely useful even if the final interface will be your AGS widget.

Its most useful purpose during development is to show what the audio system actually sees.

The Playback tab can expose application playback streams such as:

```text
Chrome
Spotify
Discord
System Sounds
```

with independent volume controls.

You can use it to answer questions such as:

- Does PipeWire see the application?
- Is the application producing a separate stream?
- What output is the stream connected to?
- Is the stream muted?
- Does changing its volume work?
- Does the stream disappear when the application stops playing audio?

This makes pavucontrol an excellent **reference implementation and debugging tool** for the AGS project.

---

# 8. wpctl: Command-Line Interface

WirePlumber provides:

```bash
wpctl
```

which is useful for inspecting and manipulating the audio graph.

The first command to learn is:

```bash
wpctl status
```

It provides a high-level view of devices, sinks, sources, and streams.

A conceptual output might look like:

```text
Audio
├── Devices
│   ├── Built-in Audio
│   └── USB Headset
│
├── Sinks
│   ├── Built-in Speakers
│   └── USB Headphones
│
├── Sources
│   ├── Built-in Microphone
│   └── USB Microphone
│
└── Streams
    ├── Chrome
    ├── Spotify
    └── Discord
```

The actual IDs and structure will depend on the machine.

---

# 9. Volume Control with wpctl

A stream/device has an object ID.

You can inspect volume:

```bash
wpctl get-volume <ID>
```

Set a volume:

```bash
wpctl set-volume <ID> 50%
```

Toggle mute:

```bash
wpctl set-mute <ID> toggle
```

This is useful for testing whether the underlying audio system behaves correctly before implementing the AGS interface.

---

# 10. AGS as the Custom Frontend

The important architectural decision is:

> **AGS should be a frontend to the audio system, not a second audio-management system.**

AGS can expose audio-related objects through its audio service.

Conceptually, you can work with collections such as:

```text
audio.speakers
audio.microphones
audio.apps
audio.recorders
```

The exact API depends on the AGS version you are using, so the installed version's documentation/API should be checked before writing production code.

The important abstraction is that **application streams are objects**.

---

# 11. Dynamic Application Discovery

This is the key feature you want.

Do not write:

```text
Chrome slider
Spotify slider
Discord slider
```

Instead think:

```text
audio.apps
    │
    ├── stream
    ├── stream
    ├── stream
    └── stream
```

Each stream becomes a UI component.

Conceptually:

```text
Application stream
        │
        ├── name
        ├── application ID
        ├── icon
        ├── volume
        ├── mute state
        └── stream ID
                │
                ▼
        AppVolumeSlider(stream)
```

Then:

```text
audio.apps.map(AppVolumeSlider)
```

produces the UI.

This is much better than hard-coding application names.

---

# 12. Dynamic Lifecycle

A good implementation must handle applications appearing and disappearing.

For example:

```text
Chrome starts YouTube
        │
        ▼
PipeWire creates stream
        │
        ▼
WirePlumber manages stream
        │
        ▼
AGS receives stream-added
        │
        ▼
Widget creates slider
```

When playback stops and the stream disappears:

```text
PipeWire removes stream
        │
        ▼
AGS receives stream-removed
        │
        ▼
Widget removes slider
```

Therefore the UI always represents the current audio graph.

---

# 13. Example UI Architecture

A practical audio popup could look like:

```text
┌──────────────────────────────────────────┐
│ 🔊 Audio                                 │
├──────────────────────────────────────────┤
│                                          │
│ OUTPUT                                   │
│                                          │
│ 🎧 Headphones                         72%│
│ ───────────────────────────────●──────── │
│                                          │
│ APPLICATIONS                             │
│                                          │
│ 🌐 Chrome                             68%│
│ ─────────────────────────────●────────── │
│                                          │
│ 🎵 Spotify                           42% │
│ ────────────────────●─────────────────── │
│                                          │
│ 💬 Discord                           81% │
│ ────────────────────────────────●─────── │
│                                          │
│ INPUT                                    │
│                                          │
│ 🎙 USB Microphone                     74%│
│ ─────────────────────────────●────────── │
│                                          │
│ RECORDING                                │
│                                          │
│ 🎥 OBS                                90%│
│ ─────────────────────────────────●────── │
│                                          │
│ Output: Headphones                       │
│ Input:  USB Microphone                   │
└──────────────────────────────────────────┘
```

This interface should be generated from the current PipeWire/AGS state.

---

# 14. Outputs

The output section should distinguish between:

## Physical / logical output devices

For example:

```text
Built-in Speakers
USB Headphones
HDMI
Bluetooth Headset
```

and:

## Application playback streams

For example:

```text
Chrome
Spotify
Discord
```

These are different concepts.

A useful UI hierarchy is:

```text
OUTPUT

Default output
    Headphones          72%

Applications
    Chrome              68%
    Spotify             42%
    Discord             81%
```

---

# 15. Inputs

The same architecture can be applied to inputs.

For example:

```text
INPUT

Default microphone
    USB Microphone      74%

Recording applications
    Discord             80%
    OBS                 90%
    Chrome              50%
```

Again, do not hard-code application names.

The application list should be generated from the currently active recording streams.

---

# 16. Routing

Volume is only one part of audio management.

PipeWire also supports routing streams to different targets.

Conceptually:

```text
Chrome ───────────► Headphones
Spotify ──────────► Speakers
Discord ──────────► Headphones
OBS ──────────────► Monitor
```

A future AGS interface could therefore expose:

```text
Chrome
Volume: 68%

Output:
[ Headphones ▼ ]
```

The dropdown would be populated from the currently available sinks.

This is another case where dynamic discovery is preferable to hard-coding.

---

# 17. Important Browser Limitation

There is an important distinction between:

```text
Application
```

and:

```text
Browser tab / web application
```

You specifically want to distinguish:

```text
Chrome / YouTube
Chrome / WhatsApp
```

That is not guaranteed to map to two independent PipeWire streams.

PipeWire generally sees audio streams created by the application/audio subsystem.

Depending on how Chromium creates and mixes its audio, you may see something closer to:

```text
Chrome
```

rather than:

```text
Chrome / YouTube
Chrome / WhatsApp
```

Therefore:

> **Per-application volume is a normal PipeWire use case. Per-browser-tab volume should not be assumed to be available through PipeWire.**

If Chrome exposes separate streams for particular audio contexts, they can potentially be controlled independently. But the AGS widget should not assume that every browser tab is independently represented.

---

# 18. Recommended AGS Data Model

The widget should conceptually work with objects rather than names.

For an application stream:

```text
ApplicationStream
├── id
├── name
├── application_id
├── description
├── icon_name
├── volume
├── muted
└── target/output information
```

Then the widget becomes:

```text
PipeWire/AGS object
        │
        ▼
ApplicationStream
        │
        ▼
AppVolumeWidget
```

This gives you a clean separation:

```text
Audio infrastructure
        │
        ▼
AGS service
        │
        ▼
Data model
        │
        ▼
Widgets
```

---

# 19. Avoid Using wpctl as the Main AGS API

`wpctl` is excellent for:

- manual testing
- shell scripts
- diagnostics
- troubleshooting
- quick experiments

But it is not ideal as the primary mechanism for a reactive UI.

A bad architecture would repeatedly execute:

```text
wpctl status
wpctl get-volume ...
wpctl get-volume ...
wpctl get-volume ...
```

from the UI.

That introduces unnecessary process spawning and polling.

A better architecture is:

```text
PipeWire / WirePlumber
        │
        ▼
AGS audio service
        │
        ▼
Reactive application objects
        │
        ▼
AGS widgets
```

Use `wpctl` to inspect and troubleshoot the system.

Use the AGS audio abstraction for the actual widget whenever possible.

---

# 20. Event-Driven Design

A dynamic UI should ideally be event-driven.

Conceptually:

```text
stream-added
      │
      ▼
create widget

stream-changed
      │
      ▼
update widget

stream-removed
      │
      ▼
destroy widget
```

This is preferable to constantly rebuilding the entire UI.

For example:

```text
Existing streams:

Chrome
Spotify
Discord

           ↓

User starts VLC

           ↓

stream-added(VLC)

           ↓

Create VLC slider

           ↓

Chrome
Spotify
Discord
VLC
```

No hard-coded modification is required.

---

# 21. Audio Widget Modules

A maintainable project could be organized approximately like:

```text
audio/
├── AudioPopup
├── OutputControl
├── InputControl
├── ApplicationList
├── ApplicationVolume
├── RecordingList
├── DeviceSelector
└── AudioIndicator
```

The responsibilities could be:

### AudioIndicator

Small bar component:

```text
🔊 72%
```

### OutputControl

Controls the default output device.

### InputControl

Controls the default microphone/input.

### ApplicationList

Dynamically discovers playback applications.

### ApplicationVolume

One reusable component representing one application stream.

### RecordingList

Dynamically discovers recording applications.

### DeviceSelector

Allows switching/routing between available devices.

---

# 22. Small Bar Widget vs Full Popup

It is useful to separate the two.

The bar can remain compact:

```text
[ 🔊 72% ]
```

Clicking it opens:

```text
┌───────────────────────────────┐
│ Audio                         │
│                               │
│ Output                        │
│ Headphones             72%    │
│                               │
│ Apps                          │
│ Chrome                 68%    │
│ Spotify                42%    │
│ Discord                81%    │
│                               │
│ Input                         │
│ Microphone             74%    │
└───────────────────────────────┘
```

This prevents the main Waybar/AGS bar from becoming cluttered.

---

# 23. Debugging Workflow

Before writing the AGS widget, verify the underlying audio stack.

## Step 1: Check PipeWire

```bash
systemctl --user status pipewire
```

You want the service running.

---

## Step 2: Check WirePlumber

```bash
systemctl --user status wireplumber
```

Again, it should be running.

---

## Step 3: Check pipewire-pulse

```bash
systemctl --user status pipewire-pulse
```

This is useful if you intend to use PulseAudio-compatible applications/tools.

---

## Step 4: Inspect the graph

```bash
wpctl status
```

Look for:

- sinks
- sources
- playback streams
- recording streams

---

## Step 5: Open pavucontrol

Run:

```bash
pavucontrol
```

Play audio in an application.

Verify that the application appears as a playback stream.

---

## Step 6: Test application volume

Change the application's volume in pavucontrol.

Then verify that the actual audio level changes.

---

## Step 7: Test routing

If multiple outputs exist, move a stream between outputs using pavucontrol.

---

## Step 8: Only then implement the AGS widget

At that point the UI is primarily a presentation/control problem rather than an audio-stack debugging problem.

---

# 24. Testing Scenarios

The AGS widget should eventually be tested with:

## One application

```text
Chrome
```

Expected:

```text
Chrome slider appears
```

---

## Multiple applications

```text
Chrome
Spotify
Discord
```

Expected:

```text
Chrome slider
Spotify slider
Discord slider
```

---

## Application starts after widget is open

```text
Widget open
      ↓
Start VLC
      ↓
VLC stream appears
      ↓
VLC slider appears
```

---

## Application stops

```text
Discord closes
      ↓
Discord stream disappears
      ↓
Discord slider disappears
```

---

## Mute

```text
Chrome
Volume: 68%
Mute: false

       ↓

Mute

       ↓

Chrome
Volume: 68%
Mute: true
```

The UI should distinguish volume from mute state.

---

## Device changes

Plug in:

```text
USB Headphones
```

Expected:

```text
USB Headphones
```

appears as an available output.

Unplug it:

```text
USB Headphones
```

disappears.

The UI should react accordingly.

---

# 25. Application Identity

Do not rely exclusively on a displayed name.

An application stream may expose several identifying properties.

Potentially useful fields include:

```text
application name
application ID
media name
description
icon name
process information
```

A good UI can use them roughly like:

```text
Primary label:
    Chrome

Secondary information:
    YouTube
```

when that information is actually exposed.

Do not assume that every application provides all fields.

---

# 26. Why This Architecture Scales

The biggest advantage is that the audio widget does not need to know what applications the user has installed.

Today:

```text
Chrome
Spotify
Discord
```

Tomorrow:

```text
Firefox
VLC
OBS
Steam
mpv
```

The widget continues to work.

The application list is a property of the live audio graph rather than the source code.

This is the same design principle used by many good system interfaces:

```text
Discover resources
        ↓
Represent resources as objects
        ↓
Generate UI from objects
```

rather than:

```text
Write a widget for every possible application
```

---

# 27. Recommended Development Order

Do not start by implementing the complete audio popup.

Use incremental development.

### Phase 1 — Verify infrastructure

Get:

```text
PipeWire
WirePlumber
pipewire-pulse
```

working.

---

### Phase 2 — Learn the graph

Use:

```bash
wpctl status
```

and:

```bash
pavucontrol
```

to understand what your machine exposes.

---

### Phase 3 — AGS master volume

Create a simple widget showing:

```text
🔊 72%
```

and allow changing the default output volume.

---

### Phase 4 — Dynamic application list

Read the AGS application streams.

Display:

```text
Chrome
Spotify
Discord
```

without hard-coding those names.

---

### Phase 5 — Per-application sliders

Each stream gets:

```text
Name
Icon
Volume slider
Mute control
```

---

### Phase 6 — Inputs

Add:

```text
Microphones
Recording streams
```

---

### Phase 7 — Routing

Add:

```text
Application → Output device
```

selection.

---

### Phase 8 — Polish

Add:

- icons
- animations
- scrolling
- sorting
- search/filtering
- compact mode
- keyboard controls
- mute indicators
- device switching

---

# 28. Potential Sorting Strategy

Once multiple applications are active, sorting becomes useful.

Possible ordering:

```text
Active applications
    ↓
Recently active
    ↓
Alphabetical
```

Alternatively:

```text
Highest volume
    ↓
Lowest volume
```

The important thing is that sorting should operate on discovered stream objects rather than application-specific rules.

---

# 29. Handling Duplicate Application Streams

An application may create multiple streams.

Therefore do not assume:

```text
one application = one stream
```

For example:

```text
Chrome
 ├── audio stream A
 └── audio stream B
```

could exist.

Your data model should operate on **stream IDs**, not merely application names.

If the desired UX is application-level aggregation, you can later group streams by application identity.

For example:

```text
Chrome
 ├── Stream A
 └── Stream B
```

could be presented as one logical application entry.

But that should be an explicit aggregation layer.

---

# 30. Distinguish Physical Devices from Streams

This distinction should remain explicit throughout the implementation.

```text
DEVICE

USB Headphones
USB Microphone
HDMI Output


STREAM

Chrome
Spotify
Discord
OBS
```

A device represents an endpoint.

A stream represents an application's audio flow.

They are related, but they are not the same object.

---

# 31. Future Extensions

Once the basic implementation works, the same architecture could support:

### Per-application routing

```text
Chrome → Headphones
Spotify → Speakers
```

### Default device selection

```text
Default output → Headphones
Default input  → USB microphone
```

### Bluetooth controls

When supported by the underlying device/session stack.

### Virtual devices

For example:

```text
Monitor of ...
Loopback
Virtual microphone
Virtual sink
```

### Stream muting

```text
Chrome → mute
```

### Keyboard shortcuts

For example:

```text
Super + F10 → volume down
Super + F11 → volume up
Super + F12 → mute
```

### Application-specific persistence

WirePlumber can be configured to remember routing/policy decisions, although this should be implemented only after understanding the normal default policy.

---

# 32. What Not to Build

Avoid creating a custom audio daemon.

You do not need:

```text
Your daemon
    ↓
PipeWire
```

You also do not need to continuously parse:

```bash
wpctl status
```

from AGS.

And you do not need to maintain a database containing:

```text
Chrome
Spotify
Discord
```

The audio graph already contains the current state.

Your application should primarily be:

```text
PipeWire/WirePlumber
        ↓
AGS audio service
        ↓
Reactive UI
```

---

# 33. GUI Recommendation

For the conventional desktop GUI:

```text
pavucontrol
```

is the first tool to install/use.

It gives you a practical way to inspect:

- Playback
- Recording
- Output devices
- Input devices
- Per-stream volumes
- Per-stream routing
- Mute state

It should remain installed even after your custom AGS widget is complete because it is useful for diagnosing problems.

---

# 34. CLI Recommendation

Keep these commands available:

```bash
wpctl status
```

```bash
wpctl get-volume <ID>
```

```bash
wpctl set-volume <ID> 50%
```

```bash
wpctl set-mute <ID> toggle
```

They are particularly useful when debugging your AGS widget.

---

# 35. Architecture Summary

The final architecture should look like:

```text
                          ┌───────────────────────┐
                          │       AGS Bar         │
                          │                       │
                          │       🔊 72%          │
                          └───────────┬───────────┘
                                      │
                                      ▼
                          ┌───────────────────────┐
                          │     Audio Popup       │
                          │                       │
                          │ Outputs               │
                          │ Inputs                │
                          │ Applications          │
                          │ Recorders             │
                          │ Routing               │
                          └───────────┬───────────┘
                                      │
                                      ▼
                          ┌───────────────────────┐
                          │     AGS Audio API     │
                          └───────────┬───────────┘
                                      │
                                      ▼
                          ┌───────────────────────┐
                          │       PipeWire        │
                          │                       │
                          │ Nodes / Streams       │
                          │ Sinks / Sources       │
                          └───────────┬───────────┘
                                      │
                                      ▼
                          ┌───────────────────────┐
                          │     WirePlumber       │
                          │ Session / Policy      │
                          └───────────┬───────────┘
                                      │
                                      ▼
                 ┌────────────────────────────────────────┐
                 │ Hardware / Applications                │
                 │                                        │
                 │ Chrome   Spotify   Discord   OBS       │
                 │ Speakers  Headphones  Microphones      │
                 └────────────────────────────────────────┘
```

---

# 36. Final Design Principles

The most important principles for the implementation are:

1. **PipeWire is the audio graph.**
2. **WirePlumber manages desktop audio policy and session state.**
3. **pipewire-pulse provides compatibility with PulseAudio clients.**
4. **pavucontrol is the conventional GUI and an excellent debugging tool.**
5. **wpctl is useful for CLI inspection and testing.**
6. **AGS should act as the custom UI layer.**
7. **Discover streams dynamically rather than hard-coding applications.**
8. **Treat stream IDs as the identity of individual audio streams.**
9. **Do not assume one application always equals one stream.**
10. **Do not assume browser tabs are independently exposed as PipeWire streams.**
11. **Keep physical devices and application streams as separate concepts.**
12. **Prefer reactive/event-driven updates over polling.**
13. **Build the system incrementally: output → applications → inputs → routing → polish.**
14. **Use pavucontrol to validate the audio graph before debugging AGS.**

The key conceptual model is:

```text
             AUDIO INFRASTRUCTURE
                     │
             PipeWire / WirePlumber
                     │
                     ▼
                AUDIO OBJECTS
                     │
       ┌─────────────┼─────────────┐
       ▼             ▼             ▼
     Outputs       Apps         Inputs
       │             │             │
       ▼             ▼             ▼
     Sliders       Sliders       Sliders
       │             │             │
       └─────────────┼─────────────┘
                     ▼
                  AGS UI
```

That gives you a clean, extensible system where the UI is generated from the actual state of the Linux audio system instead of being tied to a fixed list of applications.

---

## References

- PipeWire documentation: https://pipewire.pages.freedesktop.org/pipewire/
- WirePlumber documentation: https://pipewire.pages.freedesktop.org/wireplumber/
- WirePlumber `wpctl` documentation: https://pipewire.pages.freedesktop.org/wireplumber/man/wpctl.html
- WirePlumber stream configuration: https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/stream.html
- AGS audio service documentation: https://aylur.github.io/ags-docs/services/audio/
- pavucontrol project: https://freedesktop.org/software/pulseaudio/pavucontrol/
