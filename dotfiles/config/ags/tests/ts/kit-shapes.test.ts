import assert from "node:assert/strict"
import { test } from "node:test"
import { iconByVariant } from "ags-platform/ports/icon-source"
import type {
  BarContext,
  BarWidgetSpec,
  CollectionSpec,
  DescriptorSpec,
  ForeignCollectionSpec,
  RichWidgetSpec,
  Shell,
  WidgetSpec,
} from "../../kit/shapes.ts"

/**
 * The widget vocabulary (spine AD-8; doc 101 §5).
 *
 * The TYPE test is the assignment: if any of the four shapes stopped extending
 * the one `Shell<S>`, this file would fail to compile under
 * `tsc -p tsconfig.tests.json` and `make ags-test` would go red. The runtime
 * assertions are a formality so `node --test` has something to run.
 *
 * The pure vocabulary leaves the rendered subtree type `E` opaque (`unknown`);
 * the app specializes it to `JSX.Element` in `kit/widget.tsx`. These tests use
 * `string` as the element type to show the parameter is threaded through.
 */
test("every shape shares one Shell, and BarWidgetSpec is realized from DescriptorSpec", () => {
  const descriptor: DescriptorSpec<undefined> = {
    id: "btop",
    read: () => undefined,
    icon: iconByVariant("btop", () => "btop"),
  }

  // The four live descriptors declare BarWidgetSpec<S>; the alias must accept a
  // DescriptorSpec so they typecheck unchanged.
  const legacy: BarWidgetSpec<undefined> = descriptor

  const rich: RichWidgetSpec<undefined, string> = {
    id: "clock",
    read: () => undefined,
    content: () => "<clock/>",
  }

  const collection: CollectionSpec<string, undefined, string> = {
    id: "workspaces",
    read: () => undefined,
    items: () => ["1"],
    key: (item) => item,
    item: (item): WidgetSpec<undefined, string> => ({ id: `ws-${item}`, read: () => undefined }),
  }

  const foreign: ForeignCollectionSpec<string, undefined, string> = {
    id: "tray",
    read: () => undefined,
    items: () => ["sni"],
    render: () => "<tray/>",
  }

  const shells: readonly Shell<undefined>[] = [descriptor, legacy, rich, collection, foreign]
  assert.equal(shells.length, 5)

  // The rich shape renders through the injected BarContext (AD-8); popup and
  // hub.control are CAPABILITIES on it, not shapes.
  const ctx: BarContext = {
    popup: () => {},
    hub: { control: () => {} },
  }
  assert.equal(typeof ctx.popup, "function")
  assert.equal(typeof ctx.hub.control, "function")
})
