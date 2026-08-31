# Hyprland Screenshot & Screen Recording Tool — Full Project Plan

**Status:** Design and technical investigation  
**Target environment:** Arch Linux / EndeavourOS, Hyprland, Wayland, AGS v3/Astal, Waybar  
**Date:** August 28, 2026

---

# 1. Project Goal

Build a custom screenshot and screen-recording utility integrated into the user's Hyprland desktop shell.

The application will use **AGS as the graphical interface and controller**, while delegating actual capture and encoding to established Wayland-native command-line tools.

The application should provide two distinct workflows:

1. **Screenshot**
2. **Recording**

Both workflows share the same capture targets:

- Region
- Screen
- Window

but expose different settings appropriate to the operation.

The application should feel like a native component of the user's Hyprland environment rather than a generic standalone GUI application.

---

# 2. Core UX Concept

The main interface contains two top-level modes:

```text
┌─────────────────────────────────────────────┐
│                                             │
│       📷 Screenshot     🎥 Recording        │
│       ─────────────                          │
│                                             │
│       ...selected interface...              │
│                                             │
└─────────────────────────────────────────────┘
```

The user chooses what operation they want first:

- Screenshot
- Recording

The selected operation then determines which settings are displayed.

The three capture targets are common to both:

- Region
- Screen
- Window

This gives us a clean conceptual model:

```text
Operation:
    screenshot | recording

Target:
    region | screen | window
```

The application should not expose implementation details such as `grim`, `slurp`, `wf-recorder`, FFmpeg, or GPU Screen Recorder to the user.

---

# 3. Screenshot UI

The screenshot interface is currently defined as:

```text
┌─────────────────────────────────────────────┐
│  📷 Screenshot                              │
│                                             │
│  CAPTURE                                    │
│                                             │
│  ┌────────────┐ ┌────────────┐ ┌──────────┐│
│  │     ⛶     │ │     🖥     │ │    ▣     ││
│  │   Region   │ │   Screen   │ │  Window  ││
│  └────────────┘ └────────────┘ └──────────┘│
│                                             │
│  DELAY                                      │
│  [ None ] [ 3s ] [ 5s ] [ 10s ]            │
│                                             │
│  FORMAT                                     │
│  [ PNG ] [ JPEG ]                           │
│                                             │
│  OUTPUT                                     │
│  [ 📋 Clipboard ] [ 💾 Save ]               │
│                                             │
│                    [ Take Screenshot ]      │
└─────────────────────────────────────────────┘
```

## 3.1 Capture targets

### Region

The user selects an arbitrary rectangle using `slurp`.

Conceptually:

```text
AGS
 ↓
hide UI
 ↓
slurp
 ↓
geometry
 ↓
grim
```

### Screen

Capture the monitor selected by the application.

The application can obtain monitor information from Hyprland rather than requiring the user to manually specify monitor names.

### Window

Capture the currently focused Hyprland window.

Hyprland exposes client information including position and dimensions through its IPC, and Astal provides a Hyprland library exposing clients and their geometry.

Therefore:

```text
focused Hyprland client
        ↓
x / y / width / height
        ↓
capture geometry
        ↓
grim
```

This is specifically Hyprland-aware and does not attempt to provide generic compositor-independent window capture.

---

# 4. Screenshot Settings

## Delay

Available options:

```text
None
3 seconds
5 seconds
10 seconds
```

The delay occurs before capture.

For region capture:

```text
Start
 ↓
delay
 ↓
slurp
 ↓
grim
```

The UI should disappear before `slurp` begins.

## Format

Initial formats:

```text
PNG
JPEG
```

PNG should be the default.

Additional formats such as WebP can be considered later, but should not complicate the initial UI.

## Output

Available options:

```text
Clipboard
Save
```

The implementation can use `wl-copy` for clipboard output.

Hyprland's documentation explicitly recommends `grim` + `slurp` and `wl-copy` for this workflow.

Possible future option:

```text
Clipboard + Save
```

---

# 5. Recording UI

The recording UI is deliberately separate from the screenshot UI because recording has significantly different configuration requirements.

Proposed interface:

```text
┌─────────────────────────────────────────────┐
│  🎥 Recording                               │
│                                             │
│  CAPTURE                                    │
│                                             │
│  ┌────────────┐ ┌────────────┐ ┌──────────┐│
│  │     ⛶     │ │     🖥     │ │    ▣     ││
│  │   Region   │ │   Screen   │ │  Window  ││
│  └────────────┘ └────────────┘ └──────────┘│
│                                             │
│  FPS                                         │
│  [ 24 ] [ 30 ] [ 60 ]                       │
│                                             │
│  FORMAT                                     │
│  [ MP4 ] [ WebM ] [ GIF ]                   │
│                                             │
│  AUDIO                                      │
│  [ 🔇 None ] [ 🔊 System ] [ 🎙 Mic ]       │
│                                             │
│  QUALITY                                    │
│  [ Low ] [ Medium ] [ High ]                │
│                                             │
│  DURATION                                   │
│  [ ∞ ] [ 10s ] [ 30s ] [ 60s ] [ Custom ] │
│                                             │
│                     [ 🔴 Start Recording ]  │
└─────────────────────────────────────────────┘
```

