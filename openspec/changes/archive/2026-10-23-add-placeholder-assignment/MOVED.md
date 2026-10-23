# Moved to `ags-apps` (icme) + ITR half complete

The `icon-templates-renderer` half is implemented and tested
(`cli/template.py`, `adapters/file_template_writer.py`,
`tests/unit/adapters/test_file_template_writer.py`). The remaining work is the
icme GUI: wire the template tree/picker + manifest registration
(`ags-apps/icme/ui/TemplatesTab.tsx` is currently unimported), add the parity
test, docs, and the two manual checks listed in the original `tasks.md` 5.x.
Track it in `ags-apps`; this change is archived here as a pointer.
