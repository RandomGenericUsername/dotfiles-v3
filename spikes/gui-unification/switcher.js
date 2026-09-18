/* Palette switcher for the GUI-unification mocks.
 *
 * Proves the spec's core claim: every surface is palette-token driven, so a
 * palette swap restyles every tool with no structural change. Flip between the
 * live runtime palette and the one captured in juan david's screenshots. */
(function () {
  const PRESETS = [
    { id: "live", label: "Live palette" },
    { id: "shot", label: "Screenshot palette" },
  ];

  function apply(id) {
    document.documentElement.setAttribute("data-palette", id);
    try { localStorage.setItem("mock-palette", id); } catch (e) {}
    document.querySelectorAll(".palette-switch button").forEach((b) => {
      b.setAttribute("aria-pressed", String(b.dataset.palette === id));
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    const saved = (() => {
      try { return localStorage.getItem("mock-palette"); } catch (e) { return null; }
    })();
    const initial = saved || "live";

    const bar = document.createElement("div");
    bar.className = "palette-switch";
    PRESETS.forEach((p) => {
      const b = document.createElement("button");
      b.textContent = p.label;
      b.dataset.palette = p.id;
      b.setAttribute("aria-pressed", "false");
      b.addEventListener("click", () => apply(p.id));
      bar.appendChild(b);
    });
    document.body.appendChild(bar);
    apply(initial);
  });
})();
