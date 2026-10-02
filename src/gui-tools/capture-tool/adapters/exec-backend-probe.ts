// ---------------------------------------------------------------------------
// ADAPTER: `execAsync(["capture-tool","backend"])` probe (design.md §3.4,
// task 5.8).
//
// The only place the capture tool asks the CLI which recorder it would
// auto-select, and the only place that parses the answer.
//
// `?? "none"` covers BOTH "the JSON had no `backend` key" and "the output was
// not JSON at all" (the try/catch). The promise NEVER rejects: the settings
// page renders the result, and an unavailable backend is a readout state
// ("Automatic (unavailable)"), not an error the view must handle. The argv
// array here is deliberately minimal and carries none of the capture-action
// vocabulary — that belongs to the request->argv translator A6 will add.
// ---------------------------------------------------------------------------

import { execAsync } from "ags/process"
import type { BackendProbe } from "../ports/backend-probe"

/** The composition root's `BackendProbe`. */
export function execBackendProbe(): BackendProbe {
  return {
    backend(): Promise<string> {
      return execAsync(["capture-tool", "backend"])
        .then((out) => {
          let name = "none"
          try {
            name = (JSON.parse(out) as { backend?: string }).backend ?? "none"
          } catch {
            name = "none"
          }
          return name
        })
        .catch(() => "none")
    },
  }
}