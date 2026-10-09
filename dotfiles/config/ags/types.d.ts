/**
 * Ambient module declarations for non-TypeScript imports in the AGS layer.
 *
 * `ags bundle` resolves `./style.css` through its own CSS loader, so TypeScript
 * never sees it. Without this declaration `tsc` reports TS2307 on app.tsx's
 * `import style from "./style.css"` -- a false positive that would otherwise
 * have to sit in the typecheck baseline forever.
 *
 * Keep this minimal: every entry must be an import TypeScript cannot resolve on
 * its own. If a `.ts`/`.tsx` module ever lands here, it is shadowing a real
 * file and losing its types.
 */

declare module "*.css" {
  const css: string;
  export default css;
}