---

# 6. Recording Capture Targets

The same three targets are used:

```text
Region
Screen
Window
```

This consistency is intentional.

The user does not need to learn two different capture systems.

## Region

Interactive selection using `slurp`.

## Screen

Capture a specific monitor.

## Window

Capture the focused Hyprland window.

Window capture is one of the items that should be tested early because Wayland intentionally restricts global window access compared with X11. However, Hyprland exposes the necessary client geometry through its IPC, making geometry-based capture viable for a Hyprland-specific implementation. Astal's Hyprland library exposes client position, size, title, address, monitor, and other properties.

---

# 7. Recording FPS

Initial options:

```text
24
30
60
```

The backend must receive the selected FPS explicitly.

`wf-recorder` supports a constant framerate option (`--framerate`).

GPU Screen Recorder also exposes an FPS option and defaults to 60 FPS.

---

# 8. Recording Formats

Initial UI:

```text
MP4
WebM
GIF
```

There is an important technical distinction:

- MP4/WebM are video containers.
- H.264/HEVC/AV1/etc. are codecs.
- GIF is an animated image format.

Therefore codec selection should **not** be exposed in the main UI initially.

The UI should present user-oriented choices such as:

```text
MP4
WebM
GIF
```

and the application should select sensible codecs internally.

`wf-recorder` delegates encoding to FFmpeg and determines the output format from the file extension when using `-f`. It also supports explicitly selecting codecs and muxers.

GPU Screen Recorder currently supports H.264, HEVC, AV1, VP8, and VP9 and supports MP4, MKV, FLV, and WebM containers.

## GIF

GIF should be treated as a special recording mode.

It should not necessarily expose exactly the same settings as normal video.

For example, when GIF is selected:

```text
FPS
[ 10 ] [ 15 ] [ 20 ] [ 30 ]

SIZE
[ Original ] [ 75% ] [ 50% ]
```

Audio should automatically disappear because GIF does not contain audio.

The GIF implementation may involve a separate encoding/conversion pipeline rather than simply asking the primary recorder to produce a GIF.

This should be validated during backend testing.

---

# 9. Recording Audio

Initial options:

```text
None
System
Microphone
```

A future option may be:

```text
System + Microphone
```

Audio is technically feasible.

`wf-recorder` supports audio capture and allows selecting an audio device. It also supports an audio backend and audio codec configuration.

GPU Screen Recorder supports audio devices and application audio through PipeWire.

The exact implementation should use the user's existing PipeWire/WirePlumber environment.

---

# 10. Recording Quality

The UI should initially expose:

```text
Low
Medium
High
```

These are user-facing presets rather than raw bitrate/codec parameters.

Internally they can map to appropriate encoder parameters.

For example, the conceptual model is:

```text
Low
 ↓
smaller file / lower bitrate

Medium
 ↓
balanced

High
 ↓
higher bitrate / better quality
```

Exact values should be determined after selecting the recording backend.

The user should not have to understand CRF, bitrate, GOP, B-frames, VAAPI parameters, etc.

Advanced codec configuration can be added later under a settings page if actually needed.

---

# 11. Recording Duration

The recording UI includes:

```text
∞
10 seconds
30 seconds
60 seconds
Custom
```

This allows useful workflows such as:

> Record this region for 10 seconds as a GIF.

If infinite duration is selected, the recording continues until the user explicitly stops it.

If a finite duration is selected:

```text
Start
 ↓
record
 ↓
duration reached
 ↓
stop
 ↓
finalize file
```

The UI should display remaining time where useful.

---

# 12. Persistent Recording State

This is a major architectural requirement.

Starting a recording must **not** mean that the recording depends on the AGS popup remaining open.

Instead:

```text
AGS UI
   │
   │ start
   ↓
Capture Controller
   │
   ↓
Recorder process
   │
   └── continues independently
```

The recording process must continue after:

- the configuration UI disappears;
- the user changes workspace;
- the user interacts with other applications.

The application needs persistent runtime state such as:

```text
recordingState:
    idle
    recording
    paused

startedAt
elapsed
duration
target
format
outputPath
pid
```

---

# 13. Recording Tray / Status Indicator

The user specifically wants a persistent indicator in the system bar while recording.

Desired behavior:

```text
Normal desktop:

Waybar
──────────────────────────────────────
          ...       🔴
```

Clicking the indicator should expose recording controls.

For example:

```text
┌──────────────────────────┐
│ 🔴 Recording             │
│                          │
│        00:37             │
│                          │
│  [ ⏸ Pause ] [ ⏹ Stop ] │
└──────────────────────────┘
```

When paused:

```text
┌──────────────────────────┐
│ ⏸ Recording paused       │
│                          │
│        00:37             │
│                          │
│  [ ▶ Resume ] [ ⏹ Stop ]│
└──────────────────────────┘
```

---

# 14. Important Tray Architecture Finding

There is an important distinction between **consuming** a system tray and **creating** a system-tray item.

Astal's Tray library implements/handles the StatusNotifierItem system and is primarily a tray management/host library.

The FreeDesktop StatusNotifier specification defines:

