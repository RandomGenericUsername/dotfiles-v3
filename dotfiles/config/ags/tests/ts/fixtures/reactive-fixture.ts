import type { ReadAccessor, ReactiveRuntime, Setter } from "../../../domains/reactive.ts"

/**
 * A minimal, PURE `ReactiveRuntime` for the domain-read-model suites.
 *
 * The read models take their reactive primitive as a parameter (spine AD-2), so
 * this fake is what lets `make ags-test` prove each one is reactive without the
 * desktop stack: the real runtime is gnim's `createState`, which needs GObject.
 * The fake is deliberately the smallest thing that behaves like a signal — a
 * cell plus a setter — because the suites test the read models, not gnim.
 */
export function fakeRuntime(): ReactiveRuntime {
  return {
    createState<T>(initial: T): [ReadAccessor<T>, Setter<T>] {
      let value = initial
      const get = Object.assign(() => value, { peek: () => value })
      const set: Setter<T> = (next) => {
        value = next
      }
      return [get, set]
    },
  }
}

/**
 * A fake GObject-style emitter: the `connect`/`disconnect`/`emit` surface an
 * Astal service exposes, minus the runtime. `emit(signal)` fires exactly the
 * handlers registered for that signal, so a suite can prove a read model
 * republishes on the property change a real device would announce.
 */
export interface Emitter {
  connect(signal: string, callback: () => void): number
  disconnect(handler: number): void
  emit(signal: string): void
}

export function makeEmitter(): Emitter {
  const handlers = new Map<number, { signal: string; callback: () => void }>()
  let nextId = 1
  return {
    connect(signal, callback) {
      const id = nextId++
      handlers.set(id, { signal, callback })
      return id
    },
    disconnect(handler) {
      handlers.delete(handler)
    },
    emit(signal) {
      // Copy first: a handler could (in principle) disconnect while firing.
      for (const entry of [...handlers.values()]) {
        if (entry.signal === signal) entry.callback()
      }
    },
  }
}
