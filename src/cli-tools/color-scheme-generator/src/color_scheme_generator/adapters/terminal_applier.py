"""Apply the generated color-scheme terminal sequences to the live terminal.

After a successful ``csg generate`` that produced the ``sequences`` format,
the freshly-written ``colors.sequences`` file contains OSC escape sequences
(``\\x1b]4;N;#hex\\x1b\\\\``, ``\\x1b]10...\\x1b\\\\``...). Writing those bytes
to the controlling terminal (/dev/tty) updates the live palette immediately —
event-driven, no shell polling, no precmd hook, no source-of-truth
re-derivation: csg emits exactly what it just generated.

Guards (the "exactly like that" contract from the design decision):
  - Only applies when the ``sequences`` output was actually produced this run
    (no sequences file in ``output_files`` -> no-op).
  - Only applies when standard output is a real TTY (an interactive terminal);
    piped/CI/captured output is never corrupted.
  - Respects the effective ``apply_to_terminal`` setting (default true; the
    --apply-to-terminal / --no-apply-to-terminal CLI flag overrides it).
"""

from __future__ import annotations

import sys
from pathlib import Path

_SEQUENCES_FILENAME = "colors.sequences"


def _is_tty() -> bool:
    return sys.stdout.isatty()


def _resolve_sequences_file(output_files: tuple[Path, ...]) -> Path | None:
    for path in output_files:
        if path.name == _SEQUENCES_FILENAME:
            return path
    return None


def _emit_to_terminal(sequences_path: Path) -> str:
    """Write the sequences file bytes to /dev/tty. Returns the sequence content
    (for the caller's summary/logs); the side effect recolors the terminal.

    Opening /dev/tty directly guarantees the codes reach the controlling
    terminal regardless of how stdout was redirected, but we only call this
    when stdout is a TTY anyway.
    """
    content = sequences_path.read_bytes()
    with open("/dev/tty", "wb") as tty:
        tty.write(content)
        tty.flush()
    return content.decode(errors="replace")


def apply_to_terminal(
    output_files: tuple[Path, ...],
    enabled: bool,
) -> Path | None:
    """Apply the generated sequences to the live terminal if every guard
    passes. Returns the sequences path that was applied, or None if it was a
    no-op (no sequences output, not a TTY, or apply disabled)."""
    if not enabled:
        return None
    sequences_path = _resolve_sequences_file(output_files)
    if sequences_path is None:
        return None
    if not _is_tty():
        return None
    _emit_to_terminal(sequences_path)
    return sequences_path