- StatusNotifierItem — the application providing the indicator
- StatusNotifierWatcher — tracks indicators
- StatusNotifierHost — displays indicators

Applications register their StatusNotifierItem on D-Bus.

Therefore, if the desired icon is literally a traditional **system tray item**, we should not assume that `AstalTray` itself is the correct API for creating our own indicator.

There are two better implementation options.

## Preferred option for this setup: Waybar custom module

Because the desktop already uses Waybar, the simplest solution is to add a custom Waybar module dedicated to recording state.

Waybar custom modules support:

- scripts;
- JSON output;
- dynamic text/icon;
- CSS classes;
- click actions;
- tooltips;
- signals/updates.

This is directly supported by the current Waybar custom-module interface.

Conceptually:

```text
Recording Controller
        │
        ├── state = idle
        │
        └── state = recording
                │
                ↓
          Waybar custom module
                │
                ↓
             🔴 00:37
```

Click:

```text
Waybar
 ↓
recording-control command
 ↓
pause / resume / stop
```

This is simpler and more reliable than implementing an SNI producer purely to get an icon into a tray that already belongs to Waybar.

## Alternative: actual StatusNotifierItem

If we specifically want a real SNI item rather than a Waybar custom module, the application can implement/register a StatusNotifierItem through D-Bus.

This is technically possible according to the StatusNotifier specification, but it adds unnecessary infrastructure for this project.

Therefore:

**Recommended:** use a Waybar custom module for the recording indicator.

---

# 15. Pause / Resume

Pause is one of the most important backend-selection criteria.

Originally this was considered uncertain with `wf-recorder`.

The investigation found that **GPU Screen Recorder explicitly supports pause/resume**.

Its current man page documents:

```text
SIGINT
    Stop and save recording

SIGUSR2
    Pause/unpause recording
```

for normal recording.

There is also a current 2026 Hyprland-oriented project discussion showing this exact mechanism being used for a screen-recording bar indicator: pause/resume is implemented by sending `SIGUSR2` to the running GPU Screen Recorder process.

This makes GPU Screen Recorder considerably more attractive for the recording backend.

However, pause/resume still needs to be tested directly on the target system before the implementation is declared final.

---

# 16. Recording Backend Investigation

Three primary candidates were considered.

## 16.1 wf-recorder

Advantages:

- Native Wayland.
- Lightweight.
- Specifically recommended by Hyprland.
- Uses `wlr-screencopy`.
- Works naturally with `slurp`.
- Supports region geometry.
- Supports FPS.
- Supports audio.
- Uses FFmpeg.
- Supports hardware encoding through FFmpeg/VAAPI.
- Very simple process model.

Hyprland's current documentation explicitly recommends `wf-recorder` for recording and provides region-recording examples using `slurp`.

`wf-recorder`'s current documentation confirms support for:

- geometry;
- output selection;
- FPS;
- codecs;
- audio;
- audio codecs;
- FFmpeg muxers;
- hardware encoding.

### Main disadvantage

Pause/resume is not an obvious native control exposed by wf-recorder.

Therefore it does not fit the tray-control requirement as cleanly.

---

# 17. GPU Screen Recorder

GPU Screen Recorder is currently the most promising candidate for the recording backend.

Its current documentation states that it:

- works on X11 and Wayland;
- supports AMD, Intel, and NVIDIA;
- uses GPU-accelerated encoding;
- supports H.264, HEVC, AV1, VP8 and VP9;
- supports audio;
- supports monitors;
- supports regions;
- supports Wayland portal capture;
- supports screenshots;
- supports instant replay.

Its current command-line interface also explicitly supports:

```text
-w region
-w monitor
-w portal
```

and region geometry compatible with `slurp`.

It also explicitly supports:

```text
SIGUSR2
```

for pause/unpause during normal recording.

This is a very strong match for the project's requirements.

### Important limitation

GPU Screen Recorder's current CLI documentation says that direct window capture by window ID/focused window is X11-only, while Wayland supports portal capture and region/monitor capture.

Therefore, **our "Window" mode on Wayland needs to be investigated carefully.**

A possible implementation is:

```text
Hyprland focused client
        ↓
get geometry
        ↓
capture rectangle
```

rather than asking GPU Screen Recorder to perform native window selection.

That should be tested.

---

# 18. wl-screenrec

`wl-screenrec` is another Wayland-native recorder explicitly recommended by Hyprland.

It should be considered as a fallback or alternative during the backend benchmark.

However, based on the currently identified requirements, it is not the first candidate because the project specifically needs:

- audio;
- multiple output formats;
- GIF;
- pause/resume;
- strong process control;
- potentially hardware encoding.

The backend investigation should determine whether wl-screenrec provides enough of these features without additional processing.

---

# 19. OBS Studio

OBS is fully viable on Wayland through PipeWire and the Hyprland desktop portal. Hyprland documents OBS as a supported recording solution.

However, OBS is not the preferred backend.

OBS is designed for much more complicated workflows:

- scenes;
- sources;
- streaming;
- cameras;
- overlays;
- audio mixing;
- recording profiles.

Our application needs:

```text
capture target
+
encoding settings
+
recording lifecycle
```

