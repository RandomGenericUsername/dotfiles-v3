## Purpose

Clipboard history for Hyprland: a resident watcher that captures copied text and images (with smart type classification), persists them locally, and serves a keyboard-driven AGS overlay for searching, favoriting, and re-copying past items, with incognito available through the runtime hub.

## ADDED Requirements

### Requirement: Event-driven clipboard detection

The clipboard watcher SHALL detect changes through the compositor's `wlr-data-control` protocol so that it wakes only when the selection actually changes and consumes no CPU while idle. It MUST NOT poll on the healthy path. A hash-compare polling loop MAY run only as an explicitly declared degraded mode when the data-control protocol is unavailable, and the watcher SHALL report which mode it is in.

#### Scenario: Change wakes the watcher
- **WHEN** the user copies new content while the watcher is running in protocol mode
- **THEN** the watcher is notified of the change without having polled and records exactly one new history entry

#### Scenario: Idle consumes no cycles
- **WHEN** the clipboard is unchanged
- **THEN** the watcher performs no periodic clipboard reads

#### Scenario: Degraded mode is declared
- **WHEN** the data-control protocol is unavailable at startup
- **THEN** the watcher runs the polling fallback and reports the degraded mode rather than failing silently

#### Scenario: Same content is not duplicated
- **WHEN** identical content is copied twice
- **THEN** the history contains one entry whose recency is updated, and no second entry is created

### Requirement: Content type classification

The watcher SHALL classify each captured item as text, image, link, code, hexadecimal color, or emoji, using clipboard MIME types plus content inspection. Images SHALL be stored as files; every other type SHALL be stored as text. When multiple representations are present (for example a browser offering both `image/png` and `text/plain`), image SHALL take precedence.

#### Scenario: Plain text
- **WHEN** the user copies arbitrary prose
- **THEN** the item is classified as text and its preview is the text content

#### Scenario: Image
- **WHEN** the clipboard offers an `image/*` representation
- **THEN** the image is written to the cache directory and the item references its path

#### Scenario: Link
- **WHEN** the clipboard offers `text/uri-list` or a single URL
- **THEN** the item is classified as a link

#### Scenario: Hex color
- **WHEN** the clipboard content is a bare hex color value such as `#1e1e2e`
- **THEN** the item is classified as a color

#### Scenario: Code and emoji distinctions
- **WHEN** the clipboard content is recognizable code or consists of emoji
- **THEN** the item is classified as code or emoji respectively

### Requirement: History persistence and retention

History SHALL persist as a JSON document under the user's state directory (`$XDG_STATE_HOME/hypr-pano/`), with image files under the cache directory (`~/.cache/hypr-pano/`). Writes SHALL be atomic. Each item SHALL carry a content hash, a type, a creation/recency timestamp, and a favorite flag. Retention SHALL be enforced per type using configured limits, evicting the oldest non-favorite items first, and favorites SHALL be exempt from automatic eviction. The store SHALL start empty; no pre-existing SQLite history is imported.

#### Scenario: Persistence across restarts
- **WHEN** the watcher is stopped and started again
- **THEN** previously captured items are still listed in history

#### Scenario: Per-type limit enforced
- **WHEN** more text items are captured than the configured text limit
- **THEN** the oldest non-favorite text items are evicted until the count is within the limit

#### Scenario: Favorites are retained
- **WHEN** the oldest item under a type is a favorite and the type exceeds its limit
- **THEN** that favorite is not evicted and a non-favorite item is evicted instead

#### Scenario: Atomic write survives interruption
- **WHEN** the process is interrupted during a history write
- **THEN** the previous history document remains readable and uncorrupted

### Requirement: Configurable retention

Settings SHALL be read from `~/.config/hypr-pano/config.json`; that file is the only settings surface and there is no settings GUI. It SHALL define per-type retention limits. When the file is missing, unreadable, or invalid, the watcher SHALL fall back to built-in defaults and continue operating while reporting the problem.

#### Scenario: Custom limits applied
- **WHEN** the config sets a distinct limit for images
- **THEN** image eviction follows that limit while other types use their own configured or default limits

#### Scenario: Missing config uses defaults
- **WHEN** no config file exists
- **THEN** the watcher runs with built-in defaults without error

#### Scenario: Invalid config is tolerated
- **WHEN** the config file is malformed JSON
- **THEN** the watcher reports the problem, uses defaults, and continues capturing

### Requirement: Runtime hub integration

The watcher SHALL run as a resident runtime job registered with the session hub, renewing its lease while alive and ending it on exit. On every accepted change it SHALL publish a `clipboard.update` domain event on the `org.dotfiles.Events1` interface whose payload carries the item type, content hash, and a preview or image path — never raw binary. The topic SHALL be delivered by hydration-then-signal semantics (subscribe, hydrate, discard stale `(epoch, seq)`), and the watcher SHALL operate in a loud but non-fatal degraded mode when the hub is absent.

#### Scenario: Job is registered and renewed
- **WHEN** the clipboard job starts with the hub present
- **THEN** it appears in the hub's active jobs and remains present while it runs

#### Scenario: Change publishes an event
- **WHEN** new content is captured
- **THEN** a `clipboard.update` event describing that item is published to the hub

#### Scenario: No binary over the bus
- **WHEN** a copied image is published
- **THEN** the event carries the image path and hash rather than image bytes

#### Scenario: Hub absent degrades loudly
- **WHEN** the watcher starts and no hub is present
- **THEN** it continues capturing locally and reports reduced functionality instead of exiting silently

#### Scenario: Payload fields decode as plain values
- **WHEN** a consumer receives a `clipboard.update` signal or its hydration reply
- **THEN** the payload fields (`type`, `hash`, `path`, `preview`, `_epoch`, `_seq`) are plain scalars rather than wrapped variant objects

