# cli-output-cli-integration

Wire the shared `cli-output` renderer into WEG and CSG: per-CLI `OutputAdapterBase` thin-projector adapters, `projectors.py` domain→view mappings, renderer-backed `create_output_adapter` factories, canonical output shapes (errors to stderr, `{kind,message,details}` envelope), and preserved `dump-*` format override.
