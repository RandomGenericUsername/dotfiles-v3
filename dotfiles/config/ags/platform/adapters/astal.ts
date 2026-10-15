import { createState } from "ags"
import type { ReactiveRuntime, ReadAccessor, Setter } from "../ports/reactive"

/**
 * The AGS/gnim binding of the `ReactiveRuntime` port (spine AD-2).
 *
 * This is the ONLY place a domain read model's reactivity comes from the
 * framework. The read models themselves are pure and take this object as a
 * parameter, so the same code runs against a fake runtime in `make ags-test`.
 *
 * The setter is wrapped rather than passed through so the port stays the
 * narrowest thing the read models use (`(value: T) => void`); gnim's setter
 * also accepts a producer, which the read models never need.
 */
export const agsRuntime: ReactiveRuntime = {
  createState<T>(initial: T): [ReadAccessor<T>, Setter<T>] {
    const [get, set] = createState<T>(initial)
    return [get, (value: T) => set(value)]
  },
}
