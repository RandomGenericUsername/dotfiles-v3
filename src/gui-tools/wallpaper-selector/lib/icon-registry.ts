// Selector icon resolver — consumes the SAME rendered-icon pipeline as the
// bar and hypr-pano.
//
// Templates live in the repo (`dotfiles/assets/icon-templates/`), are mapped
// in `icon-mappings/icons.yaml`, rendered by ITR into
// `$XDG_STATE_HOME/dotfiles/current/icons/`, and advertised through the AGS
// manifest (`~/.config/ags/icons.json`, generated from icons.yaml). This
// module resolves a `(group, variant)` to an on-disk SVG path exactly like the
// bar's `lib/icon-registry.ts`, so a palette change restyles these too.

import GLib from "gi://GLib?version=2.0";

interface Variant {
  name: string;
  output: string;
}

interface IconGroup {
  variants: Variant[];
}

type IconManifest = Record<string, IconGroup>;

const RUNTIME_ICONS_DIR = `${
  GLib.getenv("XDG_STATE_HOME") || `${GLib.get_home_dir()}/.local/state`
}/dotfiles/current/icons`;

// The bar owns the shared manifest (compositor_configs renders icons.yaml to
// <spine>/config/ags/icons.json, exposed at ~/.config/ags). The selector reads
// it cross-config; a missing/stale manifest just yields no icon, never a crash.
const MANIFEST_PATH = `${GLib.get_user_config_dir()}/ags/icons.json`;

let manifest: IconManifest | null = null;

function loadManifest(): IconManifest {
  if (manifest !== null) return manifest;
  try {
    const [ok, bytes] = GLib.file_get_contents(MANIFEST_PATH);
    manifest =
      ok && bytes !== null
        ? (JSON.parse(new TextDecoder().decode(bytes)) as IconManifest)
        : {};
  } catch (error) {
    console.error(`wallpaper-selector: cannot read icon manifest: ${error}`);
    manifest = {};
  }
  return manifest;
}

/** Force a manifest re-read (after provisioning regenerates icons.json). */
export function reloadIconManifest(): void {
  manifest = null;
}

/** Absolute path to the rendered SVG for `group`/`variant`, or null. */
export function resolveIcon(group: string, variant: string): string | null {
  const groupData = loadManifest()[group];
  if (groupData === undefined) return null;
  const entry = groupData.variants?.find((candidate) => candidate.name === variant);
  if (entry === undefined) return null;
  const path = `${RUNTIME_ICONS_DIR}/${entry.output}`;
  return GLib.file_test(path, GLib.FileTest.EXISTS) ? path : null;
}
