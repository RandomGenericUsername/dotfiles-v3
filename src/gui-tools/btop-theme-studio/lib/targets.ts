// Save targets: Repo | Installed (design D6, capability `btop-theme-studio`).
//
// No path selection: the user chooses a target, the resolved destination is
// shown read-only, and the diff/action follow the target. Repo is the
// repo-authoritative default deployed by bootstrap; Installed writes straight
// into the install spine and reloads btop live.

import type { Theme } from "./theme-model.ts";

export type SaveTarget = "repo" | "installed";

export interface TargetContext {
  /** Repo root (the checkout). */
  readonly repoRoot: string;
  /** Install spine root (`<install>`). */
  readonly installDir: string;
}

/** The authored-theme repo directory (shipped by provisioning). */
export const REPO_AUTHORED_DIR = "dotfiles/assets/btop-themes";
/** The repo-owned active-theme setting rendered into btop.conf. */
export const REPO_ACTIVE_THEME = "dotfiles/config/btop/active-theme";
/** The generated theme map (palette-linked base). */
export const REPO_GENERATED_MAP = "dotfiles/config/btop/theme-map.yaml";

/** The install-spine themes directory btop scans. */
export const SPINE_THEMES_DIR = "config/btop/themes";

/**
 * The resolved destination for a theme + target, shown read-only in the UI.
 *
 * A generated theme is a palette-linked, runtime-owned pointer; its repo form
 * is the theme MAP, not a `.theme` file, and its installed form is the
 * `colors.btop.theme` pointer.
 */
export function resolvedPath(theme: Theme, target: SaveTarget, ctx: TargetContext): string {
  const generated = theme.kind === "generated";
  if (target === "repo") {
    return generated
      ? `${ctx.repoRoot}/${REPO_GENERATED_MAP}`
      : `${ctx.repoRoot}/${REPO_AUTHORED_DIR}/${theme.name}.theme`;
  }
  const spine = `${ctx.installDir}/${SPINE_THEMES_DIR}`;
  return generated ? `${spine}/colors.btop.theme (pointer)` : `${spine}/${theme.name}.theme`;
}

/** The save button label for a target. */
export function actionLabel(target: SaveTarget): string {
  return target === "repo" ? "Save to repo" : "Save to installed";
}

/** The hint under the target toggle. */
export function targetHint(target: SaveTarget): string {
  return target === "repo"
    ? "Repo edit → deployed by bootstrap (provision) on the next run. Reproducible; not instantly live."
    : "Installed edit → written straight to the spine and reloaded live (SIGUSR2). Drifts from the repo.";
}

/**
 * The divergence caveat for the Installed target (spec: repo edits will not
 * propagate to a machine-owned installed theme).
 */
export function divergenceCaveat(target: SaveTarget): string | null {
  return target === "installed"
    ? "This goes straight to the install spine and drifts from the repo — repo edits will not propagate to this machine-owned theme."
    : null;
}

/**
 * The generated theme is a derived pointer; Installed is discouraged (design
 * risk: recommend repo-only for generated and warn on Installed).
 */
export function generatedInstalledWarning(theme: Theme, target: SaveTarget): string | null {
  return theme.kind === "generated" && target === "installed"
    ? "colors.btop is a palette-linked pointer re-derived on every wallpaper set — fork it before saving, or save to the repo."
    : null;
}

/** True when the theme must be forked before it can be edited/installed. */
export function mustFork(theme: Theme): boolean {
  return theme.kind === "generated";
}
