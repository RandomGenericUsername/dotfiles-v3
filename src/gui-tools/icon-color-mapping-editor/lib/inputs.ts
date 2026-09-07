// Input resolution for the editor session.
//
// Precedence per input: ICME_* environment override, then the checked-out
// repository layout relative to the launch directory, except the color
// scheme, whose default is the provisioned generated copy. Failures to read
// any input surface as ItrError through lib/itr.ts at load time.

import GLib from "gi://GLib?version=2.0";
import Gio from "gi://Gio?version=2.0";

export interface EditorInputs {
  templateRoot: string;
  iconsYaml: string;
  colorScheme: string;
}

export function resolveInputs(): EditorInputs {
  const cwd = GLib.get_current_dir();
  return {
    templateRoot:
      GLib.getenv("ICME_TEMPLATE_ROOT") ?? `${cwd}/../../../dotfiles/assets/icon-templates`,
    iconsYaml:
      GLib.getenv("ICME_ICONS_YAML") ??
      `${cwd}/../../../dotfiles/config/icon-template-color-scheme-mappings/icons.yaml`,
    colorScheme:
      GLib.getenv("ICME_COLOR_SCHEME") ??
      `${GLib.get_user_data_dir()}/dotfiles/generated/palettes/colors.yaml`,
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