Using OBS as a hidden backend would introduce unnecessary complexity.

---

# 20. Backend Recommendation

Current recommendation:

### Screenshot backend

```text
grim
+
slurp
+
wl-copy
```

### Recording backend

**Investigate GPU Screen Recorder first.**

Fallback:

```text
wf-recorder
```

The reason GPU Screen Recorder moves ahead of wf-recorder is not simply performance.

The decisive feature is:

```text
start
pause
resume
stop
```

combined with:

- Wayland support;
- region recording;
- monitor recording;
- FPS;
- audio;
- hardware encoding;
- multiple video formats.

The final backend decision must still be made after testing on the target machine.

---

# 21. AGS Technical Role

AGS should be responsible for:

- rendering the UI;
- storing UI state;
- launching the capture controller;
- tracking recorder state;
- displaying errors;
- displaying completion state;
- opening/closing the capture window;
- integrating with the existing desktop shell.

AGS should **not** implement:

- video encoding;
- screenshot capture protocols;
- FFmpeg;
- GPU encoding;
- audio recording;
- GIF encoding.

AGS is the frontend/controller.

The underlying utilities are the capture engine.

AGS v3 uses TypeScript/GJS and Gnim/GTK for its UI. The official documentation describes AGS as a framework for building Wayland desktop shells, while Astal provides system libraries behind it.

---

# 22. AGS Process Management

Astal provides process utilities for starting external processes and monitoring their stdout/stderr.

This allows the application to launch a recorder as a child process and retain a process handle.

Conceptually:

```text
RecorderController
        │
        ├── start()
        │      ↓
        │   subprocess()
        │
        ├── stop()
        │      ↓
        │   SIGINT
        │
        ├── pause()
        │      ↓
        │   SIGUSR2
        │
        └── resume()
               ↓
            SIGUSR2
```

The exact signal/process API should be implemented and tested rather than relying on shell commands such as `pkill`.

The controller should preferably retain the exact PID/process object that it started.

---

# 23. Hyprland Integration

Astal provides a dedicated Hyprland library that monitors Hyprland's IPC socket and exposes:

- clients;
- monitors;
- workspaces;
- active state;
- Hyprland events.



This allows the application to query:

```text
focused client
client x
client y
client width
client height
monitor list
active monitor
```

without repeatedly parsing `hyprctl` command output.

This is preferable to shelling out to `hyprctl` everywhere.

---

# 24. Wayland / Hyprland Screencopy Permissions

Current Hyprland versions have a screencopy permission system.

The current Hyprland documentation identifies:

```text
grim
wl-screenrec
wf-recorder
```

as applications that directly access the screen through Wayland protocols and may therefore be subject to the `screencopy` permission system.

The default mode is currently `ASK`.

If denied, capture can produce a black screen with a permission-denied message.

Therefore the installation/configuration part of the project must include a permission strategy.

The final setup should ensure the capture binaries are allowed to capture without requiring a permission prompt every time.

This should be handled explicitly rather than silently assuming capture will work.

---

# 25. Proposed Application Architecture

The application should be divided into these logical components:

```text
capture-tool/
│
├── app/
│   ├── main.tsx
│   │
│   ├── ui/
│   │   ├── CaptureWindow.tsx
│   │   ├── ScreenshotView.tsx
│   │   ├── RecordingView.tsx
│   │   ├── TargetSelector.tsx
│   │   ├── SettingSelector.tsx
│   │   └── RecordingIndicator.tsx
│   │
│   ├── capture/
│   │   ├── CaptureController.ts
│   │   ├── ScreenshotController.ts
│   │   ├── RecordingController.ts
│   │   ├── TargetResolver.ts
│   │   └── Backends/
│   │       ├── GrimBackend.ts
│   │       ├── WfRecorderBackend.ts
│   │       └── GpuScreenRecorderBackend.ts
│   │
│   ├── state/
│   │   ├── ScreenshotState.ts
│   │   └── RecordingState.ts
│   │
│   └── utils/
│       ├── paths.ts
│       ├── filenames.ts
│       └── notifications.ts
│
└── scripts/
    └── installation/setup scripts if needed
```

The exact filenames are not final; the important part is the separation of responsibilities.

---

# 26. Screenshot State Model

Conceptually:

```text
ScreenshotConfig
├── target
│   ├── region
│   ├── screen
│   └── window
│
├── delay
│
├── format
│   ├── png
│   └── jpeg
│
└── output
    ├── clipboard
    └── file
```

Runtime state:

```text
ScreenshotState
├── idle
├── waiting
├── selecting
├── capturing
├── completed
└── error
```

---

# 27. Recording State Model

Configuration:

```text
RecordingConfig
├── target
│   ├── region
│   ├── screen
│   └── window
│
├── fps
│
├── format
│   ├── mp4
│   ├── webm
│   └── gif
│
├── audio
│   ├── none
│   ├── system
│   └── microphone
│
├── quality
│   ├── low
│   ├── medium
│   └── high
│
└── duration
    ├── infinite
    ├── 10
    ├── 30
    ├── 60
    └── custom
```

Runtime state:

```text
RecordingState
├── idle
├── starting
├── recording
├── paused
├── stopping
├── finalizing
├── completed
└── error
```

