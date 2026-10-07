# btop-theme-prototype — throwaway validation harness (phase 1)
#
# These files are INVESTIGATION ARTIFACTS, not production code. They exist to
# de-risk the OpenSpec change (add-csg-btop-theme-formats) by proving the
# generated .theme files satisfy btop 1.4.7's real parser before any wiring is
# written. Nothing here is imported by csg, the runtime, or provisioning.
#
# The production templates that ship from the spec will live at
#   src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/
# and are expected to be near-identical in structure to the *.j2 here.
#
# Colors emitted here are rendered from the DEVELOPER's live palette at
# ~/.local/state/dotfiles/current/colors.yaml and are NOT portable — regenerate,
# do not commit, if you find stale .theme files checked in below.
#
# Run:  python3 make_templates.py && python3 render.py && python3 validate.py

# rendered output from render.py (regenerate locally)
colors.btop-minimal.theme
colors.btop-balanced.theme
colors.btop-full.theme

__pycache__/
