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
  /**
   * Non-null when the runtime palette is missing: previews built on
   * colorScheme will fail downstream, so the UI must show this instead of
   * silently falling back to the orphaned generated/ seed (Epic 4 removed
   * that tree — the runtime is the sole palette producer).
   */
  colorSchemeWarning: string | null;
}

const MANIFEST_PROBE =
  "dotfiles/config/icon-template-color-scheme-mappings/icons.yaml";

function spineHome(): string {
  return `${GLib.get_user_data_dir()}/dotfiles`;
}

/**
 * Color-scheme resolution: the runtime-owned current palette, no fallback.
 *
 * The runtime reconciler repoints <state>/dotfiles/current/colors.yaml on
 * every wallpaper set (via the color-scheme generator), and the whole
 * desktop consumes that pointer — so the editor previews against the LIVE
 * scheme. There is deliberately no generated/ fallback: Epic 4 removed that
 * tree and the runtime is its sole producer. When the pointer is missing
 * (runtime never ran), callers get the path anyway plus a warning carrying
 * the recovery command; downstream itr failures then surface next to it.
 */
const MISSING_SCHEME_HINT =
  "Runtime palette not found — run `dotfiles-runtime wallpaper set <wallpaper>` or re-bootstrap; previews are unavailable until it exists.";

function resolveColorScheme(): { path: string; warning: string | null } {
  const override = GLib.getenv("ICME_COLOR_SCHEME");
  if (override) return { path: override, warning: null };
  const current = `${GLib.get_user_state_dir()}/dotfiles/current/colors.yaml`;
  if (GLib.file_test(current, GLib.FileTest.EXISTS)) return { path: current, warning: null };
  return { path: current, warning: MISSING_SCHEME_HINT };
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
  const scheme = resolveColorScheme();
  if (repoRoot) {
    return {
      templateRoot:
        GLib.getenv("ICME_TEMPLATE_ROOT") ?? `${repoRoot}/dotfiles/assets/icon-templates`,
      iconsYaml:
        GLib.getenv("ICME_ICONS_YAML") ??
        `${repoRoot}/${MANIFEST_PROBE}`,
      colorScheme: scheme.path,
      colorSchemeWarning: scheme.warning,
    };
  }
  return {
    templateRoot: GLib.getenv("ICME_TEMPLATE_ROOT") ?? `${spineHome()}/icon-templates`,
    iconsYaml: GLib.getenv("ICME_ICONS_YAML") ?? `${spineHome()}/icon-mappings/icons.yaml`,
    colorScheme: scheme.path,
    colorSchemeWarning: scheme.warning,
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

/**
 * Change fingerprint for the color-scheme pointer: symlink target + mtime.
 * The runtime repoints current/colors.yaml on every wallpaper set — often at
 * a cached entry whose mtime predates the switch — so mtime alone misses
 * repoints back to an older scheme. Null when unreadable.
 */
export function schemeFingerprint(colorSchemePath: string): string | null {
  try {
    const target = GLib.file_read_link(colorSchemePath) ?? colorSchemePath;
    const mtime = mtimeOf(colorSchemePath);
    if (mtime === null) return null;
    return `${target}@${mtime}`;
  } catch {
    return null;
  }
}