---

# 28. Capture Controller Abstraction

The UI should never directly execute `grim` or `gpu-screen-recorder`.

Instead:

```text
UI
 ↓
CaptureController
 ↓
Backend
```

For example:

```text
ScreenshotController.capture(config)
```

and:

```text
RecordingController.start(config)
RecordingController.pause()
RecordingController.resume()
RecordingController.stop()
```

This lets us change the backend without redesigning the UI.

---

# 29. Target Resolution

The target abstraction should be:

```text
TargetResolver
```

with:

```text
resolveRegion()
resolveScreen()
resolveWindow()
```

## Region

Invoke:

```text
slurp
```

and return geometry.

## Screen

Query Hyprland monitors and determine the requested output geometry.

## Window

Query the active Hyprland client and return:

```text
x
y
width
height
```

The backend receives a geometry rather than knowing anything about Hyprland.

This is an important abstraction:

```text
Hyprland
   ↓
TargetResolver
   ↓
geometry
   ↓
capture backend
```

---

# 30. Recording Indicator Architecture

Recommended implementation:

```text
AGS application
       │
       │ owns recording state
       ↓
recording-state IPC / state file / socket
       │
       ↓
Waybar custom module
```

The exact communication mechanism should be selected during implementation.

Possible options:

### Unix socket

Best long-term architecture.

```text
AGS
 ↕
Unix socket
 ↕
Waybar module
```

### State file

Simpler initial implementation:

```text
~/.cache/<application>/recording-state.json
```

Waybar reads it.

### Dedicated local CLI

For example:

```text
capture-tool status
capture-tool pause
capture-tool resume
capture-tool stop
```

Waybar calls the CLI.

This is particularly attractive because it also gives the user a command-line interface.

A possible final design is:

```text
capture-tool
├── ui
├── start
├── pause
├── resume
├── stop
└── status
```

AGS and Waybar then become clients of the same controller.

---

# 31. Recommended Long-Term Architecture

The strongest architecture is actually:

```text
                    capture-tool
                         │
              ┌──────────┴──────────┐
              │                     │
         Control API            Capture engine
              │                     │
       ┌──────┴──────┐       ┌──────┴──────┐
       │             │       │             │
      AGS         Waybar   Screenshot   Recording
       │                       │             │
       │                      grim      recorder
       │
       └──────── UI
```

This prevents the recording process from being coupled to a GTK window.

---

# 32. User Flow — Screenshot

```text
Open capture UI
       ↓
Screenshot
       ↓
Region / Screen / Window
       ↓
Delay
       ↓
PNG / JPEG
       ↓
Clipboard / Save
       ↓
Take Screenshot
       ↓
capture
       ↓
notification / optional preview
       ↓
done
```

For Region:

```text
Take Screenshot
       ↓
hide AGS UI
       ↓
delay
       ↓
slurp
       ↓
grim
       ↓
output
```

---

# 33. User Flow — Recording

```text
Open capture UI
       ↓
Recording
       ↓
Region / Screen / Window
       ↓
FPS
       ↓
MP4 / WebM / GIF
       ↓
Audio
       ↓
Quality
       ↓
Duration
       ↓
Start Recording
       ↓
configuration UI closes
       ↓
recording continues in background
       ↓
Waybar recording indicator appears
       ↓
user clicks indicator
       ↓
Pause / Resume / Stop
       ↓
recording finalizes
       ↓
notification / output
```

---

# 34. Recording Tray State Machine

The tray indicator should have at least three states.

## Idle

```text
No recording icon
```

or the module is hidden.

## Recording

```text
🔴 00:37
```

Click:

```text
pause / stop controls
```

## Paused

```text
⏸ 00:37
```

Click:

```text
resume / stop controls
```

This state machine is directly compatible with GPU Screen Recorder's pause/resume capability.

---

# 35. Notifications

After screenshot:

```text
Screenshot captured
~/Pictures/Screenshots/2026-08-28_16-50-21.png
```

After recording:

```text
Recording saved
~/Videos/Recordings/2026-08-28_16-52-03.mp4
```

On failure:

```text
Capture failed
<short useful error>
```

Notifications should not expose raw backend errors unless useful.

Detailed errors should be logged for debugging.

---

# 36. File Naming

Recommended default:

```text
Screenshots:
~/Pictures/Screenshots/

Recordings:
~/Videos/Recordings/
```

Filename pattern:

```text
screenshot_YYYY-MM-DD_HH-MM-SS.ext
recording_YYYY-MM-DD_HH-MM-SS.ext
```

Example:

```text
screenshot_2026-08-28_16-51-23.png
recording_2026-08-28_16-54-02.mp4
```

The output directory and filename template should eventually be configurable.

---

# 37. UI Persistence

The application should remember the last-used configuration.

For example:

If the user normally records:

```text
Screen
60 FPS
MP4
System audio
High quality
```

the next time Recording is opened, those options should remain selected.

Similarly, Screenshot should remember:

```text
Region
None delay
PNG
Save
```

The state should be stored in a small configuration file rather than hard-coded.

---

# 38. Settings vs Main UI

The main UI should remain simple.

Advanced settings should not be placed into the main capture workflow.

