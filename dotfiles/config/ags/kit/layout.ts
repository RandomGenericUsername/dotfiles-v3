/**
 * The layout vocabulary (spine AD-9; doc 101 §4.3).
 *
 * Layout is PLACEMENT, not looks. A provider returns a whole `BarLayout` or
 * null — there is no partial merge, because a merge would make "which widget is
 * where" depend on which providers happened to answer. The resolution chain is
 * **user › runtime › repo-default**, the first non-null provider wins, and the
 * repo default is always non-null (AD-18: the bar runs with nothing external).
 *
 * A `BarLayout` carries NO version field of its own (AD-9): it is versioned by
 * the artifact's `schemaVersion` (AD-16), so there is one versioning scheme, not
 * two. Doc 101 §4.3's `version: 1` is deliberately dropped here.
 *
 * This module is PURE: no GTK, no AGS, no JSX. That is what lets the chain and
 * the repo default be unit-tested on a stock runner.
 */

/** One placed widget: its stable id, plus any declared params. */
export interface BarEntry {
  readonly id: string
  readonly params?: Readonly<Record<string, unknown>>
}

/** A whole bar layout, by section. Absent sections render nothing. */
export interface BarLayout {
  readonly sections: {
    readonly start?: readonly BarEntry[]
    readonly center?: readonly BarEntry[]
    readonly end?: readonly BarEntry[]
  }
}

/** A source of a whole layout, or null when it has none to offer. */
export interface LayoutProvider {
  load(): BarLayout | null
}

/**
 * Resolve the layout chain (AD-9). `providers` are the higher-priority sources
 * in order (user, then runtime); `repoDefault` is the always-non-null floor.
 * The first non-null layout wins. If even the repo default returned null (it
 * must not), an empty layout is returned so a caller always has something to
 * render — the bar never fails to place its widgets.
 */
export function resolveLayout(
  providers: readonly LayoutProvider[],
  repoDefault: LayoutProvider,
): BarLayout {
  for (const provider of providers) {
    const layout = provider.load()
    if (layout) return layout
  }
  return repoDefault.load() ?? { sections: {} }
}
