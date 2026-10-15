/**
 * The surface contract (spine AD-10; doc 101 §4.4).
 *
 * A surface is a piece of content plus the few facts a host needs to place it.
 * The load-bearing rule is the MOUNT POLICY (doc 101 §4.4, Option B): a surface
 * body is a **factory**, and a host mounts it **only while visible** and tears it
 * down when hidden. Because the overlay coordinator allows one overlay at a time,
 * at most one body is live — the shared-state races that bit the Wi-Fi/Bluetooth
 * panels become structurally impossible, and durable state must live in an
 * app-level service rather than in the component.
 *
 * This module is PURE: no `gi://`, no `ags`, no JSX runtime. The rendered subtree
 * is the type parameter `E` (default `unknown`), the same device `kit/shapes.ts`
 * uses, so the contract and the mount policy are unit-testable on a stock runner
 * with no desktop stack. `kit/popup-host.tsx` specializes `E` to gnim's
 * `JSX.Element`.
 */

/**
 * The reactive read a body or a spec needs. gnim's `Accessor` is a `Function`
 * subclass and is assignable to this shape, so the real runtime satisfies it
 * unchanged (same structural trick as `platform/ports/reactive.ts`).
 */
export type SurfaceAccessor<T> = () => T

/**
 * What a surface body factory receives. Doc 101 §4.4 also carries the full
 * `BarContext` here (`ctx`); that is minted in the platform-extraction step
 * (AD-20 step 8), so today the factory receives only the reactive visibility it
 * needs to stay honest about the mount policy.
 *
 * `A` is the accessor type. It defaults to the structural `SurfaceAccessor` so
 * this module stays pure; the app specializes it to gnim's concrete `Accessor`
 * (`PopupSurfaceSpec` in `kit/popup-host.tsx`) so a body can hand `visible`
 * straight to content components that declare gnim accessors.
 */
export interface SurfaceHostContext<A = SurfaceAccessor<boolean>> {
  /** True while the surface is mounted; the body reads it, never stores it. */
  readonly visible: A
}

/**
 * A surface declaration. `body` is a FACTORY (AD-10) — a host calls it to build
 * the body and drops the result when hidden. `width`/`height` are placement
 * hints the host may use; `keyboard` is true while the body needs TYPED input,
 * so the host can flip the window keymode (doc 101 §4.4).
 */
export interface SurfaceSpec<E = unknown, A = SurfaceAccessor<boolean>> {
  readonly id: string
  body(host: SurfaceHostContext<A>): E
  readonly width?: number
  readonly height?: number
  /** True while the body needs typed input; the host flips keymode. */
  readonly keyboard?: A
}

/** A lookup of the surfaces an app ships (doc 101 §4.7 `BarContext.surfaces`). */
export interface SurfaceRegistry<E = unknown> {
  get(id: string): SurfaceSpec<E> | undefined
  all(): readonly SurfaceSpec<E>[]
}

/**
 * Build a registry from a fixed set of specs. Later duplicates of an `id` win,
 * mirroring `Map` semantics, so a composition root can register defaults and
 * override one by appending.
 */
export function createSurfaceRegistry<E>(
  specs: readonly SurfaceSpec<E>[] = [],
): SurfaceRegistry<E> {
  const byId = new Map<string, SurfaceSpec<E>>()
  for (const spec of specs) byId.set(spec.id, spec)
  return {
    get: (id) => byId.get(id),
    all: () => [...byId.values()],
  }
}

/**
 * The pure mount policy (AD-10): the body exists **only** while visible.
 *
 * `render(visible)` is the whole decision. On the hidden→visible edge it calls
 * the factory once; while visible it returns the SAME instance (no rebuild on an
 * unrelated re-render); on the visible→hidden edge it drops the instance and runs
 * `teardown`, so no body outlives its surface. A host drives this from its
 * visibility accessor and hands the result to the renderer (gnim `With`), which
 * owns the GTK side.
 */
export interface SurfaceMount<E> {
  /** True while a body instance is live. */
  readonly isMounted: () => boolean
  /** The body while visible, or null while hidden. Idempotent per state. */
  render(visible: boolean): E | null
}

export function createSurfaceMount<E>(
  build: () => E,
  teardown?: (body: E) => void,
): SurfaceMount<E> {
  let body: E | null = null
  return {
    isMounted: () => body !== null,
    render(visible: boolean): E | null {
      if (!visible) {
        if (body !== null) {
          const gone = body
          body = null
          teardown?.(gone)
        }
        return null
      }
      if (body === null) body = build()
      return body
    },
  }
}
