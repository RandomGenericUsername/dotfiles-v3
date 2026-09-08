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

export interface TemplateShape {
  id: number;
  tag: string;
  paint_attr: "fill" | "stroke";
  placeholder: string | null;
  literal: string | null;
}

export interface TemplateAnalyzeResult {
  path: string;
  mode: "templated" | "bare";
  shapes: TemplateShape[];
}

export interface TemplateScanEntry {
  path: string;
  mode: "templated" | "bare";
}

export function templateScan(root: string): Promise<TemplateScanEntry[]> {
  return runJson<{ templates: TemplateScanEntry[] }>(["template", "scan", root]).then(
    (payload) => payload.templates,
  );
}

export interface RegisterResult {
  group: string;
  variant: string;
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

export interface SetArgs {
  placeholder: string;
  token: string;
  unsafe?: boolean;
  dryRun?: boolean;
  withDiff?: boolean;
  templateDir?: string;
  colorScheme?: string;
}

function setArgv(command: "set" | "set-default", target: string, args: SetArgs): string[] {
  const argv = ["mapping", command, target, "--placeholder", args.placeholder, "--token", args.token];
  if (args.unsafe === true) argv.push("--unsafe");
  if (args.dryRun === true) argv.push("--dry-run");
  if (args.withDiff === true) argv.push("--diff");
  if (args.templateDir !== undefined) argv.push("--template-dir", args.templateDir);
  if (args.colorScheme !== undefined) argv.push("--color-scheme", args.colorScheme);
  return argv;
}

export interface SetGroupArgs extends SetArgs {
  iconsYaml: string;
  group: string;
  variant?: string;
}

export function mappingSet(args: SetGroupArgs): Promise<MappingSetResult> {
  const argv = setArgv("set", args.iconsYaml, args);
  argv.push("--icon", args.group);
  if (args.variant !== undefined) argv.push("--variant", args.variant);
  return runJson<MappingSetResult>(argv);
}

export interface SetDefaultArgs extends SetArgs {
  defaultsYaml: string;
  manifestYaml?: string;
}

export function mappingSetDefault(args: SetDefaultArgs): Promise<MappingSetDefaultResult> {
  const argv = setArgv("set-default", args.defaultsYaml, args);
  if (args.manifestYaml !== undefined) argv.push("--icons", args.manifestYaml);
  return runJson<MappingSetDefaultResult>(argv);
}

export function templateAnalyze(path: string): Promise<TemplateAnalyzeResult> {
  return runJson<TemplateAnalyzeResult>(["template", "analyze", path]);
}

export function templateSetPlaceholder(
  path: string,
  shapeId: number,
  name: string,
): Promise<TemplateAnalyzeResult> {
  return runJson<TemplateAnalyzeResult>([
    "template",
    "set-placeholder",
    path,
    "--shape",
    String(shapeId),
    "--name",
    name,
  ]);
}

export interface RegisterArgs {
  manifestYaml: string;
  group: string;
  variant: string;
  template: string;
  output: string;
}

export function manifestRegister(args: RegisterArgs): Promise<RegisterResult> {
  return runJson<RegisterResult>([
    "mapping",
    "register",
    args.manifestYaml,
    "--group",
    args.group,
    "--variant",
    args.variant,
    "--template",
    args.template,
    "--output",
    args.output,
  ]);
}