Possible settings page:

```text
General
├── Screenshot directory
├── Recording directory
├── Filename format
└── Notifications

Screenshot
├── Default format
├── Default output
└── Cursor

Recording
├── Default FPS
├── Default quality
├── Default format
├── Default audio
├── Cursor
└── Backend
```

The backend itself should preferably remain hidden unless debugging/advanced configuration is needed.

---

# 39. Technical Validation Plan

Before implementing the full AGS application, the following must be validated on the target machine.

## Phase 1 — Screenshot

Test:

```text
grim
slurp
wl-copy
```

Validate:

- region capture;
- monitor capture;
- focused window geometry;
- multiple monitors;
- HiDPI/scaling;
- negative monitor coordinates;
- clipboard;
- PNG;
- JPEG.

---

# 40. Phase 2 — Hyprland Target Resolution

Test Astal/Hyprland data:

```text
active client
client geometry
monitor geometry
monitor name
monitor scale
```

Validate:

- floating window;
- tiled window;
- maximized window;
- fullscreen window;
- XWayland window;
- multiple monitors;
- monitor positioned left/right/above;
- fractional scaling.

The goal is to ensure that "Window" and "Screen" capture use correct geometry.

---

# 41. Phase 3 — wf-recorder

Test:

```text
whole monitor
region
FPS
audio
hardware encoding
MP4
WebM
```

Then specifically test:

```text
start
stop
```

and determine whether pause/resume can be implemented cleanly.

If pause/resume is not suitable, wf-recorder remains a fallback backend but not the preferred backend.

---

# 42. Phase 4 — GPU Screen Recorder

Test:

```text
Wayland
region
monitor
portal
FPS
MP4
WebM
audio
GPU encoding
pause
resume
stop
```

Especially test:

```text
SIGUSR2
```

for pause/resume and verify that the resulting file remains valid. The current GPU Screen Recorder documentation explicitly defines SIGUSR2 as pause/unpause for normal recording.

Also test:

```text
window
```

through our Hyprland-geometry approach rather than relying on X11-only native window capture.

---

# 43. Phase 5 — GIF

Determine the best pipeline.

Potential architecture:

```text
capture frames/video
       ↓
FFmpeg conversion
       ↓
GIF
```

Test:

- 10 FPS;
- 15 FPS;
- 20 FPS;
- 30 FPS;
- 10-second recording;
- 30-second recording;
- large region;
- small region;
- file size;
- visual quality.

GIF should probably receive a maximum duration recommendation because GIF files become extremely large compared with video.

---

# 44. Phase 6 — Audio

Test:

```text
None
System
Microphone
System + microphone
```

The final implementation should use PipeWire/WirePlumber-compatible sources.

Verify:

- audio/video synchronization;
- microphone selection;
- system audio selection;
- unavailable device behavior;
- device changes during recording.

---

# 45. Phase 7 — Recording Controller

Build the actual process lifecycle:

```text
start
 ↓
recording
 ↓
pause
 ↓
paused
 ↓
resume
 ↓
recording
 ↓
stop
 ↓
finalizing
 ↓
completed
```

Test abnormal cases:

```text
recorder crashes
AGS crashes
Waybar restarts
user closes UI
Hyprland reloads
output directory disappears
disk becomes full
capture permission denied
```

The recorder should not silently leave stale state behind.

---

# 46. Phase 8 — Waybar Integration

Implement:

```text
custom/recording
```

with a JSON-returning state provider.

Waybar custom modules support JSON output containing fields such as:

```text
text
alt
tooltip
class
percentage
```

and support click handlers.

The module can therefore display:

```text
🔴 00:37
```

with:

```text
class = recording
```

and:

```text
⏸ 00:37
```

with:

```text
class = paused
```

This also allows the existing Waybar CSS to style the indicator.

---

# 47. Phase 9 — AGS UI

Only after the backend has been validated should the polished UI be implemented.

Components:

```text
CaptureWindow
├── ModeSelector
│   ├── Screenshot
│   └── Recording
│
├── ScreenshotView
│   ├── TargetSelector
│   ├── DelaySelector
│   ├── FormatSelector
│   ├── OutputSelector
│   └── CaptureButton
│
└── RecordingView
    ├── TargetSelector
    ├── FPSSelector
    ├── FormatSelector
    ├── AudioSelector
    ├── QualitySelector
    ├── DurationSelector
    └── RecordButton
```

---

# 48. Visual Behavior

The capture UI should:

- float above the desktop;
- be centered or positioned according to the desired shell behavior;
- use the same visual language as the rest of the user's AGS shell;
- close when capture starts;
- not interfere with the captured region;
- support keyboard navigation;
- allow Escape to cancel;
- clearly show the selected option;
- provide visual feedback while starting.

For Region capture, the UI must disappear before `slurp` begins.

---

# 49. Error Handling

Errors should be categorized.

## User cancellation

Example:

```text
slurp cancelled
```

No notification required.

## Permission error

Show:

```text
Screen capture permission denied.

Check Hyprland screencopy permissions.
```

## Backend unavailable

Example:

```text
GPU Screen Recorder is not installed.
```

## Encoder unavailable

