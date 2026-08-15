"""Integration tests for the dotfiles provisioning system.

These tests exercise the REAL Ansible scaffold (never fakes): FR-25 dry-runs of
every playbook via ``ansible-playbook --check``, the AC-4 "makepkg never runs in
dry-run mode" proof, and an apply+verify run on a disposable container target.
"""

__all__ = []
