# Capture tool skeleton

This directory is the starting point for the Hyprland screenshot/recording UI and controller layer.

## Current intent

- AGS owns the desktop UI and state wiring.
- The capture logic stays behind a controller layer rather than being executed directly from widgets.
- The recording backend should be selected behind an abstraction so `gpu-screen-recorder` or `wf-recorder` can be swapped without redesigning the UI.

## Planned layout

```text
capture/
├── CaptureWindow.tsx
├── ScreenshotView.tsx
├── RecordingView.tsx
├── controllers/
│   ├── CaptureController.ts
│   ├── ScreenshotController.ts
│   ├── RecordingController.ts
│   └── TargetResolver.ts
├── types.ts
└── README.md
```

## Dependency notes

The provisioning manifest already includes core screenshot utilities (`grim`, `slurp`, `wl-clipboard`).
The recording setup also requires media/audio dependencies and a recorder backend, which are now added to `dotfiles/provisioning/packages.yaml`.

## Primary architecture

```text
AGS UI
  ↓
CaptureController
  ├── ScreenshotController
  ├── RecordingController
  └── TargetResolver
  ↓
Backend (grim / slurp / gpu-screen-recorder / wf-recorder)
```

This keeps the UI free of shell commands and makes the recorder lifecycle testable.
