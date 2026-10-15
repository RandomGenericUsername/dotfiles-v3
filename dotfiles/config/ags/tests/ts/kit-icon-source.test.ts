import assert from "node:assert/strict"
import { test } from "node:test"
import {
  iconByStateKey,
  iconByVariant,
  resolveIconSource,
  type IconProvider,
  type IconRef,
} from "../../platform/ports/icon-source.ts"

/**
 * The one icon resolution chain (spine AD-7; doc 101 §7):
 *   provider table -> provider.resolve -> ref.fallback -> blank.
 *
 * These tests pin the chain's ORDER. The pure module has no GTK/AGS import, so
 * the whole decision is exercised here without the desktop stack.
 */

/** A provider with no table and no art: the bare-desktop case. */
const blankProvider: IconProvider = { resolve: () => null }

/** A provider with a state->variant table for `network` only. */
const tableProvider: IconProvider = {
  barMappings: (group) =>
    group === "network" ? { states: { "wifi-full": "wifi-full-default" } } : null,
  resolve: (group, variant) =>
    group === "network" && variant === "wifi-full-default"
      ? { kind: "file", path: "/icons/wifi-full.svg" }
      : null,
}

test("chain: the provider table wins and the fallback is not consulted", () => {
  let fallbackCalled = false
  const ref: IconRef<undefined> = {
    group: "network",
    variant: () => "wifi-full",
    fallback: (v) => {
      fallbackCalled = true
      return { kind: "name", name: v }
    },
  }

  assert.deepEqual(resolveIconSource(tableProvider, ref, undefined), {
    kind: "file",
    path: "/icons/wifi-full.svg",
  })
  assert.equal(fallbackCalled, false)
})

test("chain: a tableless ref degrades to ref.fallback", () => {
  const ref: IconRef<undefined> = {
    group: "btop",
    variant: () => "btop",
    fallback: (v) => ({ kind: "name", name: v }),
  }

  assert.deepEqual(resolveIconSource(blankProvider, ref, undefined), {
    kind: "name",
    name: "btop",
  })
})

test("chain: blank when neither provider nor fallback resolves", () => {
  const ref = iconByVariant("btop", () => "btop")
  assert.equal(resolveIconSource(blankProvider, ref, undefined), null)
})

test("chain: blank when the ref emits no variant (nothing to fall back to)", () => {
  const ref = iconByVariant("btop", () => "")
  assert.equal(resolveIconSource(tableProvider, ref, undefined), null)
})

test("chain: fallback is consulted when the table maps but resolve misses", () => {
  const provider: IconProvider = {
    barMappings: () => ({ states: { k: "missing" } }),
    resolve: () => null,
  }
  const ref: IconRef<undefined> = {
    group: "g",
    variant: () => "k",
    fallback: (v) => ({ kind: "name", name: v }),
  }

  assert.deepEqual(resolveIconSource(provider, ref, undefined), {
    kind: "name",
    name: "k",
  })
})

test("iconByStateKey emits the state key; iconByVariant emits the variant name", () => {
  assert.equal(iconByStateKey("network", () => "wifi-full").variant(undefined), "wifi-full")
  assert.equal(iconByVariant("btop", () => "btop").variant(undefined), "btop")
  assert.equal(iconByVariant("btop", () => "").variant(undefined), null)
})
