# Design: password field visibility toggle

## Implementation (`WifiPasswordPrompt`)

- Local `createState(false)` for revealed; entry gets
  `visibility={revealed}` (keep existing `visibility={false}` default shape —
  flip the literal to the accessor).
- Eye button (`canFocus={false}`) beside the entry in a horizontal wrap box;
  `onClicked={() => setRevealed(!revealed())}`; `tooltipText` swaps
  Show/Hide password; active tint class while revealed.
- Keep: focus-grab effect, `onActivate={join}`, error label, Cancel/Join.

## CSS (`style.css`)

- `.settings-pwd-wrap` (horizontal, entry `hexpand` carries width),
  `.settings-eye-btn` (field-surface chip, hover border, active accent tint).
  Tokens only.

## Contract table

| Mock element (`state-6-need-auth`) | Code owner |
|---|---|
| Masked entry + eye button | wrap box + `visibility` accessor |
| Show/Hide affordance | tooltip + active tint |

## Verification

- Parity gate → 0. Live: type → dots; eye → plaintext + tint; eye again →
  masked; Join path unaffected (submit masked or revealed identically).
  Screenshot vs `state-6-need-auth`.
