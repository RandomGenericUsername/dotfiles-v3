// ---------------------------------------------------------------------------
// PORT: report which recorder backend the tool would auto-select
// (design.md §2, task 5.4).
//
// Reached through `capture-tool backend`, which prints one JSON object. The
// shape is deliberately opaque here — the settings page only ever renders it,
// so widening the type to a parsed object would be a promise neither layer can
// keep. The `?? "none"` fallback and the JSON parse belong to
// `adapters/exec-backend-probe.ts`.
//
// Interface only — no concrete implementation, no `ags/*`, no `gi://*
// (gate check 1, and the spec requirement "Ports SHALL declare no concrete
// implementation").
// ---------------------------------------------------------------------------

export interface BackendProbe {
  /**
   * The auto-selected backend's name, or `"none"` when the probe failed or
   * the CLI reported nothing. Never rejects: an unavailable backend is a
   * readout state, not an error the view must handle.
   */
  backend(): Promise<string>
}