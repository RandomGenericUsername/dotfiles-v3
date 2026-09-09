# Phase 3 — State Awareness: Diagrams (MG)

Source: as-built Phase 2 runtime (`src/runtime/`, `ARCHITECTURE-SPINE.md` AD-1..AD-20, `cache-model.md`, `consumer-wiring.md`, Epic 4 single-source).
Target: Phase 3 invalidation + drift-heal + eviction. Synchronous, hexagonal, FS-authoritative. No daemon (Phase 5).

## 1. Derivation graph + invalidation edges (extends spine)

```mermaid
flowchart LR
    W[wallpaper file] -->|sha256| WH[WallpaperEntry wh]
    WH --> P[PaletteEntry<br/>hash wh + templates]
    WH --> E[EffectsEntry<br/>hash wh + catalog]
    P --> I[IconsEntry<br/>hash ph + templates + mappings]
    P --> C1[current/colors.yaml]
    P --> C2[current/colors.conf]
    P --> C3[current/colors.gtk.css]
    WH --> MWP[MonitorWallpaperConfig<br/>per monitor]
    MWP --> WP[current/wallpaper-mon.png]
    E --> EF[current/effects/]
    I --> IC[current/icons/]

    T[spine inputs<br/>csg templates] -. invalidate .-> P
    T -. invalidate .-> I
    CAT[weg effects catalog] -. invalidate .-> E
    MAP[icon templates + mappings] -. invalidate .-> I

    P -. cascade .-> I
    WH -. cascade .-> P & E
```

## 2. Phase 3 pipeline: check → invalidate → regenerate → heal → prune

```mermaid
flowchart TD
    A[recompute spine input hashes<br/>templates catalog mappings] --> B{match meta.json?}
    B -- yes --> C[cache hit: skip layer]
    B -- no --> D[selective regenerate<br/>stale layer only + cascade]
    C --> E[three-way drift check<br/>current.json vs current/ vs cache/]
    D --> E
    E -- consistent --> F[repoint current/ + save current.json + append history]
    E -- diverged/corrupt --> G[doctor repair<br/>quarantine bad meta + repopulate<br/>revert stray symlinks]
    G --> F
    F --> H[reload consumers<br/>hyprland ags hyprpaper terminal]
    H --> I[cache verify + prune<br/>keep active + last-N + seed]
```

## 3. Drift-decision sequence (doctor)

```mermaid
sequenceDiagram
    participant CLI as dotfiles-runtime doctor
    participant INV as Invalidation query
    participant CACHE as cache/ + meta.json
    participant CUR as current/ symlinks
    participant STORE as current.json/history.jsonl
    CLI->>INV: recompute input hashes
    INV->>CACHE: compare vs meta.json
    CACHE-->>CLI: stale layers[]
    CLI->>CUR: readlink all + resolve targets
    CUR-->>CLI: ok/missing/diverged/dangling
    CLI->>STORE: load current.json
    STORE-->>CLI: expected hashes
    alt diverged or corrupt
        CLI->>CACHE: quarantine + repopulate stale
        CLI->>CUR: revert/repoint to last-good
        CLI->>STORE: save + append trigger=doctor
    else consistent
        CLI-->>CLI: report clean
    end
```
