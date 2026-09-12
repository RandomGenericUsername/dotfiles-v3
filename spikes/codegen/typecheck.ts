// Compile-only consumer of the GENERATED TypeScript contract.
//
// `tsc --noEmit` proves the generated types are well-formed and usable:
//   - a valid HistoryLine type-checks
//   - the trigger switch is exhaustiveness-checked against the generated enum
//   - event constants are typed
// Delete a trigger from contract.json and this file fails to compile (the
// `never` assignment). Hand-edit generated/contract.ts and the drift check
// fails before tsc even runs.

import {
  HISTORY_TRIGGERS,
  EVENTS_INTERFACE,
  EVENTS_SIGNALS,
  type HistoryLine,
  type HistoryTrigger,
} from "./generated/contract";

const valid: HistoryLine = {
  ts: "2026-01-01T00:00:00Z",
  trigger: "seed",
  wallpaper: "a".repeat(64),
  palette: null,
  effects: null,
  icons: null,
  source_path: "/home/u/wall.png",
};

function describeTrigger(t: HistoryTrigger): string {
  switch (t) {
    case "seed":
    case "set":
    case "reconcile":
    case "force":
    case "regenerate":
    case "doctor":
    case "prune":
      return t;
    default: {
      const unreachable: never = t;
      return unreachable;
    }
  }
}

export const summary = {
  interface: EVENTS_INTERFACE,
  signals: Object.keys(EVENTS_SIGNALS),
  triggers: HISTORY_TRIGGERS,
  validTrigger: describeTrigger(valid.trigger),
};