Example:

```text
The selected format/codec is not available.
```

## Audio unavailable

Example:

```text
The selected audio source is unavailable.
```

## File error

Example:

```text
Could not save recording.
```

Detailed backend output should be logged.

---

# 50. Security Considerations

The application is capable of capturing the user's entire desktop.

Therefore:

- do not blindly execute arbitrary strings;
- do not construct shell commands from untrusted UI values;
- prefer argument arrays over shell strings;
- validate output paths;
- avoid `eval`;
- avoid interpolating arbitrary user-controlled values into `bash -c`.

Astal's process utilities explicitly execute commands without shell expansion by default, which is useful for this architecture.

Where a shell is genuinely necessary, invoke it explicitly and carefully.

---

# 51. What AGS Should Not Become

The project should not turn into:

```text
a complete video editor
```

or:

```text
a complete OBS replacement
```

It should remain a **capture controller**.

Its job is:

```text
choose target
choose settings
start capture
control capture
show status
```

not:

```text
edit video
mix audio
create scenes
stream
add overlays
```

---

# 52. Features Explicitly Out of Scope for Version 1

Do not implement initially:

- streaming;
- webcam overlay;
- scene management;
- video editing;
- annotation editor;
- codec expert settings;
- custom FFmpeg filter chains;
- instant replay;
- multi-source recording;
- webcam recording;
- automatic upload;
- cloud storage;
- OCR;
- AI processing.

These can be considered later.

---

# 53. Potential Future Features

Once the basic application is stable:

### Screenshot

- Satty integration;
- screenshot preview;
- annotation;
- screenshot history;
- copy + save;
- open file;
- delete screenshot.

### Recording

- instant replay;
- recording history;
- preview;
- open recording;
- delete recording;
- application-specific audio;
- cursor configuration;
- custom resolution;
- codec presets.

GPU Screen Recorder already exposes instant replay and application-audio functionality, making these plausible future extensions.

---

# 54. Existing Projects Investigated

The investigation found that this general concept already exists in the Hyprland ecosystem.

## HyprCapture

Hyprland's current documentation lists HyprCapture as a Hyprland-oriented screenshot and recording utility.

This validates the idea of combining screenshot and recording into a unified capture workflow.

## Other Hyprland capture projects

The ecosystem also contains projects combining:

- region capture;
- window capture;
- monitor capture;
- recording;
- GPU Screen Recorder;
- GIF/animated output.

These are useful reference implementations, but this project should remain independent so that the UI and controller are tailored to the user's shell.

---

# 55. Why Build This Instead of Using an Existing Tool?

The objective is not simply to reproduce `grim` or `wf-recorder`.

The value is the integration:

```text
Hyprland
+
AGS
+
Waybar
+
grim
+
slurp
+
recording backend
```

The resulting experience becomes:

```text
one consistent capture UI
```

with:

```text
Screenshot
    Region
    Screen
    Window

Recording
    Region
    Screen
    Window
```

and persistent recording control integrated into the existing desktop shell.

---

# 56. Final Proposed Architecture

```text
                         ┌───────────────────────┐
                         │         AGS           │
                         │                       │
                         │  Screenshot / Record  │
                         │       UI              │
                         └───────────┬───────────┘
                                     │
                                     ↓
                         ┌───────────────────────┐
                         │  Capture Controller   │
                         │                       │
                         │  state                │
                         │  lifecycle            │
                         │  configuration        │
                         └───────────┬───────────┘
                                     │
                       ┌─────────────┴─────────────┐
                       │                           │
                       ↓                           ↓
             ┌──────────────────┐       ┌──────────────────┐
             │ Screenshot       │       │ Recording        │
             │ Controller       │       │ Controller       │
             └────────┬─────────┘       └────────┬─────────┘
                      │                          │
                      ↓                          ↓
                ┌───────────┐             ┌──────────────┐
                │ grim      │             │ GPU Screen   │
                │ slurp     │             │ Recorder     │
                │ wl-copy   │             │ / wf-recorder│
                └───────────┘             └──────┬───────┘
                                                 │
                                      ┌──────────┴─────────┐
                                      │                    │
                                      ↓                    ↓
                                  Recording             State
                                  process                │
                                                         ↓
                                                   ┌──────────┐
                                                   │ Waybar   │
                                                   │ custom   │
                                                   │ module   │
                                                   └──────────┘
```

---

# 57. Final Technical Assessment

## Is it possible?

**Yes.**

The core components are already available and are designed for Wayland/Hyprland.

Hyprland officially documents:

- `grim` + `slurp` for screenshots;
- `wf-recorder` for recording;
- `wl-screenrec` as another recording option;
- OBS through PipeWire/portal.

AGS/Astal provides:

- GTK/Wayland desktop-shell UI;
- process management;
- Hyprland IPC integration;
- system integration libraries.

Waybar provides the required dynamic custom-module mechanism for a persistent recording indicator.

GPU Screen Recorder provides the particularly important recording controls:

```text
start
pause
resume
stop
```

with pause/resume explicitly exposed through SIGUSR2.

---

# 58. Remaining Technical Risks

There are no fundamental blockers, but these items must be experimentally validated:

### High priority