### Requirement: Incognito control

The clipboard job SHALL serve the hub's control channel for `pause`, `resume`, and `stop`. While paused, the watcher MUST NOT add any captured content to history. The job SHALL expose its paused/running state so consumers can reflect it.

#### Scenario: Pause suspends capture
- **WHEN** a `pause` control is received and content is subsequently copied
- **THEN** no history entry is added for that content

#### Scenario: Resume restores capture
- **WHEN** a `resume` control is received and content is then copied
- **THEN** the content is captured normally

#### Scenario: Stop ends the job
- **WHEN** a `stop` control is received
- **THEN** the job finalizes and its lease is ended

#### Scenario: Unknown control fails loudly
- **WHEN** an unsupported control action is received
- **THEN** the job returns a typed error and does not change state

### Requirement: Overlay UI presentation

The GUI SHALL be a standalone AGS application rendered as a bottom-anchored layer-shell overlay containing a search field and a horizontal strip of item cards. Each card SHALL show a preview appropriate to its type (text excerpt, image thumbnail, link, code, color swatch, or emoji) and a type-distinguishing icon. The list SHALL update live from clipboard events without polling, and SHALL show an explicit empty state when there is no history.

#### Scenario: Overlay opens at the bottom
- **WHEN** the UI is toggled open
- **THEN** an overlay appears anchored to the bottom of the screen above other windows

#### Scenario: Live update on capture
- **WHEN** the overlay is open and new content is captured
- **THEN** a new card appears without the UI re-reading history on a timer

#### Scenario: Search filters history
- **WHEN** text is entered in the search field
- **THEN** only items matching the query remain listed

#### Scenario: Empty history
- **WHEN** history is empty
- **THEN** the overlay shows an explicit empty state rather than a blank strip

#### Scenario: Position badge
- **WHEN** items are listed
- **THEN** each card shows its 1-based list position so the `Ctrl+1..9` shortcut is discoverable

#### Scenario: Follows the generated palette
- **WHEN** the overlay is rendered
- **THEN** its colors come from the runtime-generated palette (`colors.css`: `@color_background`/`@color_foreground`/`@color_00..15`), so a wallpaper/palette change restyles the overlay like the bar, capture tool, and rofi launcher

### Requirement: Selection, copy-back, and window lifecycle

Selecting an item SHALL place its content back on the system clipboard with the correct representation (plain text or `image/png` for images) so it can be pasted. Items SHALL be selectable by mouse and by keyboard, including arrow navigation, Enter to copy the focused item, `Ctrl+1..9` to copy by position, and Delete to remove an item; a favorite toggle SHALL be available. Keyboard commands MUST reach the overlay even while the search field holds focus (handled before the text widget consumes them). The overlay MUST close on Escape, hide after a copy is performed, and hide when the toggle/launcher closes it.

#### Scenario: Click copies an item
- **WHEN** an item card is clicked
- **THEN** its content is placed on the clipboard and the overlay hides

#### Scenario: Enter copies the focused item
- **WHEN** an item is focused and Enter is pressed
- **THEN** that item is copied and the overlay hides

#### Scenario: Numbered shortcut
- **WHEN** `Ctrl+3` is pressed
- **THEN** the third item in the current list is copied

#### Scenario: Delete removes an item
- **WHEN** Delete is pressed on a focused item
- **THEN** that item is removed from history and the list updates

#### Scenario: Favorite toggle
- **WHEN** the favorite shortcut is used on an item
- **THEN** the item's favorite flag toggles and persists in history

#### Scenario: Image round-trip
- **WHEN** an image item is selected
- **THEN** the clipboard offers `image/png` content that a paste target can consume

#### Scenario: Dismiss behaviors
- **WHEN** Escape is pressed, a copy completes, or the toggle/launcher is invoked again
- **THEN** the overlay hides

#### Scenario: Navigation works while typing
- **WHEN** the search field has focus and an arrow or `Ctrl+1..9` is pressed
- **THEN** the overlay navigates/copies instead of the search field consuming the key

### Requirement: Standalone instance identity and toggle

The GUI SHALL run as its own AGS instance with a stable name separate from the bar, and SHALL be toggled by a desktop keybind that opens the window when the instance is running and starts a fresh instance when it is not, so the keybind is never a silent no-op.

#### Scenario: Toggle opens and closes
- **WHEN** the keybind is pressed with the instance running
- **THEN** the overlay visibility toggles without affecting the bar

#### Scenario: Keybind restarts a stopped instance
- **WHEN** the keybind is pressed after the instance has exited
- **THEN** a fresh instance starts and the overlay opens

### Requirement: Provisioning and autostart

Provisioning SHALL deploy the AGS application to a dedicated config directory and symlink it into the user's config, install the toggle launcher, and autostart both the runtime clipboard job and the AGS instance at session start. The runtime job SHALL be started so that clipboard history accumulates whether or not the overlay has ever been opened.

#### Scenario: Deployed application
- **WHEN** provisioning runs
- **THEN** the AGS app directory exists and the user config symlink resolves to it

#### Scenario: Session autostart
- **WHEN** a Hyprland session starts
- **THEN** the clipboard job is running and the AGS instance is available to toggle

#### Scenario: History accumulates without the UI
- **WHEN** a Hyprland session has started but the overlay has never been opened
- **THEN** copied content is still recorded in history

#### Scenario: Job unit template change restarts the job
- **WHEN** provisioning rewrites the clipboard job's systemd user unit template
- **THEN** an already-running job is restarted so the change takes effect, while an unchanged template leaves the running job untouched
