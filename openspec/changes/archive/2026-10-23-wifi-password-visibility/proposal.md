# Proposal: password field visibility toggle

## Why

The Wi-Fi password prompt masks input with no way to verify what was typed —
a classic typo-and-retry loop on long WPA keys. The approved mock
(`state-6-need-auth`) specifies an eye button beside the entry that toggles
masking. (Found during the parity-harness pass: the prompt predates changes
1–9 and had no owning change.)

## What Changes

- `components/wifi/WifiContent.tsx` (`WifiPasswordPrompt`): eye toggle
  button beside the entry flipping `Gtk.Entry` visibility; label swaps
  Show/Hide; auth flow untouched.
- `style.css`: wrap + eye-button classes per `state-6-need-auth`.

## Non-goals

- No auth-flow changes. No other prompt restyle.

## Mock anchors

- `state-6-need-auth`
