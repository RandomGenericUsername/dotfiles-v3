// Typed wrapper around `itr mapping …` for the editor GUI.
//
// The GUI shells out to the CLI (see design D5): Python owns YAML in both
// directions and the GUI stays a pure view. All functions raise ItrError on
// CLI failure with the stderr text attached.

import { execAsync } from "ags/process";

export type MappingOrigin = "vocabulary" | "group" | "variant";

export interface MappingEntry {
  placeholder: string;
  token: string;
  origin: MappingOrigin;
}

export interface VariantMappingView {
  variant: string;
  template_path: string;
  svg_body: string;
  mappings: MappingEntry[];
}

export interface GroupMappingView {
  group: string;
  variants: VariantMappingView[];
}

export interface MappingShow {
  groups: GroupMappingView[];
  palette: Record<string, string>;
  missing_tokens: string[];
  shadows: Record<string, string[]>;
}

export interface MappingSetResult {
  group: string;
  variant: string | null;
  placeholder: string;
  token: string;
  dry_run: boolean;
  diff: string;
}

export interface MappingSetDefaultResult {
  placeholder: string;
  token: string;
  dry_run: boolean;
  diff: string;
  shadows: string[];
}

export class ItrError extends Error {
  readonly argv: string[];
  constructor(argv: string[], message: string) {
    super(`itr ${argv.join(" ")} failed: ${message}`);
    this.name = "ItrError";
    this.argv = argv;
  }
}

async function runJson<T>(argv: string[]): Promise<T> {
  let stdout: string;
  try {
    stdout = await execAsync(["itr", "--output-format", "json", ...argv]);
  } catch (error) {
    throw new ItrError(argv, String(error));
  }
  try {
    return JSON.parse(stdout) as T;
  } catch (error) {
    throw new ItrError(argv, `unparseable output: ${String(error)}`);
  }
}

export interface ShowArgs {
  iconsYaml: string;
  icon?: string;
  templateDir?: string;
  colorScheme?: string;
}

export function mappingShow(args: ShowArgs): Promise<MappingShow> {
  const argv = ["mapping", "show", args.iconsYaml];
  if (args.icon !== undefined) argv.push("--icon", args.icon);
  if (args.templateDir !== undefined) argv.push("--template-dir", args.templateDir);
  if (args.colorScheme !== undefined) argv.push("--color-scheme", args.colorScheme);
  return runJson<MappingShow>(argv);
}

export interface SetArgs extends ShowArgs {
  placeholder: string;
  token: string;
  variant?: string;
  unsafe?: boolean;
  dryRun?: boolean;
  withDiff?: boolean;
}

function setArgv(command: "set" | "set-default", target: string, args: SetArgs): string[] {
  const argv = ["mapping", command, target, "--placeholder", args.placeholder, "--token", args.token];
  if (command === "set") {
    if (args.icon !== undefined) argv.push("--icon", args.icon);
    if (args.variant !== undefined) argv.push("--variant", args.variant);
  }
  if (args.unsafe === true) argv.push("--unsafe");
  if (args.dryRun === true) argv.push("--dry-run");
  if (args.withDiff === true) argv.push("--diff");
  if (args.templateDir !== undefined) argv.push("--template-dir", args.templateDir);
  if (args.colorScheme !== undefined) argv.push("--color-scheme", args.colorScheme);
  return argv;
}

export interface SetGroupArgs extends SetArgs {
  group: string;
}

export function mappingSet(args: SetGroupArgs): Promise<MappingSetResult> {
  return runJson<MappingSetResult>(setArgv("set", args.iconsYaml, { ...args, icon: args.group }));
}

export interface SetDefaultArgs extends SetArgs {
  iconsYaml?: string;
}

export function mappingSetDefault(args: SetDefaultArgs): Promise<MappingSetDefaultResult> {
  const argv = setArgv("set-default", args.iconsYaml, args);
  if (args.iconsYaml !== undefined) argv.push("--icons", args.iconsYaml);
  return runJson<MappingSetDefaultResult>(argv);
}
