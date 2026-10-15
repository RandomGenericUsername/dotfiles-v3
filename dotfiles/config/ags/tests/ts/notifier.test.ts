import { describe, it } from "node:test"
import assert from "node:assert/strict"

import {
  createNotifier,
  isCardIntent,
  type NotificationIntent,
  type NotifierSinks,
} from "../../platform/ports/notifier.ts"

/**
 * The `Notifier` port (spine AD-11), driven by fake sinks that capture intents.
 * These prove the route the provider exists for: a transient intent goes to the
 * freedesktop wire; a keyed or progress intent goes to the event-card path; and
 * the sender never chooses.
 */

function fakeSinks() {
  const notified: NotificationIntent[] = []
  const carded: NotificationIntent[] = []
  const dismissed: string[] = []
  const sinks: NotifierSinks = {
    notify: (intent) => notified.push(intent),
    card: (intent) => carded.push(intent),
    dismiss: (key) => dismissed.push(key),
  }
  return { sinks, notified, carded, dismissed }
}

describe("notifier port", () => {
  it("routes a transient intent to freedesktop", () => {
    const fake = fakeSinks()
    const notifier = createNotifier(fake.sinks)
    notifier.post({ app: "Bluetooth", summary: "Pairing failed", body: "Timeout" })
    assert.equal(fake.notified.length, 1)
    assert.equal(fake.carded.length, 0)
    assert.equal(fake.notified[0].summary, "Pairing failed")
  })

  it("routes a keyed intent to the event-card path", () => {
    const fake = fakeSinks()
    const notifier = createNotifier(fake.sinks)
    notifier.post({ key: "speedtest", summary: "Speed test", body: "Running" })
    assert.equal(fake.carded.length, 1)
    assert.equal(fake.notified.length, 0)
    assert.equal(fake.carded[0].key, "speedtest")
  })

  it("routes a progress intent to the event-card path", () => {
    const fake = fakeSinks()
    const notifier = createNotifier(fake.sinks)
    notifier.post({ summary: "Copying", progress: { value: 3, max: 10 } })
    assert.equal(fake.carded.length, 1)
    assert.equal(fake.notified.length, 0)
  })

  it("treats key plus progress as a card intent", () => {
    assert.equal(
      isCardIntent({ key: "copy", summary: "Copying", progress: { value: 1, max: 2 } }),
      true,
    )
    assert.equal(isCardIntent({ summary: "Done" }), false)
  })

  it("routes dismiss to the dismiss seam", () => {
    const fake = fakeSinks()
    const notifier = createNotifier(fake.sinks)
    notifier.dismiss?.("speedtest")
    assert.deepEqual(fake.dismissed, ["speedtest"])
  })

  it("is a no-op when the dismiss seam is absent", () => {
    const notified: NotificationIntent[] = []
    const carded: NotificationIntent[] = []
    const notifier = createNotifier({
      notify: (intent) => notified.push(intent),
      card: (intent) => carded.push(intent),
    })
    assert.doesNotThrow(() => notifier.dismiss?.("nothing"))
  })
})
