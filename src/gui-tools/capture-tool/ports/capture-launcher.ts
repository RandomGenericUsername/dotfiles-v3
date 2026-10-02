// ---------------------------------------------------------------------------
// PORT: spawn the capture backend (design.md §2, task 5.3).
//
// The port takes argv, NOT a request. Translating a request into argv is
// pure and belongs to `domain/cli-args.ts` (A6); spawning is I/O and belongs
// to `adapters/exec-capture-launcher.ts`. Handing the port a request instead
// would put the argv vocabulary behind the process boundary, which is exactly
// the coupling this seam removes.
//
// The hide-then-wait-150ms sequence is part of the CONTRACT and lives in the
// adapter, not here: "the window must be off screen before the backend reads
// the display" is a fact about the compositor, not about a view, so a second
// layout gets it for free rather than re-deriving (possibly wrongly) the
// delay.
//
// Interface only — no concrete implementation, no `ags/*`, no `gi://*
// (gate check 1, and the spec requirement "Ports SHALL declare no concrete
// implementation").
// ---------------------------------------------------------------------------

export interface CaptureLauncher {
  /** Launch the capture backend with `argv` (argv[0] is the program). */
  launch(argv: string[]): void
}