// Input resolution for the editor session.
//
// The authoring model is REPO-AUTHORITATIVE (reverted from the brief
// seed-once experiment, 2026-09-07): the editor targets the repo manifest
// whenever a checkout is detectable — via ICME_REPO_ROOT (set by the
// provisioned launcher) or a working-directory ancestor walk — bootstrap
// then propagates repo edits to the spine on every run ("edit repo,
// bootstrap, deployed"). Machines without a checkout fall back to the
// seeded spine copy:
//   - manifest:   <repo>/dotfiles/config/icon-template-color-scheme-mappings/icons.yaml
//                 or ~/.local/share/dotfiles/icon-mappings/icons.yaml
//   - templates:  <repo>/dotfiles/assets/icon-templates/ or spine
//   - scheme:     the generated palette (always machine-local)
// ICME_* environment overrides and the in-app pickers take precedence.

import GLib from "gi://GLib?version=2.0";
import Gio from "gi://Gio?version=2.0";

export interface EditorInputs {
  templateRoot: string;
  iconsYaml: string;
  colorScheme: string;
}

const MANIFEST_PROBE =
  "dotfiles/config/icon-template-color-scheme-mappings/icons.yaml";

function spineHome(): string {
  return `${GLib.get_user_data_dir()}/dotfiles`;
}

/**
 * Color-scheme resolution: the runtime-owned current palette first, the
 * provisioned generated seed as fallback.
 *
 * The runtime reconciler repoints <state>/dotfiles/current/colors.yaml on
 * every wallpaper set (via the color-scheme generator), and the whole
 * desktop consumes that pointer — so the editor previews against the LIVE
 * scheme. Before the runtime ever runs (or if the pointer dangles), fall
 * back to the bootstrap-rendered generated/palettes/colors.yaml seed,
 * which the verify role accepts as the pre-runtime palette location.
 */
function resolveColorScheme(): string {
  const override = GLib.getenv("ICME_COLOR_SCHEME");
  if (override) return override;
  const current = `${GLib.get_user_state_dir()}/dotfiles/current/colors.yaml`;
  if (GLib.file_test(current, GLib.FileTest.EXISTS)) return current;
  return `${spineHome()}/generated/palettes/colors.yaml`;
}

/** True when a path lives under the install spine (not a repo checkout). */
export function isSpinePath(path: string): boolean {
  return path === spineHome() || path.startsWith(`${spineHome()}/`);
}

function findRepoRoot(): string | null {
  // Explicit checkout from the provisioned launcher wins: `ags run -d`
  // re-roots the app process into the app dir, so the cwd walk below can
  // never find a checkout on its own.
  const hinted = GLib.getenv("ICME_REPO_ROOT");
  if (
    hinted &&
    GLib.file_test(`${hinted}/${MANIFEST_PROBE}`, GLib.FileTest.EXISTS)
  ) {
    return hinted;
  }
  let dir = GLib.get_current_dir();
  for (;;) {
    if (GLib.file_test(`${dir}/${MANIFEST_PROBE}`, GLib.FileTest.EXISTS)) return dir;
    const parent = GLib.path_get_dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
}

export function resolveInputs(): EditorInputs {
  const repoRoot = findRepoRoot();
  if (repoRoot) {
    return {
      templateRoot:
        GLib.getenv("ICME_TEMPLATE_ROOT") ?? `${repoRoot}/dotfiles/assets/icon-templates`,
      iconsYaml:
        GLib.getenv("ICME_ICONS_YAML") ??
        `${repoRoot}/${MANIFEST_PROBE}`,
      colorScheme: resolveColorScheme(),
    };
  }
  return {
    templateRoot: GLib.getenv("ICME_TEMPLATE_ROOT") ?? `${spineHome()}/icon-templates`,
    iconsYaml: GLib.getenv("ICME_ICONS_YAML") ?? `${spineHome()}/icon-mappings/icons.yaml`,
    colorScheme: resolveColorScheme(),
  };
}

/** Vocabulary file resolved alongside the manifest (mirrors the CLI). */
export function defaultsPathFor(iconsYaml: string): string {
  return `${GLib.path_get_dirname(iconsYaml)}/defaults.yaml`;
}

/** mtime seconds of a file, or null when it cannot be read. */
export function mtimeOf(path: string): number | null {
  try {
    const info = Gio.File.new_for_path(path).query_info(
      "time::modified",
      Gio.FileQueryInfoFlags.NONE,
      null,
    );
    return info.get_modification_date_time()?.to_unix() ?? null;
  } catch {
    return null;
  }
}