1. **Wayland window capture**
   - Resolve focused Hyprland window geometry.
   - Capture exactly that rectangle.
   - Test floating/tiled/fullscreen/XWayland windows.

2. **GPU Screen Recorder + Wayland**
   - Verify the desired capture modes on the target hardware.

3. **Pause/resume**
   - Verify SIGUSR2 behavior and resulting files.

4. **GIF**
   - Determine the best recording/conversion pipeline.

5. **Audio**
   - Verify system audio, microphone, and combinations.

6. **Hyprland screencopy permissions**
   - Determine the cleanest configuration for the chosen binaries.

### Medium priority

7. Fractional scaling.
8. Multi-monitor geometry.
9. Hardware encoder availability.
10. Failure/recovery behavior.
11. Waybar state synchronization.

---

# 59. Implementation Order

The project should be implemented in this order:

```text
1. Backend investigation
       ↓
2. Target-resolution prototype
       ↓
3. Screenshot backend
       ↓
4. Recording backend
       ↓
5. Pause/resume lifecycle
       ↓
6. Waybar recording indicator
       ↓
7. Capture controller
       ↓
8. AGS screenshot UI
       ↓
9. AGS recording UI
       ↓
10. Persistent configuration
       ↓
11. Error handling
       ↓
12. Polish / animations / styling
       ↓
13. Documentation
```

Do **not** begin by building the polished AGS interface.

The backend should be proven first.

---

# 60. First Prototype Milestone

The first real milestone should be extremely small:

```text
capture-test
```

It should prove:

```text
Region screenshot
Screen screenshot
Window screenshot

Region recording
Screen recording
Window recording

Pause recording
Resume recording
Stop recording
```

from the command line.

Only after those work reliably should AGS be introduced.

---

# 61. Definition of Done

Version 1 is complete when the user can:

### Screenshot

- open the AGS capture UI;
- select Screenshot;
- select Region / Screen / Window;
- select delay;
- select PNG/JPEG;
- select Clipboard/Save;
- capture successfully;
- receive useful feedback.

### Recording

- open the AGS capture UI;
- select Recording;
- select Region / Screen / Window;
- select FPS;
- select MP4/WebM/GIF;
- select audio;
- select quality;
- select duration;
- start recording;
- close the capture UI;
- see a recording indicator in Waybar;
- pause;
- resume;
- stop;
- receive useful feedback;
- obtain a valid output file.

### Reliability

The application must also correctly handle:

- cancelled region selection;
- denied capture permission;
- unavailable encoder;
- unavailable audio source;
- recorder crash;
- invalid output directory;
- Waybar restart;
- AGS restart;
- Hyprland reload;
- recording termination.

---

# 62. Current Decision Summary

| Area | Current decision |
|---|---|
| Desktop | Hyprland / Wayland |
| UI framework | AGS v3 / Astal |
| Bar | Existing Waybar |
| Screenshot | `grim` |
| Region selection | `slurp` |
| Clipboard | `wl-copy` |
| Screenshot modes | Region / Screen / Window |
| Screenshot formats | PNG / JPEG |
| Screenshot delay | None / 3s / 5s / 10s |
| Screenshot output | Clipboard / Save |
| Recording modes | Region / Screen / Window |
| Recording FPS | 24 / 30 / 60 |
| Recording formats | MP4 / WebM / GIF |
| Recording audio | None / System / Mic |
| Recording quality | Low / Medium / High |
| Recording duration | Infinite / 10s / 30s / 60s / Custom |
| Recording indicator | Waybar custom module |
| Recording control | Pause / Resume / Stop |
| Preferred recorder candidate | GPU Screen Recorder |
| Fallback recorder | wf-recorder |
| Window capture | Hyprland geometry-based |
| Backend selection | Must be experimentally validated |
| Advanced settings | Separate from main UI |
| Streaming | Out of scope |
| Video editing | Out of scope |
| Instant replay | Future feature |

---

# 63. Overall Conclusion

The project is technically feasible and has a coherent architecture.

The most important design decision is to separate the concepts:

```text
OPERATION
    Screenshot
    Recording

TARGET
    Region
    Screen
    Window
```

The AGS UI represents those concepts, while the actual capture is delegated to Wayland-native tools.

For screenshots, the technology is mature and straightforward:

```text
grim + slurp + wl-copy
```

For recording, the main investigation points toward **GPU Screen Recorder** because it combines Wayland support, GPU encoding, audio, multiple capture sources, multiple formats, and — crucially for this project — explicit pause/resume control.

The persistent recording indicator should preferably be implemented as a **Waybar custom module**, rather than trying to make AGS act as a traditional system-tray host/producer. Waybar already provides the exact dynamic custom-module functionality required.

The biggest remaining technical questions are therefore **not whether the project is possible**, but which exact recording backend configuration gives us the most reliable implementation of:

```text
Wayland
+
Region
+
Screen
+
Hyprland Window
+
FPS
+
MP4/WebM/GIF
+
Audio
+
Pause/Resume
+
Hardware encoding
```

Those should be resolved experimentally before the final implementation begins.

**Recommended next phase:** backend proof-of-concept first, followed by the AGS/Waybar implementation.