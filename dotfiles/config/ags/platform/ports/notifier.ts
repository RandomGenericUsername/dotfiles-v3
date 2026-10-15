/**
 * The Notifier port (spine AD-11; doc 101 §4.5).
 *
 * Senders post `NotificationIntent`s; they never construct a freedesktop call
 * or emit a bespoke event. The provider routes a **transient** intent (no `key`,
 * no `progress`) to the freedesktop `notify` sink and a **keyed or progress**
 * intent to the `card` sink — the event-card path the notifications app renders
 * in place. Both land in the same notification window; only the wire differs,
 * and the sender no longer knows which.
 *
 * WHY THE SINKS ARE INJECTED. The routing decision is policy and belongs in a
 * pure, testable core; the two wires (a Gio D-Bus call and the event-card
 * publisher) are the adapter's. Injecting them is what lets `make ags-test`
 * capture intents with a fake and assert the route without a bus.
 *
 * PURE: no `ags`, no `gi://*`, no I/O.
 */

import type { IconSource } from "./icon-source";

export interface NotificationIntent {
  /** Stable id -> updates the same card in place (routes to the event-card path). */
  readonly key?: string;
  readonly summary: string;
  readonly body?: string;
  readonly app?: string;
  readonly icon?: IconSource;
  readonly urgency?: "low" | "normal" | "critical";
  readonly timeoutMs?: number;
  /** A determinate bar (routes to the event-card path, which can update in place). */
  readonly progress?: { readonly value: number; readonly max: number };
}

export interface Notifier {
  post(intent: NotificationIntent): void;
  dismiss?(key: string): void;
}

/**
 * The two wires the provider routes between: `notify` is the freedesktop
 * one-shot; `card` is the event-card path. `dismiss` releases a keyed card.
 */
export interface NotifierSinks {
  notify(intent: NotificationIntent): void;
  card(intent: NotificationIntent): void;
  dismiss?(key: string): void;
}

/**
 * A keyed or progress intent belongs on the event-card path: it is updatable in
 * place, which a one-shot freedesktop toast is not. Everything else is
 * transient.
 */
export function isCardIntent(intent: NotificationIntent): boolean {
  return intent.key !== undefined || intent.progress !== undefined;
}

export function createNotifier(sinks: NotifierSinks): Notifier {
  return {
    post(intent: NotificationIntent): void {
      if (isCardIntent(intent)) sinks.card(intent);
      else sinks.notify(intent);
    },
    dismiss(key: string): void {
      sinks.dismiss?.(key);
    },
  };
}
