# 4deus Mod

[![Discord — join the 4deus community](https://img.shields.io/badge/Discord-Join_the_community-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/83eanusuRU)
[![Telegram — follow 4deus](https://img.shields.io/badge/Telegram-Follow_4deus-229ED9?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/the4deus)

`4deus Mod` is a modular Decky Loader plugin for Steam Deck fixes and
customizations.

## Getting started

Install the latest release directly from Decky Loader using the
[Getting Started guide](docs/GETTING_STARTED.md).

## Keyboard module

- Keeps the Steam keyboard above application windows when opened with a
  controller shortcut.
- Optionally keeps the keyboard open after pressing Enter.
- Adds a controller-friendly system-key layer with Ctrl, Alt, Fn, Esc, Delete,
  and F1-F12.
- Can send Alt+Shift, Ctrl+Shift, or Cmd+Space from Steam's language key while
  the system layer is active. Hold the key to choose a chord or Steam's native
  behavior directly on four keyboard keys using either trackpad; the choice is
  saved.
- Turns Steam's language key into Start while Fn is active.
- Optionally maps View, L1, R1, L4, R4, L5, or R5 to common typing keys while
  the virtual keyboard is open.
- Supports holding Ctrl, Alt, and Shift on separate Deck buttons for chords such as
  Ctrl+Shift+W with an on-screen letter.
- Supports sequential on-screen modifier chords: tap Ctrl, then hold Shift or
  Alt to latch both modifiers before pressing the final key; a short second
  modifier press sends the modifier-only chord immediately.
- Supports optional custom one-button quick chords such as
  `Ctrl+Shift+Delete` and an optional second hotkey set while R4 is held; the
  active set is shown on the space bar.
- Matches secondary and system-key labels to Steam keyboard theme states.
- Sends system chords such as Alt+Tab, Alt+Shift, and Ctrl+Shift.
- Sends system keys through a dedicated Linux `uinput` keyboard so they reach
  the focused application.
- Supports holding the Steam items key to switch the system layer on or off.
- Shows letters from a second enabled Steam keyboard layout on each key.
- Shows the secondary layout's symbols while Shift is active.
- Keeps secondary letters synchronized with Shift and Caps Lock.
- Supports automatic secondary-layout selection and a manually preferred
  layout.
- Reads layouts directly from Steam, so labels follow the layouts configured
  in Steam settings.
- Localizes plugin settings for every language currently supported by Steam.
- Provides optional keyboard diagnostics in the Decky plugin log.

Secondary labels are visual only. Steam remains responsible for the active
layout and text input.

## Controller module

- Monitors the built-in Steam Deck trackpads for the stuck calibration state.
- Optionally power-cycles the controller automatically after the guarded
  recovery checks succeed.
- Keeps recovery and developer metrics behind one module lifecycle so disabling
  Controller stops all HID monitoring without deleting either preference.

## App Bridge module

- Scans installed Flatpak and desktop applications without modifying Steam's
  shortcut database directly.
- Adds or repairs non-Steam shortcuts through Steam's live shortcut API.
- Uses one autonomous launcher with saved per-application compatibility
  profiles, so shortcuts continue to work when Decky is not loaded.
- Supports optional process tracking, Steam preload cleanup, Gamescope/X11
  environment variables, custom working directories, arguments, and
  compatibility library paths.
- Includes a quick **Add / Fix Parsec** action that keeps the Steam session
  active for Parsec's real background process.
- Includes a quick **Add / Fix RustDesk** action with Steam runtime cleanup,
  RustDesk compatibility libraries, the Gamescope/X11 environment, and
  automatic installation of the Nested Desktop pointer hook.
- Updates existing shortcuts in place to preserve their Steam app ID,
  controller layout, and play history.
- Refreshes branded portrait, grid, hero, and logo artwork for Parsec and
  RustDesk whenever their Add / Fix actions run.

## Nested Desktop module

- Provides explicit install, repair, status, and removal actions for the
  narrowly scoped MangoHud Nested Desktop compatibility fix.
- Keeps the built-in Gamescope performance overlay running when protected KWin
  processes prevent MangoApp from enumerating `/proc/<pid>/fd` or
  `/proc/<pid>/fdinfo`.
- Installs only a user-level systemd drop-in and a dedicated preload library;
  it does not replace the system MangoHud package or add runtime dependencies.
- Removes only files marked as managed by 4deus Mod and cleans the fix up when
  the plugin is uninstalled.
- Adds or repairs a **Steam Os** non-Steam shortcut for the built-in Nested
  Desktop, using a persistent launcher with the correct locale and IBus
  environment.
- Updates an existing SteamOS shortcut in place to preserve its app ID,
  controller layout, and play history.
- Refreshes all four Steam artwork slots from the bundled branded SteamOS
  artwork whenever Add / Repair runs.
- Restores right-trackpad and right-stick cursor control, configurable clicks,
  and left-pad scrolling in Nested Desktop while another Game Mode application
  is running.
- Restores the Steam Deck touchscreen in Nested Desktop, including swipes and
  multiple simultaneous contacts. Touch forwarding has its own saved switch
  and is active only while Nested Desktop owns input focus.
- Optionally extends a fast, straight, single-finger swipe with time-based
  kinetic motion and a smooth fade. Taps, holds, direction changes, slow
  drags, multitouch, new contacts, and focus loss cancel or suppress it.
- Keeps guarded touchscreen inertia tuning behind the module's Advanced
  switch, with safe ranges, an explicit Apply action, and one-click defaults.
- Fixes RustDesk's duplicate cursor, click offset, and pointer teleportation by
  relaying only its pointer events through Nested Desktop's EIS input. The
  setting is enabled by default and can be disabled without restarting
  RustDesk.
- Provides configurable controller bindings that are sent directly to Nested
  Desktop while it owns focus, including when a parallel game retains Steam
  Input.
- Starts with Steam's Desktop Configuration: A/Enter, B/Escape, X/keyboard,
  Y/Space, D-pad and left-stick arrows, View/Escape, Menu/Tab, L1/Ctrl,
  R1/Alt, L2/right click, R2/left click, R3/left click, L4/Shift, R4/Page Up,
  L5/Meta, R5/Page Down, and trackpad clicks.
- Lets every binding be reassigned or cleared, provides a master binding
  switch, and can reset the complete set to Steam defaults.
- Activates the input bridge only while Nested Desktop is frontmost, with
  configurable cursor and scroll inertia that is saved between sessions.
- Uses Decky's root process only to open the protected physical touchscreen
  and for managed systemd compatibility drop-ins. The descriptor is passed to
  the latency-sensitive Nested Desktop input worker, which still runs as the
  regular Steam Deck user and never grabs the touchscreen away from Steam.

### Why dual-language labels matter

Remote desktop clients such as Parsec and RustDesk can forward keyboard
positions or scan codes while the local or remote operating system applies the
active language layout. In that setup, the Steam keyboard may display English
keys even though the target system is typing Russian.

Switching Steam's own on-screen keyboard to Russian is not a reliable
workaround inside Gamescope or Nested Desktop. Users have reported a failure
where every letter produces `1` while number keys continue to work. RustDesk
also documents the distinction between position-based `Map 1:1` input and
character-oriented `Translate` input.

4deus Mod returns Steam to its built-in QWERTY layout when a configured system
language shortcut is used, and adds the secondary layout as visual labels. The
remote or desktop system remains responsible for language switching, while
every key shows the character that the active secondary layout will produce.

- [Nested Desktop report: letter keys produce `1`](https://www.reddit.com/r/SteamDeck/comments/1jdd0e1/nested_desktop_keyboard_problem/)
- [RustDesk keyboard translation modes](https://github.com/rustdesk/rustdesk/wiki/FAQ#keyboard-translation-modes)

## Interface

The Quick Access panel has a permanent module manager plus one tab per enabled
module. Steam's native tab navigation lets L2/R2 move between them. Disabling a
module removes its tab, stops its runtime work, and preserves the configured
feature values for the next activation. Each enabled module tab starts with a
localized Settings button, followed by its frequent, safe controls. The button
opens a short, focused full-screen settings route for that module.

## Development

```bash
corepack enable pnpm
pnpm install
pnpm check
pnpm build
```

See [Backend architecture](docs/BACKEND_ARCHITECTURE.md) for the Python module
boundaries and stable Decky/worker entrypoints.

Enable **Keyboard diagnostics** in the keyboard settings to write state,
refresh, and mutation counters to Decky's `4deusMod` log every five seconds.
The option is disabled by default and resets to off whenever the plugin
restarts.

## Releases

Set the matching version in `package.json`, commit it, and push a `v*` tag.
GitHub Actions verifies the tag, runs all checks, builds `4deusMod.zip`,
generates a SHA-256 checksum, and publishes both files in a GitHub Release.

## License

MIT
