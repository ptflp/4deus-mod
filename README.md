 4deus Mod

`4deus Mod` is a modular Decky Loader plugin for Steam Deck fixes and
customizations.

## Keyboard module

- Keeps the Steam keyboard above application windows when opened with a
  controller shortcut.
- Optionally keeps the keyboard open after pressing Enter.
- Adds a controller-friendly system-key layer with Ctrl, Alt, Fn, Esc, Delete,
  and F1-F12.
- Can send Alt+Shift, Ctrl+Shift, or Cmd+Space from Steam's language key while
  the system layer is active. Hold the key to choose a chord or Steam's native
  behavior; the choice is saved.
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

The Quick Access panel provides one activation row per mod. Detailed options
open in a native full-screen Decky settings route, keeping the panel compact as
new modules are added.

## Development

```bash
corepack enable pnpm
pnpm install
pnpm check
pnpm build
```

Enable **Keyboard diagnostics** in the keyboard settings to write state,
refresh, and mutation counters to Decky's `4deusMod` log every five seconds.
The option is disabled by default.

## Releases

Set the matching version in `package.json`, commit it, and push a `v*` tag.
GitHub Actions verifies the tag, runs all checks, builds `4deusMod.zip`,
generates a SHA-256 checksum, and publishes both files in a GitHub Release.

## License

MIT
