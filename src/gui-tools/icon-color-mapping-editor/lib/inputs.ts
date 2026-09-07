// Input resolution for the editor session.
//
// The editor is a provisioned app: it edits the DEPLOYED artifacts in the
// spine (~/.local/share/dotfiles/), never a repo checkout. Defaults:
//   - manifest:   ~/.local/share/dotfiles/icon-mappings/icons.yaml (writable;
//                 defaults.yaml is resolved alongside it by the CLI)
//   - templates:  ~/.local/share/dotfiles/icon-templates/ (read-only)
//   - scheme:     generated palette (read-only)
// ICME_* environment overrides and the in-app pickers take precedence.
// Provisioning seeds the manifest once (first run); afterwards the machine
// owns it — re-bootstrap never overwrites edits.

import GLib from "gi://GLib?version=2.0";
import Gio from "gi://Gio?version=2.0";

export interface EditorInputs {
  templateRoot: string;
  iconsYaml: string;
  colorScheme: string;
}

function spineHome(): string {
  const dataHome = GLib.get_user_data_dir();
  return `${dataHome}/dotfiles`;
}

export function resolveInputs(): EditorInputs {
  return {
    templateRoot: GLib.getenv("ICME_TEMPLATE_ROOT") ?? `${spineHome()}/icon-templates`,
    iconsYaml: GLib.getenv("ICME_ICONS_YAML") ?? `${spineHome()}/icon-mappings/icons.yaml`,
    colorScheme:
      GLib.getenv("ICME_COLOR_SCHEME") ?? `${spineHome()}/generated/palettes/colors.yaml`,
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
