/**
 * The reactive primitive a domain read model is built on, as an injectable port
 * (spine AD-2: injected context, no module globals).
 *
 * WHY THIS IS A PORT AND NOT AN `ags` IMPORT. A read model's whole job is to
 * turn a device subscription into a reactive accessor. If it imported
 * `createState` from `ags` directly, the module would need the desktop stack to
 * load and could never be exercised by `make ags-test` — the same reason
 * `PipeWireObservationAdapter` takes its service rather than calling
 * `Wp.get_default()` itself. With the primitive injected, a fake runtime drives
 * the real read-model logic under plain `node --test`, and the AGS binding
 * (`platform/adapters/astal.ts`) supplies gnim's `createState` in the app.
 *
 * PURE: no `ags`, no `gi://*`, no I/O.
 */

/**
 * The read side of a reactive cell, structurally — the subset of gnim's
 * `Accessor` a read model needs. gnim's `Accessor` is a `Function` subclass and
 * is assignable to this shape, so the real runtime satisfies it unchanged.
 */
export interface ReadAccessor<T> {
  (): T
  /** Read the current value without registering a reactive dependency. */
  peek(): T
}

/** The write side of a reactive cell. gnim's setter (which also accepts a producer) satisfies this. */
export type Setter<T> = (value: T) => void

/** The reactive runtime a read model is constructed against. */
export interface ReactiveRuntime {
  createState<T>(initial: T): [ReadAccessor<T>, Setter<T>]
}
