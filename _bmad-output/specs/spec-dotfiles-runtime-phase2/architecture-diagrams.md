# Architecture Diagrams — dotfiles-runtime-phase2

Companion to SPEC-dotfiles-runtime-phase2. Diagrams for the runtime core. Mermaid blocks live here (never in the kernel).

## Dependency direction (hexagonal)

```mermaid
flowchart LR
    CLI[cli: dotfiles wallpaper set] --> APP[application: use cases]
    APP --> PORTS[ports: ABCs/Protocols]
    PORTS --> DOMAIN[domain: derivation graph]
    ADAPT[adapters: csg/weg/itr, reloaders, JSON store] --> PORTS
    ADAPT --> FS[(filesystem: cache/ + current/ + spine)]
```

## Derivation graph

```mermaid
flowchart LR
    W[wallpaper file] -->|hash| WH[WallpaperEntry hash]
    WH --> P[PaletteEntry: hash wallpaper + templates]
    WH --> E[EffectsEntry: hash wallpaper + catalog]
    P --> I[IconsEntry: hash palette + icon templates + mappings]
    P --> C[colors.conf -> current/]
    P --> CSS[colors.gtk.css -> current/]
    WH --> WP[wallpaper.png -> current/]
    E --> EF[effects/ -> current/]
    I --> IC[icons/ -> current/]
```

## First-run seeding sequence

```mermaid
sequenceDiagram
    participant U as user
    participant R as runtime
    participant S as spine (provisioning)
    participant C as cache/
    participant J as current.json + history.jsonl

    U->>R: wallpaper set img (first run)
    R->>R: current.json absent?
    R->>S: read default.png + generated/palettes/effects/icons
    R->>C: create wallpapers/<wh> (hardlink) + palettes/<ph> + effects/<eh> + icons/<ih>
    R->>J: write current.json + history (trigger: seed)
    R->>R: create current/ symlinks
```

## Cache-hit swap sequence

```mermaid
sequenceDiagram
    participant U as user
    participant R as runtime
    participant C as cache/
    participant S as current/ symlinks
    participant J as current.json + history.jsonl
    participant D as desktop (hyprland/ags/hyprpaper/terminal)

    U->>R: wallpaper set img (cached)
    R->>R: compute wh/ph/eh/ih
    R->>C: all entries present (cache hit, no tool calls)
    R->>S: repoint wallpaper -> palette -> effects -> icons
    R->>J: write current.json, append history
    R->>D: reload (hyprland reload, ags bar, hyprpaper, terminal)
```
